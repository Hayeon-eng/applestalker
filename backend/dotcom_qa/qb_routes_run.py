"""
qb_routes_run.py — 대량 검수 백그라운드 실행 (/run, /run-status, /run-progress) [qb_api 분할]

[2026-07 수정] 검수 실행이 끝난 뒤, 페이지별 Dictionary 후보(candidate_hits)를 제품
단위로 모아 spec_dict_review.aggregate()로 "여러 페이지 반복 발견" 여부와 Confidence를
재검증한다. Dictionary는 보조 기능이므로 이 결과는 summary(score/critical/warning)에는
전혀 영향을 주지 않고, run 이벤트/이력에 별도 필드(dictionary_review)로만 붙는다.
프론트엔드는 이 필드를 항상 접힌 상태의 'Dictionary Review' 섹션에서만 사용한다.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
import schema_checker
import html_qa_scoring
import spec_dict_review
from database import SessionLocal
from models import QbHistory

import qb_core
from qb_core import qb_router, _registry
from qb_routes_history import _history_save  # [분할 누락 수정] 크롤 종료 시 이력 저장 — 없으면 NameError로 크롤이 죽음

# ── 대량 크롤(91개 등)을 하나의 긴 요청에 물지 않기 위한 백그라운드 실행 ──
# Apple Stalker의 /trigger-crawl/all + /api/crawl-progress 패턴과 동일:
#  1) POST /run 은 즉시 반환(started) — 요청이 오래 걸리지 않아 "Failed to fetch" 방지
#  2) 실제 크롤은 백그라운드 태스크에서, 동시성 제한(세마포어)으로 "나눠서" 처리
#     → 91개를 한꺼번에 열지 않고, 한 번에 QB_RUN_CONCURRENCY(기본 6)개씩만 진행
#  3) 진행 상황은 SSE로 스트리밍, 완료되면 이력에 저장
_RUN_STATE: Dict[str, Any] = {"running": False, "run_id": None, "done": 0, "total": 0,
                              "events": [], "result_run_id": None, "summary": None,
                              "dictionary_review": {}}
_RUN_CONCURRENCY = int(os.getenv("QB_RUN_CONCURRENCY", "6"))


async def _run_batch(product, sitecodes, run_id, page_types=None, products=None):
    from crawler import HybridCrawler
    targets = _registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        targets = [t for t in targets if t["sitecode"] in want]
    # 페이지타입 필터(PDP/Compare 등 — 선택된 것만)
    if page_types:
        pset = {p for p in page_types}
        targets = [t for t in targets if (t.get("page_type") or runner.page_type_from_url(t.get("url", ""))) in pset]
    # 제품 필터(galaxy-s26-ultra 등 — 선택된 것만). URL 슬러그로 판별
    if products:
        prset = {p for p in products}
        targets = [t for t in targets if runner.product_from_url(t.get("url", "")) in prset]

    _RUN_STATE.update(running=True, run_id=run_id, done=0, total=len(targets), ts=__import__("time").time(),
                      events=[{"type": "start", "total": len(targets)}], result_run_id=None, summary=None,
                      dictionary_review={})

    # 필터 결과가 0개면 조용히 끝나지 않고 명확히 알린다(제품/사이트/타입 필터가 서로 안 맞는 흔한 케이스)
    if not targets:
        _RUN_STATE["events"].append({"type": "error",
            "message": "선택한 사이트·제품·페이지타입 조합에 해당하는 크롤 대상이 없습니다. "
                       "제품 필터를 비우면(전체) 해당 사이트의 모든 제품을 검수합니다."})
        _RUN_STATE.update(running=False)
        return

    crawler = None
    try:
        crawler = HybridCrawler()
        await crawler.start()
        sem = asyncio.Semaphore(_RUN_CONCURRENCY)  # 동시 진행 개수를 제한해 '나눠서' 처리
        rules_cache: Dict[str, Any] = {}
        results: List[Optional[Dict[str, Any]]] = [None] * len(targets)
        # [2026-07 FIX] spec_v2가 "스펙 값 0개 + httpx로만 수집됨"을 진단한 페이지만
        # 골라 Playwright로 재렌더 후 재검수한다. 전체 크롤 속도 유지를 위해 예산을 둔다.
        spec_rescue_cap = int(os.getenv("QB_SPEC_RESCUE_CAP", "30"))
        spec_rescue_state = {"used": 0}

        def rules_for(pt, mp):
            key = f"{pt}|{mp}"
            if key not in rules_cache:
                rules_cache[key] = runner.load_rules(product, page_type=pt, market_product=mp)
            return rules_cache[key]

        async def one(i: int, site: Dict[str, Any]):
            async with sem:
                url = site.get("url", "")
                pt = site.get("page_type") or runner.page_type_from_url(url)
                mp = runner.product_from_url(url)
                html, err, rendered_by = None, None, None
                try:
                    res = await crawler.force_render(url) if pt.lower() == "compare" else await crawler.crawl(url, requires_js=True)
                    html = (res or {}).get("html_content")
                    err = (res or {}).get("error")
                    rendered_by = (res or {}).get("rendered_by")
                except Exception as e:
                    err = str(e)
                try:
                    if html:
                        row = runner.run_site(site, html, rules_for(pt, mp), page_type=pt, rendered_by=rendered_by)
                        # [2026-07 FIX] "스펙 값 0개 + httpx로만 수집됨" 진단이면, 이 페이지만
                        # Playwright로 재렌더해 재검수한다(Compare 포함 — 룰 자체는 이미 정상
                        # 적용되지만, JS 미렌더 HTML엔 애초에 스펙 텍스트가 없어 판정 불가했던 경우).
                        diag = ((row.get("spec_v2") or {}).get("summary") or {}).get("diagnosis")
                        if diag and diag.get("rendered_by") == "httpx" and spec_rescue_state["used"] < spec_rescue_cap:
                            spec_rescue_state["used"] += 1
                            try:
                                pw = await crawler.force_render(url)
                            except Exception as e:
                                pw = {"error": str(e)}
                            if pw and pw.get("html_content") and not pw.get("error"):
                                row = runner.run_site(site, pw["html_content"], rules_for(pt, mp),
                                                       page_type=pt, rendered_by="playwright(spec_rescue)")
                        ok = True
                    else:
                        raise RuntimeError(err or "no html")
                except Exception as e:
                    row = {"sitecode": site.get("sitecode"), "url": url, "region": site.get("region"),
                           "country": site.get("country"), "page_type": pt,
                           "schema": {"summary": {}, "findings": [
                               {"block": "(collection failed)", "status": "fail",
                                "as_is": f"HTML collection failed{(' — ' + str(e)) if str(e) else ''}",
                                "to_be": "Check blocking / unrendered JS / timeout, then retry"}]},
                           "copy": {"summary": {}, "findings": []},
                           "html_qa": None}
                    ok = False
                results[i] = row
                _RUN_STATE["done"] += 1
                _RUN_STATE["ts"] = __import__("time").time()
                _RUN_STATE["events"].append({"type": "page_done", "sitecode": site.get("sitecode"), "ok": ok,
                                             "done": _RUN_STATE["done"], "total": _RUN_STATE["total"]})

        # 개별 사이트 실패가 전체를 죽이지 않도록 return_exceptions=True
        await asyncio.gather(*(one(i, s) for i, s in enumerate(targets)), return_exceptions=True)

        final = [r for r in results if r]
        qb_core.LAST_RESULTS = final
        summary = qa_report.summary_counts(final)

        # ── Dictionary Review 집계(보조 기능) — summary에는 영향 없음 ──
        try:
            dict_review = spec_dict_review.aggregate(final)
        except Exception as e:
            print(f"[qb_routes_run] dictionary_review aggregate skip: {e}")
            dict_review = {}
        # 페이지 결과에도 되돌려 붙여준다 — 프론트가 SpecV2Panel마다 다시 계산할 필요 없이
        # 제품 단위로 이미 필터링된 최종 후보를 그대로 렌더링만 하면 되게.
        for pr in final:
            sv = pr.get("spec_v2")
            if sv is not None:
                sv["dictionary_review"] = dict_review.get(pr.get("product") or "unknown", [])

        entry = _history_save(final, summary, product=product,
                              scope=("전체" if not sitecodes else f"{len(sitecodes)}개 사이트"))
        _RUN_STATE["events"].append({"type": "done", "run_id": entry["run_id"], "summary": summary})
        _RUN_STATE.update(result_run_id=entry["run_id"], summary=summary, dictionary_review=dict_review)
    except Exception as e:
        # 배치 전체가 실패해도 상태는 반드시 풀어준다(안 그러면 이후 /run이 계속 409)
        _RUN_STATE["events"].append({"type": "error", "message": str(e)})
    finally:
        if crawler is not None:
            try:
                await crawler.close()
            except Exception:
                pass
        _RUN_STATE.update(running=False)  # 성공/실패 무관 — 항상 해제


@qb_router.post("/run-reset")
def qb_run_reset():
    """검수 상태를 강제로 해제(멈춘 상태에서 409가 계속 날 때 수동 복구용)."""
    _RUN_STATE.update(running=False)
    return {"ok": True, "running": False}

@qb_router.post("/run")
async def qb_run(payload: Dict[str, Any] = Body(default={})):
    # stale 가드: '진행 중'인데 마지막 진행이 오래됐으면(크래시로 갇힘) 자동 해제
    import time as _t
    if _RUN_STATE.get("running"):
        last = _RUN_STATE.get("ts", 0)
        if last and (_t.time() - last) > 300:   # 5분 무진행 → 죽은 것으로 간주
            _RUN_STATE.update(running=False)
        else:
            raise HTTPException(409, "이미 검수가 진행 중입니다. 완료 후 다시 시도하세요.")
    product = payload.get("product", "M3")
    sitecodes = payload.get("sitecodes")
    page_types = payload.get("page_types")   # ["PDP","Compare"] 등 (없으면 전체)
    products = payload.get("products")        # ["galaxy-s26-ultra", ...] (없으면 전체)
    run_id = f"qb_{datetime.now():%Y%m%d_%H%M%S}"
    # total은 실제 필터 적용 후 개수로
    tgt = _registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        tgt = [t for t in tgt if t["sitecode"] in want]
    if page_types:
        pset = set(page_types)
        tgt = [t for t in tgt if (t.get("page_type") or runner.page_type_from_url(t.get("url", ""))) in pset]
    if products:
        prset = set(products)
        tgt = [t for t in tgt if runner.product_from_url(t.get("url", "")) in prset]
    total = len(tgt)
    asyncio.create_task(_run_batch(product, sitecodes, run_id, page_types=page_types, products=products))
    return {"status": "started", "run_id": run_id, "total": total}


@qb_router.get("/run-status")
def qb_run_status():
    return {"running": _RUN_STATE.get("running", False), "done": _RUN_STATE.get("done", 0),
            "total": _RUN_STATE.get("total", 0), "result_run_id": _RUN_STATE.get("result_run_id")}


@qb_router.get("/run-progress")
async def qb_run_progress():
    """SSE — Apple Stalker의 /api/crawl-progress와 동일한 이벤트 형식(start/page_done/done/status)."""
    async def gen():
        last = 0
        while True:
            evs = _RUN_STATE.get("events", [])
            while last < len(evs):
                yield f"data: {json.dumps(evs[last], ensure_ascii=False)}\n\n"; last += 1
            if not _RUN_STATE.get("running") and last >= len(evs):
                yield f"data: {json.dumps({'type': 'status', 'crawling': False})}\n\n"
                break
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream")

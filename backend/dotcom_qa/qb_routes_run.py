"""
qb_routes_run.py — 대량 검수 백그라운드 실행 (/run, /run-status, /run-progress) [qb_api 분할]
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
from database import SessionLocal
from models import QbHistory

import qb_core
from qb_core import qb_router, _registry

# ── 대량 크롤(91개 등)을 하나의 긴 요청에 물지 않기 위한 백그라운드 실행 ──
# Apple Stalker의 /trigger-crawl/all + /api/crawl-progress 패턴과 동일:
#  1) POST /run 은 즉시 반환(started) — 요청이 오래 걸리지 않아 "Failed to fetch" 방지
#  2) 실제 크롤은 백그라운드 태스크에서, 동시성 제한(세마포어)으로 "나눠서" 처리
#     → 91개를 한꺼번에 열지 않고, 한 번에 QB_RUN_CONCURRENCY(기본 6)개씩만 진행
#  3) 진행 상황은 SSE로 스트리밍, 완료되면 이력에 저장
_RUN_STATE: Dict[str, Any] = {"running": False, "run_id": None, "done": 0, "total": 0,
                              "events": [], "result_run_id": None, "summary": None}
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
                      events=[{"type": "start", "total": len(targets)}], result_run_id=None, summary=None)

    crawler = None
    try:
        crawler = HybridCrawler()
        await crawler.start()
        sem = asyncio.Semaphore(_RUN_CONCURRENCY)  # 동시 진행 개수를 제한해 '나눠서' 처리
        rules_cache: Dict[str, Any] = {}
        results: List[Optional[Dict[str, Any]]] = [None] * len(targets)

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
                    res = await crawler.crawl(url, requires_js=True)
                    html = (res or {}).get("html_content")
                    err = (res or {}).get("error")
                    rendered_by = (res or {}).get("rendered_by")
                except Exception as e:
                    err = str(e)
                try:
                    if html:
                        row = runner.run_site(site, html, rules_for(pt, mp), page_type=pt, rendered_by=rendered_by)
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
        entry = _history_save(final, summary, product=product,
                              scope=("전체" if not sitecodes else f"{len(sitecodes)}개 사이트"))
        _RUN_STATE["events"].append({"type": "done", "run_id": entry["run_id"], "summary": summary})
        _RUN_STATE.update(result_run_id=entry["run_id"], summary=summary)
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



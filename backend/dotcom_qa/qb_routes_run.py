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


def _filter_targets(sitecodes=None, page_types=None, products=None) -> List[Dict[str, Any]]:
    """사이트/페이지타입/제품 필터를 그대로 적용한 크롤 대상 목록. /run(총 개수 계산),
    _run_batch(실제 크롤), /run-estimate(예상 시간 계산)가 동일 로직을 공유한다."""
    targets = _registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        targets = [t for t in targets if t["sitecode"] in want]
    if page_types:
        pset = set(page_types)
        # [2026-09 D1] 레지스트리에 없는 파생 페이지타입(Specs/Buying)을 요청하면 PDP 엔트리에서 URL 을
        # 생성해 추가한다(존재 여부는 크롤 status 로 확인 — 404 는 Not Checked 시트로).
        have = {(t.get("page_type") or runner.page_type_from_url(t.get("url", ""))) for t in targets}
        derived = []
        for want in pset & set(runner.DERIVED_PAGE_TYPES):
            if want in have:
                continue
            for t in targets:
                if (t.get("page_type") or runner.page_type_from_url(t.get("url", ""))) != "PDP":
                    continue
                d = dict(t); d["url"] = runner.derive_page_url(t["url"], want); d["page_type"] = want; d["derived"] = True
                derived.append(d)
        targets = targets + derived
        targets = [t for t in targets if (t.get("page_type") or runner.page_type_from_url(t.get("url", ""))) in pset]
    if products:
        prset = set(products)
        targets = [t for t in targets if runner.product_from_url(t.get("url", "")) in prset]
    return targets


async def _run_batch(product, sitecodes, run_id, page_types=None, products=None, mode="all"):
    # [2026-07 FIX] 절대 `from crawler import HybridCrawler`(bare import) 쓰지 말 것 —
    # backend/crawler.py(구버전, js_timeout_ms=30000)와 이름이 겹쳐서, 먼저 로드된
    # 쪽이 sys.modules에 캐시되면 이후 sys.path를 아무리 바꿔도 그 캐시가 재사용된다.
    # 실제로 main.py → crawl_service.py가 먼저 "crawler"를 임포트해 구버전이 캐시되고,
    # 그 결과 Compare 페이지가 dotcom_qa/crawler.py(50초 타임아웃 + 강제 지연로딩
    # 스크롤 개선판)가 아니라 구버전으로 계속 렌더링되어 30초 타임아웃이 반복됐다.
    # qb_core._load_qb_crawler_cls()가 파일 경로로 직접 로드해 이 충돌을 피한다.
    from qb_core import _load_qb_crawler_cls
    HybridCrawler = _load_qb_crawler_cls()
    import time as _time
    mode = (mode or "all").lower()
    targets = _filter_targets(sitecodes, page_types, products)

    start_ts = _time.time()
    _RUN_STATE.update(running=True, run_id=run_id, done=0, total=len(targets), ts=start_ts, mode=mode,
                      events=[{"type": "start", "total": len(targets), "mode": mode}],
                      result_run_id=None, summary=None, dictionary_review={})

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
                html, err, rendered_by, http_status, final_url = None, None, None, None, None
                try:
                    res = await crawler.force_render(url) if pt.lower() == "compare" else await crawler.crawl(url, requires_js=True)
                    html = (res or {}).get("html_content")
                    err = (res or {}).get("error")
                    rendered_by = (res or {}).get("rendered_by")
                    http_status = (res or {}).get("status_code")   # [D8]
                    final_url = (res or {}).get("final_url")
                except Exception as e:
                    err = str(e)
                try:
                    if html:
                        row = runner.run_site(site, html, rules_for(pt, mp), page_type=pt,
                                              rendered_by=rendered_by, mode=mode,
                                              http_status=http_status, final_url=final_url)
                        # [2026-07 FIX] "스펙 값 0개 + httpx로만 수집됨" 진단이면, 이 페이지만
                        # Playwright로 재렌더해 재검수한다(Compare 포함 — 룰 자체는 이미 정상
                        # 적용되지만, JS 미렌더 HTML엔 애초에 스펙 텍스트가 없어 판정 불가했던 경우).
                        # [2026-07 과제3] Data QA 전용 실행(mode="data")은 Spec 축을 돌리지
                        # 않으므로 재렌더 예산을 쓸 이유가 없다 → 스킵해 크롤 시간을 줄인다.
                        diag = ((row.get("spec_v2") or {}).get("summary") or {}).get("diagnosis")
                        if mode in ("all", "spec") and diag and diag.get("rendered_by") == "httpx" \
                                and spec_rescue_state["used"] < spec_rescue_cap:
                            spec_rescue_state["used"] += 1
                            try:
                                pw = await crawler.force_render(url)
                            except Exception as e:
                                pw = {"error": str(e)}
                            if pw and pw.get("html_content") and not pw.get("error"):
                                row = runner.run_site(site, pw["html_content"], rules_for(pt, mp),
                                                       page_type=pt, rendered_by="playwright(spec_rescue)",
                                                       mode=mode, http_status=pw.get("status_code") or http_status,
                                                       final_url=pw.get("final_url") or final_url)
                        ok = True
                    else:
                        raise RuntimeError(err or "no html")
                except Exception as e:
                    row = {"sitecode": site.get("sitecode"), "url": url, "region": site.get("region"),
                           "country": site.get("country"), "page_type": pt, "product": mp,
                           "http_status": http_status, "final_url": final_url, "not_checked": True,  # [D8]
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
        # [2026-09 D6] Meta Description 중복 — 같은 사이트 내 페이지 간 비교(런 단위)
        try:
            import seo_checker
            seo_checker.mark_duplicates(final)
        except Exception as e:
            print(f"[qb_routes_run] seo duplicate check skip: {e}")
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

        _mode_label = {"data": "Data QA", "spec": "Spec QA"}.get(mode, "")
        _scope = ("전체" if not sitecodes else f"{len(sitecodes)}개 사이트")
        if _mode_label:
            _scope = f"{_scope} · {_mode_label}"
        entry = _history_save(final, summary, product=product,
                              scope=_scope, duration_seconds=_time.time() - start_ts)
        _RUN_STATE["events"].append({"type": "done", "run_id": entry["run_id"], "summary": summary, "mode": mode})
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


def _historical_seconds_per_page(limit: int = 20) -> Dict[str, Any]:
    """최근 완료된 run들의 실측 duration_seconds/pages 평균 = 페이지 1개당 평균 소요초.
    QB_RUN_CONCURRENCY(동시 진행 개수)까지 이미 반영된 실측값이라 이론적 계산보다
    실제 소요시간에 가깝다. 이력이 아직 없으면(초기 배포 직후) 대략치로 폴백."""
    default_spp = 8.0  # 이력 0건일 때만 쓰는 대략치(사이트당 1페이지 렌더+검수 초안)
    db = SessionLocal()
    try:
        rows = (db.query(QbHistory)
                  .filter(QbHistory.duration_seconds.isnot(None), QbHistory.pages > 0)
                  .order_by(QbHistory.id.desc()).limit(limit).all())
    except Exception:
        rows = []
    finally:
        db.close()

    samples = [r.duration_seconds / r.pages for r in rows if r.duration_seconds and r.pages]
    if not samples:
        return {"seconds_per_page": default_spp, "sample_runs": 0}
    return {"seconds_per_page": sum(samples) / len(samples), "sample_runs": len(samples)}


@qb_router.post("/run-estimate")
def qb_run_estimate(payload: Dict[str, Any] = Body(default={})):
    """선택된 사이트/제품/페이지타입 기준 예상 소요시간(초). /run과 동일한 필터 로직을
    그대로 재사용해 실제 크롤될 페이지 수를 구하고, 최근 이력의 실측 페이지당 평균초를
    곱해 추정한다 — 실행 전에 프론트에서 미리 보여주는 용도."""
    sitecodes = payload.get("sitecodes")
    page_types = payload.get("page_types")
    products = payload.get("products")
    total_pages = len(_filter_targets(sitecodes, page_types, products))
    hist = _historical_seconds_per_page()
    seconds_per_page = hist["seconds_per_page"]
    # 동시성(세마포어) 효과가 이미 이력 실측치에 녹아있으므로 단순 곱셈으로 충분하되,
    # 페이지 수가 극히 적을 때(콜드스타트/브라우저 기동 오버헤드)는 최소치를 보장한다.
    estimated_seconds = max(seconds_per_page * total_pages, seconds_per_page if total_pages else 0)
    return {
        "total_pages": total_pages,
        "seconds_per_page": round(seconds_per_page, 2),
        "estimated_seconds": round(estimated_seconds),
        "sample_runs": hist["sample_runs"],
    }


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
    # [2026-07 과제3] Data QA / Spec QA 독립 실행. mode ∈ {"all","data","spec"} (기본 all=하위호환)
    mode = (payload.get("mode") or "all").lower()
    if mode not in ("all", "data", "spec"):
        raise HTTPException(400, f"알 수 없는 mode: {mode} (all|data|spec 중 하나)")
    run_id = f"qb_{datetime.now():%Y%m%d_%H%M%S}"
    # total은 실제 필터 적용 후 개수로
    total = len(_filter_targets(sitecodes, page_types, products))
    asyncio.create_task(_run_batch(product, sitecodes, run_id, page_types=page_types,
                                   products=products, mode=mode))
    return {"status": "started", "run_id": run_id, "total": total, "mode": mode}


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

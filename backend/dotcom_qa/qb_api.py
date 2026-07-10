"""
qb_api.py — 큐비 — Dotcom QA 체커 [Phase H 백엔드]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

기존 애플스토커 FastAPI 앱에 라우터로 얹는다(main.py):
    from dotcom_qa.qb_api import qb_router, set_fetcher
    app.include_router(qb_router)
    set_fetcher(existing_crawler_fetch)   # url -> html (없으면 /run 은 501)

엔드포인트:
  GET  /api/qb/sites                 91개 사이트(지역별)
  GET  /api/qb/rules?product=M3      스키마/카피 규칙 (화면 '?' 기준 패널용)
  POST /api/qb/check                 {html, product} 단일 HTML 검수(네트워크 불필요)
  POST /api/qb/check-html-qa         {html, product} HTML QA(Level1 적용율 + Level2 3축) 종합 채점 [신규]
  POST /api/qb/run                   {sitecodes?, product} 크롤 후 검수(주입된 fetcher 필요)
  POST /api/qb/report.xlsx           {results} → Excel 다운로드
  POST /api/qb/email-draft           {results} → 메일 초안 HTML
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))  # 패키지/스크립트 양쪽에서 flat import 허용

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
import schema_checker
import html_qa_scoring
from site_registry import SiteRegistry
from database import SessionLocal
from models import QbHistory

qb_router = APIRouter(prefix="/api/qb", tags=["qubi"])
_registry = SiteRegistry()
_fetcher: Optional[Callable[[str], Optional[str]]] = None


def set_fetcher(fn: Callable[[str], Optional[str]]):
    """기존 크롤러의 'url -> html' 함수를 주입."""
    global _fetcher
    _fetcher = fn


def enable_default_crawler(requires_js: bool = True):
    """기존 애플스토커의 HybridCrawler 를 큐비 fetcher 로 자동 연결.
    삼성닷컴은 JS 렌더링 페이지가 많아 requires_js=True 를 기본으로 둔다
    (httpx 로 충분하면 그대로 쓰고, 얇게 오면 Playwright 로 업그레이드)."""
    import asyncio

    def _fetch(url: str) -> Optional[str]:
        async def _run():
            from crawler import HybridCrawler
            c = HybridCrawler()
            await c.start()
            try:
                res = await c.crawl(url, requires_js=requires_js)
                return (res or {}).get("html_content")
            finally:
                await c.close()
        return asyncio.run(_run())

    set_fetcher(_fetch)


@qb_router.get("/sites")
def qb_sites():
    by = _registry.by_region_unique()  # 사이트코드 중복 제거 — 지역 칩엔 로케일 1개씩
    return {"count": len(_registry.unique_sitecodes()),   # 사이트(로케일) 수
            "page_count": len(_registry.all()),           # 실제 크롤 대상(제품×페이지타입) 수
            "regions": {r: [{"sitecode": s["sitecode"], "country": s["country"],
                             "lang": s["lang"], "url": s["url"]} for s in sites]
                        for r, sites in by.items()},
            "missing_lang": _registry.missing_lang()}


PAGE_TYPES = ["PDP", "Compare", "Buying"]
# 스키마 타입 사전(룰 추가 드롭다운). 나중에 직접 입력으로도 추가 가능.
SCHEMA_TYPES = [
    "WebPage", "ItemPage", "WebSite", "BreadcrumbList", "ItemList", "ListItem", "CollectionPage",
    "Product", "ProductGroup", "Offer", "AggregateOffer", "Brand", "Organization",
    "Review", "CriticReview", "AggregateRating", "BuyAction",
    "ImageObject", "VideoObject", "3DModel", "MediaObject",
    "FAQPage", "Question", "Answer", "HowTo", "Article",
    "Person", "Rating", "PropertyValue", "WebPageElement",
]


@qb_router.get("/rules")
def qb_rules(product: str = Query("M3"), page_type: str = Query("PDP"),
             market_product: str = Query(None)):
    """화면 '?' 기준 패널용 — 규칙을 사람이 읽는 형태로 그대로 반환."""
    rules = runner.load_rules(product, page_type=page_type, market_product=market_product)
    schema_set = rules.get("schema_set")
    set_label = {"flagship": "Flagship PD (스마트폰)", "simple": "Simple PD (버즈·노트북·태블릿 등)",
                 "compare": "Compare PD", None: "해당없음(Buying 등 검사 제외)"}.get(schema_set, str(schema_set))
    schema_blocks = [{
        "block": b["name"], "types": b["types"], "id": b.get("id_slug"),
        "required_properties": b.get("required_properties", []),
        "optional_properties": b.get("optional_properties", []),
        "haspart_ids": b.get("haspart_ids", []),
        "conditional": b.get("conditional"),
    } for b in rules["schema"].get("blocks", [])]
    return {
        "product": product, "page_type": page_type,
        "page_types": PAGE_TYPES, "schema_types": SCHEMA_TYPES,
        "schema_set": schema_set, "schema_set_label": set_label,
        "schema": {
            "설명": (f"[{set_label}] Word(PTK 2.4.14) 기준 필수 스키마 @type/@id/속성, "
                     f"Product.hasPart @id, 값 정확성, 조건부(WARN)"),
            "출처": "PTK_schema_set 크롬 확장 2.4.14 (Word) — Buying은 검사 제외",
            "blocks": schema_blocks,
        },
        "google_criteria": {
            "설명": "Google 기준은 두 층위로 나뉩니다 — ①문법이 파싱되는가 ②파싱된 뒤 리치결과 자격(필수/권장 속성)을 충족하는가. 실시간 Rich Results Test API 호출은 이 환경에서 불가 → Google 공식 문서 기준을 정적 룰로 반영.",
            "문법_오류": {
                "구글_기준": [
                    "스마트 따옴표(“ ” ‘ ’) 등 유니코드로 값이 코드 아닌 문자로 입력 → 경고",
                    "닫는 괄호/따옴표 부족(괄호 불균형) → 오류",
                    "항목 사이 쉼표 누락 → 오류",
                    "마지막 항목 뒤 후행 쉼표 → 경고(자동 보정)",
                    "비표시 문자(NBSP·제로폭·BOM) 포함 → 경고",
                ],
                "우리_기준": [
                    "위 Google Rich Result 문법 규칙을 동일하게 적용",
                    "about 이 배열([...])이면 오류가 아닌 '권장(object)' 경고로 완화",
                    "name 등 번역 대상 값은 오류가 아닌 '번역 확인' 경고",
                ],
            },
            "리치결과_필수_권장": {
                "필수_속성_누락_오류": [
                    "리치결과 필수 속성이 없으면 오류 — 그 즉시 리치결과 자격 상실(가이드 필수 ∪ Google 공식 필수 중 더 엄격한 쪽 적용)",
                    "필수 속성 값이 형식/기준과 안 맞으면 오류(URL 아님·ISO8601 아님 등)",
                ],
                "권장_속성_누락_경고": [
                    "권장 속성이 없으면 경고 — 자격은 유지되지만 품질 저하",
                ],
                "타입별_상태": {
                    "Product": "정식 적용", "VideoObject": "정식 적용",
                    "3DModel": "제한적(일반 리치결과 X, AR만 해당)",
                    "FAQPage": "폐지(2026-05-07 Google 공식 종료 — 스키마는 유효하나 SEO 감점/가점 대상 아님)",
                },
            },
        },
        "check_methods": {
            "설명": "카피덱 정답지 기준으로 값을 검사합니다. 검사 방식별로 오류/경고를 구분합니다.",
            "정확히_일치_오류": [
                "제품 주소가 정확한지 — url·@id·mainEntity·about·brand/manufacturer/publisher 주소가 기준과 다르면 오류(사이트코드만 치환, 제품 슬러그는 정확히 일치)",
                "연결된 제품 주소가 맞는지 — hasPart의 @id에 다른 제품 주소가 섞이면 오류",
                "제품명이 올바른지 — 번역은 허용하되 제품 식별어(예: S26 Ultra / Buds4 Pro)가 빠지거나 다른 모델명이 섞이면 오류",
                "고정값이 맞는지 — @type·@context·BuyAction 등 고정 키워드는 정확히 일치",
            ],
            "필수_있어야_함_오류": [
                "반드시 있어야 하는 필수 속성이 없으면 오류(Word 기준 required)",
            ],
            "확인_경고": [
                "번역 검토 — name·description 등 번역 대상 텍스트는 존재만 확인(원문과 달라도 오류 아님)",
                "이미지 경로 — 파일명 변동은 허용, 경로에 제품이 맞는지만 확인",
                "영상 길이 — PT#S 형식만 확인",
                "페이지 언어 — inLanguage가 사이트 언어와 다르면 확인(의도된 현지화일 수 있어 오류 아님)",
                "선택 속성 미적용 — Word 기준 optional은 없어도 경고 수준",
            ],
        },
        "copy": {
            "설명": "번역 불변 값만 검사 — 스펙 토큰(숫자+단위) 정확 일치, 고유명사 존재(WARN), 핵심 스펙 값 대조",
            "spec_tokens": rules["copy"].get("spec_tokens", []),
            "proper_nouns": rules["copy"].get("proper_nouns", []),
        },
    }


@qb_router.post("/check-html-qa")
def qb_check_html_qa(payload: Dict[str, Any] = Body(...)):
    """HTML QA 종합 채점 — Level1(적용율%) + Level2(축1 정보적합성/축2 파싱+리치결과/축3 id연결성).
    /check와 별개 엔드포인트라 기존 화면·응답 형태에 영향 없음."""
    html = payload.get("html")
    product = payload.get("product", "M3")
    page_type = payload.get("page_type", "PDP")
    if not html:
        raise HTTPException(400, "html 필드가 필요합니다.")
    rules = runner.load_rules(product, page_type=page_type,
                              market_product=payload.get("market_product") or "galaxy-s26-ultra")
    schema_result = schema_checker.check_page(html, rules["schema"],
                                              sitecode=payload.get("sitecode"),
                                              site_lang=payload.get("lang"),
                                              market_product=rules.get("market_product"))
    out = html_qa_scoring.score_html_qa(html, rules["schema"], schema_result,
                                        rendered_by=payload.get("rendered_by"))
    out["page_type"] = page_type
    out["schema_set"] = rules.get("schema_set")
    return out


@qb_router.post("/check")
def qb_check(payload: Dict[str, Any] = Body(...)):
    html = payload.get("html")
    product = payload.get("product", "M3")
    page_type = payload.get("page_type", "PDP")
    if not html:
        raise HTTPException(400, "html 필드가 필요합니다.")
    # 제품: ①명시값 ②붙여넣은 HTML의 JSON-LD @id/url에서 슬러그 자동판별 ③최후 폴백
    mp = payload.get("market_product")
    if not mp:
        import re as _re
        m = _re.search(r"samsung\.com/[^/\"']+/smartphones/(galaxy-[a-z0-9-]+?)/", html)
        # -ultra/-plus 등 정확 매칭 우선(긴 슬러그가 먼저 잡히도록 non-greedy + compare/ 접미 제거)
        mp = m.group(1) if m else None
        if mp:
            mp = mp.replace("/compare", "").rstrip("/")
    if not mp:
        mp = "galaxy-s26-ultra"
    # 붙여넣기는 URL이 없으니 page_type도 HTML에 compare 흔적 있으면 보정
    if "/compare" in (html or "") and page_type == "PDP" and payload.get("page_type") is None:
        page_type = "Compare"
    rules = runner.load_rules(product, page_type=page_type, market_product=mp)
    out = runner.check_html(html, rules, sitecode=payload.get("sitecode"), site_lang=payload.get("lang"))
    out["page_type"] = page_type
    out["market_product"] = mp
    global _LAST_RESULTS
    _LAST_RESULTS = [{"sitecode": payload.get("sitecode") or "(입력)", "url": "", "page_type": page_type,
                      "market_product": mp, "schema": out["schema"], "copy": out["copy"],
                      "html_qa": out.get("html_qa")}]
    return out


@qb_router.post("/check-url")
def qb_check_url(payload: Dict[str, Any] = Body(...)):
    """사이트 링크 1개만 넣어서 즉시 검수 (크롤 후 검사). 페이지타입은 URL 자동판별(수동 지정 가능)."""
    url = (payload.get("url") or "").strip()
    product = payload.get("product", "M3")
    if not url:
        raise HTTPException(400, "url이 필요합니다.")
    if _fetcher is None:
        raise HTTPException(501, "크롤러(fetcher)가 연결되지 않았습니다.")
    html = _fetcher(url)
    if not html:
        raise HTTPException(502, "HTML 수집 실패 — URL 접근/렌더링을 확인하세요.")
    sc = _sitecode_from_url(url)
    known = _registry.get(sc)
    page_type = payload.get("page_type") or runner.page_type_from_url(url)
    market = runner.product_from_url(url)
    rules = runner.load_rules(product, page_type=page_type, market_product=market)
    res = runner.check_html(html, rules, sitecode=sc, site_lang=(known or {}).get("lang"))
    row = {"sitecode": sc, "url": url, "page_type": page_type, "market_product": market,
           "region": (known or {}).get("region"), "country": (known or {}).get("country"),
           "schema": res["schema"], "copy": res["copy"], "html_qa": res["html_qa"],
           "html": html}  # html은 디버깅/재검수용으로 유지(선택적으로 프론트가 쓸 수 있음)
    global _LAST_RESULTS
    _LAST_RESULTS = [row]
    return row


# ── 표준 스펙 항목 사전(드롭다운 + 예시) ──
SPEC_CATALOG = [
    {"category": "display_size", "label": "디스플레이 크기", "ex_value": "6.9", "ex_unit": "inch"},
    {"category": "brightness", "label": "밝기", "ex_value": "2600", "ex_unit": "nits"},
    {"category": "refresh_rate", "label": "주사율", "ex_value": "120", "ex_unit": "Hz"},
    {"category": "camera_wide", "label": "후면 메인(Wide)", "ex_value": "200", "ex_unit": "MP"},
    {"category": "camera_ultrawide", "label": "울트라와이드", "ex_value": "50", "ex_unit": "MP"},
    {"category": "camera_telephoto", "label": "망원", "ex_value": "50", "ex_unit": "MP"},
    {"category": "camera_front", "label": "전면 카메라", "ex_value": "12", "ex_unit": "MP"},
    {"category": "space_zoom", "label": "공간 줌", "ex_value": "100", "ex_unit": "x"},
    {"category": "video_playback", "label": "영상 재생(배터리)", "ex_value": "31", "ex_unit": "hours"},
    {"category": "battery_capacity", "label": "배터리 용량", "ex_value": "5000", "ex_unit": "mAh"},
    {"category": "charging", "label": "고속충전", "ex_value": "45", "ex_unit": "W"},
    {"category": "memory", "label": "메모리", "ex_value": "16", "ex_unit": "GB"},
    {"category": "storage", "label": "저장", "ex_value": "512", "ex_unit": "GB"},
    {"category": "processor", "label": "프로세서", "ex_value": "Snapdragon 8 Elite Gen 5", "ex_unit": ""},
    {"category": "display_type", "label": "디스플레이 종류", "ex_value": "Dynamic AMOLED 2X", "ex_unit": ""},
    {"category": "camera_periscope", "label": "페리스코프 망원", "ex_value": "50", "ex_unit": "MP"},
    {"category": "wireless_charging", "label": "무선충전", "ex_value": "25", "ex_unit": "W"},
    # ── 버즈(Buds) 계열 ──
    {"category": "battery_buds", "label": "이어버드 배터리", "ex_value": "61", "ex_unit": "mAh"},
    {"category": "battery_case", "label": "케이스 배터리", "ex_value": "530", "ex_unit": "mAh"},
    {"category": "playback_anc_on", "label": "재생(ANC 켬)", "ex_value": "6", "ex_unit": "hours"},
    {"category": "playback_anc_off", "label": "재생(ANC 끔)", "ex_value": "7", "ex_unit": "hours"},
    {"category": "playback_with_case", "label": "재생(케이스 포함)", "ex_value": "30", "ex_unit": "hours"},
    {"category": "audio_bit", "label": "오디오 비트", "ex_value": "24", "ex_unit": "bit"},
    {"category": "audio_khz", "label": "오디오 샘플레이트", "ex_value": "96", "ex_unit": "kHz"},
    {"category": "ip_rating", "label": "방수방진 등급", "ex_value": "IP57", "ex_unit": ""},
]


@qb_router.get("/spec-catalog")
def qb_spec_catalog():
    return {"catalog": SPEC_CATALOG}


@qb_router.get("/products")
def qb_products():
    data = _load_specs().get("products", {})
    out = []
    for code, entry in data.items():
        label = entry.get("label", code) if isinstance(entry, dict) else code
        spec_only = entry.get("spec_only", False) if isinstance(entry, dict) else False
        out.append({"code": code, "label": label, "spec_only": spec_only})
    # key_specs.json 의 등록 순서를 그대로 유지(정렬하지 않음)
    return {"products": out}


@qb_router.post("/products/add")
def qb_products_add(payload: Dict[str, Any] = Body(...)):
    name = (payload.get("product") or "").strip()
    if not name:
        raise HTTPException(400, "product가 필요합니다.")
    label = (payload.get("label") or name).strip()
    data = _load_specs()
    prods = data.setdefault("products", {})
    if name not in prods:
        prods[name] = {"label": label, "specs": []}
    _save_specs(data)
    return {"ok": True, "products": [{"code": c, "label": (e.get("label", c) if isinstance(e, dict) else c)} for c, e in prods.items()]}


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
        global _LAST_RESULTS
        _LAST_RESULTS = final
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


# ── 검수 이력 (DB 저장) ──
# [FIX] 기존엔 dotcom_qa/qb_history/*.json 로컬 파일에 저장했으나, Render 무료 플랜은
# idle 슬립 후 재시작(또는 재배포) 시 로컬 디스크가 초기화되어 사이트를 나갔다 오면
# 이력이 전부 유실됐음. 이미 붙어있는 Postgres DB(QbHistory 테이블)에 저장하도록 변경.

def _history_index() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(QbHistory).order_by(QbHistory.id.desc()).limit(100).all()
        return [{"run_id": r.run_id, "at": r.at, "product": r.product, "scope": r.scope,
                  "pages": r.pages, "fail": r.fail, "warn": r.warn} for r in rows]
    finally:
        db.close()


def _history_save(results, summary, product="M3", scope="") -> Dict[str, Any]:
    now = datetime.now()
    run_id = now.strftime("%Y%m%d-%H%M%S")
    entry = {"run_id": run_id, "at": now.strftime("%Y-%m-%d %H:%M:%S"),
             "product": product, "scope": scope, "pages": summary.get("pages", len(results)),
             "fail": summary.get("fail", 0), "warn": summary.get("warn", 0)}
    db = SessionLocal()
    try:
        db.add(QbHistory(run_id=run_id, at=entry["at"], product=product, scope=scope,
                          pages=entry["pages"], fail=entry["fail"], warn=entry["warn"],
                          results=json.dumps(results, ensure_ascii=False, separators=(",", ":"))))
        db.commit()
        # 최근 100건만 유지 — 초과분 삭제
        old_ids = [r.id for r in db.query(QbHistory.id).order_by(QbHistory.id.desc()).offset(100).all()]
        if old_ids:
            db.query(QbHistory).filter(QbHistory.id.in_(old_ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()
    return entry


@qb_router.get("/history")
def qb_history():
    return {"history": _history_index()}


@qb_router.get("/overview")
def qb_overview():
    """전사이트 현황(A안) — 이력을 최신순으로 훑어 '각 권역의 가장 최근 검수'를 하나씩 뽑고,
    그 권역들의 AEO 퀄리티 점수를 평균낸 전사이트 점수판을 만든다.
    권역별로 나눠 검수하더라도 각 권역의 최신값을 모아 전체 현황을 보여준다."""
    db = SessionLocal()
    try:
        rows = db.query(QbHistory).order_by(QbHistory.id.desc()).limit(100).all()
    finally:
        db.close()

    # region -> {최신 검수에서 집계한 값}. 이력은 최신순이라, 어떤 region을 이미 봤으면 그게 최신.
    region_latest: Dict[str, Dict[str, Any]] = {}
    seen_regions: set = set()
    for r in rows:
        try:
            results = json.loads(r.results)
        except Exception:
            continue
        # 이 run에 포함된 region별로, 아직 확정 안 된 region만 이 run 값으로 채운다.
        by_region_here: Dict[str, List[float]] = {}
        applyacc_here: Dict[str, List[int]] = {}  # region -> [prop_ok합, prop_total합]
        run_at = r.at
        for row in results:
            region = row.get("region") or "기타"
            hq = row.get("html_qa")
            if not hq:
                continue
            fp = (hq.get("overall") or {}).get("final_pct")
            if fp is None:
                continue
            by_region_here.setdefault(region, []).append(fp)
            ov = hq.get("overall") or {}
            acc = applyacc_here.setdefault(region, [0, 0])
            acc[0] += ov.get("prop_ok") or 0
            acc[1] += ov.get("prop_total") or 0
        for region, scores in by_region_here.items():
            if region in seen_regions:
                continue  # 더 최신 run에서 이미 확정됨
            seen_regions.add(region)
            avg = round(sum(scores) / len(scores), 1) if scores else None
            acc = applyacc_here.get(region, [0, 0])
            apply_pct = round(100 * acc[0] / acc[1], 1) if acc[1] else None
            region_latest[region] = {"region": region, "avg_aeo": avg, "apply_pct": apply_pct,
                                     "prop_ok": acc[0], "prop_total": acc[1],
                                     "sites": len(scores), "at": run_at}

    regions = sorted(region_latest.values(), key=lambda x: (x["avg_aeo"] if x["avg_aeo"] is not None else -1))
    vals = [x["avg_aeo"] for x in regions if x["avg_aeo"] is not None]
    total_avg = round(sum(vals) / len(vals), 1) if vals else None
    tot_ok = sum(x.get("prop_ok") or 0 for x in regions)
    tot_all = sum(x.get("prop_total") or 0 for x in regions)
    total_apply = round(100 * tot_ok / tot_all, 1) if tot_all else None
    dist = {"green": 0, "yellow": 0, "red": 0}
    for x in regions:
        a = x["avg_aeo"]
        if a is None:
            dist["red"] += 1
        elif a >= 80:
            dist["green"] += 1
        elif a >= 50:
            dist["yellow"] += 1
        else:
            dist["red"] += 1
    return {"total_avg_aeo": total_avg, "total_apply_pct": total_apply, "region_count": len(regions),
            "regions": regions, "distribution": dist}


@qb_router.get("/history/{run_id}")
def qb_history_one(run_id: str):
    db = SessionLocal()
    try:
        row = db.query(QbHistory).filter(QbHistory.run_id == run_id).first()
        if not row:
            raise HTTPException(404, "해당 이력이 없습니다.")
        results = json.loads(row.results)
        return {"run_id": run_id, "results": results, "summary": qa_report.summary_counts(results)}
    finally:
        db.close()


@qb_router.post("/history/remove")
def qb_history_remove(payload: Dict[str, Any] = Body(...)):
    run_id = payload.get("run_id", "")
    db = SessionLocal()
    try:
        db.query(QbHistory).filter(QbHistory.run_id == run_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    return {"ok": True, "history": _history_index()}


# ── 마지막 검수 결과를 서버가 보관(Apple Stalker latest-report 패턴) ──
# → 프론트가 큰 결과를 POST로 보내지 않고 GET으로 내려받게 해 CORS preflight/"Failed to fetch" 회피
_LAST_RESULTS: List[Dict[str, Any]] = []


def _resolve_results(payload=None, run_id: str = None):
    """우선순위: 요청 body의 results → run_id 이력 → 서버가 든 마지막 결과."""
    if payload and payload.get("results"):
        return payload["results"]
    if run_id:
        db = SessionLocal()
        try:
            row = db.query(QbHistory).filter(QbHistory.run_id == run_id).first()
            if row:
                return json.loads(row.results)
        finally:
            db.close()
    return _LAST_RESULTS


@qb_router.get("/report.xlsx")
def qb_report_xlsx_get(run_id: str = Query(None)):
    data = qa_report.build_xlsx(_resolve_results(run_id=run_id))
    return StreamingResponse(iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_qa_report.xlsx"})


@qb_router.post("/report.xlsx")
def qb_report_xlsx(payload: Dict[str, Any] = Body(default={})):
    data = qa_report.build_xlsx(_resolve_results(payload))
    return StreamingResponse(iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_qa_report.xlsx"})


@qb_router.get("/email-draft")
def qb_email_draft_get(run_id: str = Query(None)):
    return HTMLResponse(content=qa_report.build_email_draft(_resolve_results(run_id=run_id)))


@qb_router.post("/email-draft")
def qb_email_draft(payload: Dict[str, Any] = Body(default={})):
    return HTMLResponse(content=qa_report.build_email_draft(_resolve_results(payload)))


# ── URL 추가/삭제 ──
def _sitecode_from_url(url: str) -> str:
    import re
    if "samsung.com.cn" in (url or ""):
        return "cn"
    m = re.search(r"samsung\.com/([^/]+)/", url or "")
    return m.group(1) if m else (url or "").strip("/").split("/")[-1]


@qb_router.post("/sites/add")
def qb_sites_add(payload: Dict[str, Any] = Body(...)):
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "url이 필요합니다.")
    sc = payload.get("sitecode") or _sitecode_from_url(url)
    if _registry.get(sc):
        _registry.update(sc, url=url)
    else:
        _registry.add(sc, url, region=payload.get("region", ""), country=payload.get("country", ""),
                      lang=payload.get("lang", ""), product=payload.get("product", "galaxy-s26-ultra"))
    _registry.save()
    return {"ok": True, "sitecode": sc}


@qb_router.post("/sites/remove")
def qb_sites_remove(payload: Dict[str, Any] = Body(...)):
    sc = payload.get("sitecode")
    ok = _registry.remove(sc)
    if ok:
        _registry.save()
    return {"ok": ok}


# ── 핵심 스펙(3축: product/category/value/unit) CRUD ──
_SPEC_PATH = os.path.join(os.path.dirname(__file__), "key_specs.json")


def _load_specs() -> Dict[str, Any]:
    try:
        return json.load(open(_SPEC_PATH, encoding="utf-8"))
    except Exception:
        return {"products": {}}


def _save_specs(data: Dict[str, Any]):
    with open(_SPEC_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _prod_entry(data, product):
    e = data.setdefault("products", {}).setdefault(product, {"label": product, "specs": []})
    if isinstance(e, list):  # 구버전 호환: 리스트면 감싸기
        e = {"label": product, "specs": e}; data["products"][product] = e
    e.setdefault("specs", [])
    return e


@qb_router.get("/specs")
def qb_specs(product: str = Query("galaxy-s26-ultra")):
    data = _load_specs().get("products", {})
    e = data.get(product, {})
    if isinstance(e, list):
        return {"product": product, "label": product, "specs": e}
    return {"product": product, "label": e.get("label", product), "specs": e.get("specs", [])}


@qb_router.post("/specs/add")
def qb_specs_add(payload: Dict[str, Any] = Body(...)):
    product = payload.get("product", "galaxy-s26-ultra")
    # values: 여러 값(국별 variation) 허용 — 콤마/리스트 모두 수용
    raw = payload.get("values", payload.get("value", ""))
    if isinstance(raw, list):
        values = [str(v).strip() for v in raw if str(v).strip()]
    else:
        values = [v.strip() for v in str(raw).split(",") if v.strip()]
    pts = payload.get("page_types") or ["PDP"]
    if isinstance(pts, str):
        pts = [p.strip() for p in pts.split(",") if p.strip()] or ["PDP"]
    row = {"category": payload.get("category", ""), "values": values,
           "unit": payload.get("unit", ""), "page_types": pts}
    if not row["category"] or not values:
        raise HTTPException(400, "category와 value(값)가 필요합니다.")
    data = _load_specs()
    _prod_entry(data, product)["specs"].append(row)
    _save_specs(data)
    return {"ok": True, "specs": data["products"][product]["specs"]}


@qb_router.post("/specs/remove")
def qb_specs_remove(payload: Dict[str, Any] = Body(...)):
    product = payload.get("product", "galaxy-s26-ultra")
    idx = payload.get("index")
    data = _load_specs()
    e = data.get("products", {}).get(product, {})
    arr = e.get("specs", []) if isinstance(e, dict) else e
    if isinstance(idx, int) and 0 <= idx < len(arr):
        arr.pop(idx); _save_specs(data)
        return {"ok": True, "specs": arr}
    return {"ok": False, "specs": arr}


# ── 검수 룰 추가 (카피/스키마 별도) ──
_COPY_PATH = os.path.join(os.path.dirname(__file__), "copy_rules.json")
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema_rules.json")


@qb_router.post("/rules/copy/add")
def qb_rules_copy_add(payload: Dict[str, Any] = Body(...)):
    """스펙 QA 룰 추가: spec_token 또는 proper_noun."""
    product = payload.get("product", "M3")
    kind = payload.get("kind", "spec")  # "spec" | "proper_noun"
    token = (payload.get("token") or "").strip()
    if not token:
        raise HTTPException(400, "token이 필요합니다.")
    data = json.load(open(_COPY_PATH, encoding="utf-8"))
    key = "spec_tokens" if kind == "spec" else "proper_nouns"
    arr = data["products"].setdefault(product, {}).setdefault(key, [])
    if token not in arr:
        arr.append(token)
    json.dump(data, open(_COPY_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, key: arr}


@qb_router.post("/rules/schema/add")
def qb_rules_schema_add(payload: Dict[str, Any] = Body(...)):
    """스키마 QA 룰 추가(페이지타입별): 선택 타입 블록에 속성 + 기대값·값종류 등록. 블록 없으면 생성.
    value_kind: url(가변 치환·정확) / enum(정확) / text(번역=확인만) / exists(존재만)"""
    product = payload.get("product", "M3")
    page_type = payload.get("page_type", "PDP")
    block_type = (payload.get("block_type") or payload.get("block") or "").strip()
    prop = (payload.get("property") or "").strip()
    id_slug = (payload.get("id_slug") or "").strip() or None
    value = (payload.get("value") or "").strip()
    kind = (payload.get("value_kind") or "exists").strip()   # url|enum|text|exists
    nested = (payload.get("nested") or "").strip() or None    # @id|@type|None
    if not block_type or not prop:
        raise HTTPException(400, "block_type과 property가 필요합니다.")
    path = os.path.join(os.path.dirname(__file__), f"schema_rules.{product}.{page_type}.json")
    if os.path.exists(path):
        data = json.load(open(path, encoding="utf-8"))
    else:
        data = {"source": "manual", "sitecode_token": "{SITECODE}", "page_type": page_type, "blocks": []}
    blocks = data.setdefault("blocks", [])
    hit = next((b for b in blocks if b.get("name") == block_type or block_type in (b.get("types") or [])), None)
    if not hit:
        hit = {"name": block_type, "types": [block_type], "id_pattern": None, "id_slug": id_slug,
               "required_properties": [], "optional_properties": [], "property_notes": {},
               "haspart_ids": [], "expected_values": {}, "conditional": None}
        blocks.append(hit)
    if prop not in hit.setdefault("required_properties", []):
        hit["required_properties"].append(prop)
    # 기대값·종류 저장 (exists 는 값 검사 안 함 → expected_values 에 안 넣음)
    if kind != "exists" and value:
        hit.setdefault("expected_values", {})[prop] = {"value": value, "kind": kind, "nested": nested}
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return {"ok": True, "product": product, "page_type": page_type, "block": block_type,
            "required_properties": hit["required_properties"],
            "expected_values": hit.get("expected_values", {})}


# ── URL 엑셀 템플릿 다운로드 / 일괄 업로드 ──
_URL_COLS = ["sitecode", "url", "region", "country", "lang", "product"]


@qb_router.get("/sites/template.xlsx")
def qb_sites_template():
    from openpyxl import Workbook
    import io
    wb = Workbook(); ws = wb.active; ws.title = "URLs"
    ws.append(_URL_COLS)
    ws.append(["sg", "https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/compare/",
               "APAC", "Singapore", "en-SG", "galaxy-s26-ultra"])  # 예시 1행
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=qubi_url_template.xlsx"})


@qb_router.post("/sites/upload")
def qb_sites_upload(payload: Dict[str, Any] = Body(...)):
    """base64 로 받은 xlsx(위 템플릿 형식)를 파싱해 일괄 추가."""
    import base64
    import io
    from openpyxl import load_workbook
    b64 = payload.get("b64") or ""
    if "," in b64:
        b64 = b64.split(",", 1)[1]  # dataURL 접두 제거
    try:
        wb = load_workbook(io.BytesIO(base64.b64decode(b64)), read_only=True, data_only=True)
    except Exception as e:
        raise HTTPException(400, f"엑셀을 읽을 수 없습니다: {e}")
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"ok": True, "added": 0}
    header = [str(c or "").strip().lower() for c in rows[0]]
    idx = {c: header.index(c) for c in _URL_COLS if c in header}
    added = 0
    for r in rows[1:]:
        def g(col):
            i = idx.get(col)
            return (str(r[i]).strip() if i is not None and i < len(r) and r[i] is not None else "")
        url = g("url")
        if not url:
            continue
        sc = g("sitecode") or _sitecode_from_url(url)
        if _registry.get(sc):
            _registry.update(sc, url=url)
        else:
            _registry.add(sc, url, region=g("region"), country=g("country"),
                          lang=g("lang"), product=g("product") or "galaxy-s26-ultra")
        added += 1
    _registry.save()
    return {"ok": True, "added": added, "count": len(_registry.all())}

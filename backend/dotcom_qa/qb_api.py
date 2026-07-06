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
  POST /api/qb/run                   {sitecodes?, product} 크롤 후 검수(주입된 fetcher 필요)
  POST /api/qb/report.xlsx           {results} → Excel 다운로드
  POST /api/qb/email-draft           {results} → 메일 초안 HTML
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))  # 패키지/스크립트 양쪽에서 flat import 허용

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
from site_registry import SiteRegistry

qb_router = APIRouter(prefix="/api/qb", tags=["qubi"])
_registry = SiteRegistry()
_fetcher: Optional[Callable[[str], Optional[str]]] = None


def set_fetcher(fn: Callable[[str], Optional[str]]):
    """기존 크롤러의 'url -> html' 함수를 주입."""
    global _fetcher
    _fetcher = fn


def enable_default_crawler(requires_js: bool = False):
    """기존 애플스토커의 HybridCrawler 를 큐비 fetcher 로 자동 연결.
    main.py 에서 `enable_default_crawler()` 한 줄이면 /run 이 동작한다.
    (qb_api 엔드포인트는 동기 def 라 스레드풀에서 실행 → asyncio.run 안전)"""
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
    by = _registry.by_region()
    return {"count": len(_registry.all()),
            "regions": {r: [{"sitecode": s["sitecode"], "country": s["country"],
                             "lang": s["lang"], "url": s["url"]} for s in sites]
                        for r, sites in by.items()},
            "missing_lang": _registry.missing_lang()}


@qb_router.get("/rules")
def qb_rules(product: str = Query("M3")):
    """화면 '?' 기준 패널용 — 규칙을 사람이 읽는 형태로 그대로 반환."""
    rules = runner.load_rules(product)
    schema_blocks = [{
        "block": b["name"], "types": b["types"], "id": b.get("id_slug"),
        "required_properties": b.get("required_properties", []),
        "optional_properties": b.get("optional_properties", []),
        "haspart_ids": b.get("haspart_ids", []),
        "conditional": b.get("conditional"),
    } for b in rules["schema"].get("blocks", [])]
    return {
        "product": product,
        "schema": {
            "설명": "필수 스키마 @type/@id/속성, Product.hasPart @id, 조건부(WARN) 규칙",
            "blocks": schema_blocks,
        },
        "copy": {
            "설명": "번역 불변 값만 검사 — 스펙 토큰(숫자+단위)은 정확 일치, 고유명사는 존재(WARN)",
            "spec_tokens": rules["copy"].get("spec_tokens", []),
            "proper_nouns": rules["copy"].get("proper_nouns", []),
        },
    }


@qb_router.post("/check")
def qb_check(payload: Dict[str, Any] = Body(...)):
    html = payload.get("html")
    product = payload.get("product", "M3")
    if not html:
        raise HTTPException(400, "html 필드가 필요합니다.")
    rules = runner.load_rules(product)
    # 붙여넣기 검수: sitecode/lang 주면 값 치환 정확검사, 없으면 그 자리만 와일드카드
    return runner.check_html(html, rules,
                             sitecode=payload.get("sitecode"), site_lang=payload.get("lang"))


@qb_router.post("/run")
def qb_run(payload: Dict[str, Any] = Body(default={})):
    if _fetcher is None:
        raise HTTPException(501, "크롤러(fetcher)가 연결되지 않았습니다. set_fetcher()로 주입하세요.")
    product = payload.get("product", "M3")
    sitecodes = payload.get("sitecodes")
    results = runner.run_all(_fetcher, product=product, sitecodes=sitecodes, registry=_registry)
    return {"summary": qa_report.summary_counts(results), "results": results}


@qb_router.post("/report.xlsx")
def qb_report_xlsx(payload: Dict[str, Any] = Body(...)):
    results = payload.get("results") or []
    data = qa_report.build_xlsx(results)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_qa_report.xlsx"})


@qb_router.post("/email-draft")
def qb_email_draft(payload: Dict[str, Any] = Body(...)):
    results = payload.get("results") or []
    return HTMLResponse(content=qa_report.build_email_draft(results))


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


@qb_router.get("/specs")
def qb_specs(product: str = Query("galaxy-s26-ultra")):
    return {"product": product, "specs": _load_specs().get("products", {}).get(product, [])}


@qb_router.post("/specs/add")
def qb_specs_add(payload: Dict[str, Any] = Body(...)):
    product = payload.get("product", "galaxy-s26-ultra")
    row = {"category": payload.get("category", ""), "value": str(payload.get("value", "")),
           "unit": payload.get("unit", "")}
    if not row["category"] or not row["value"]:
        raise HTTPException(400, "category와 value가 필요합니다.")
    data = _load_specs()
    data.setdefault("products", {}).setdefault(product, []).append(row)
    _save_specs(data)
    return {"ok": True, "specs": data["products"][product]}


@qb_router.post("/specs/remove")
def qb_specs_remove(payload: Dict[str, Any] = Body(...)):
    product = payload.get("product", "galaxy-s26-ultra")
    idx = payload.get("index")
    data = _load_specs()
    arr = data.get("products", {}).get(product, [])
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
    """스키마 QA 룰 추가: 특정 블록에 필수 속성 추가."""
    product = payload.get("product", "M3")
    block = payload.get("block", "")
    prop = (payload.get("property") or "").strip()
    if not block or not prop:
        raise HTTPException(400, "block과 property가 필요합니다.")
    per = os.path.join(os.path.dirname(__file__), f"schema_rules.{product}.json")
    if os.path.exists(per):  # 제품별 분리 파일
        data = json.load(open(per, encoding="utf-8"))
        blocks = data.get("blocks", [])
        hit = next((b for b in blocks if b.get("name") == block), None)
        if not hit:
            raise HTTPException(404, f"블록 '{block}' 없음")
        if prop not in hit.setdefault("required_properties", []):
            hit["required_properties"].append(prop)
        json.dump(data, open(per, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        return {"ok": True, "block": block, "required_properties": hit["required_properties"]}
    # 통합 파일 폴백
    data = json.load(open(_SCHEMA_PATH, encoding="utf-8"))
    blocks = data["products"].get(product, {}).get("blocks", [])
    hit = next((b for b in blocks if b.get("name") == block), None)
    if not hit:
        raise HTTPException(404, f"블록 '{block}' 없음")
    if prop not in hit.setdefault("required_properties", []):
        hit["required_properties"].append(prop)
    json.dump(data, open(_SCHEMA_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "block": block, "required_properties": hit["required_properties"]}


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

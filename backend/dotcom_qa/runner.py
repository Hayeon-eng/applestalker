"""
runner.py — 큐비 — Dotcom QA 체커 [오케스트레이터 / Phase E 어댑터]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

레지스트리의 URL들에 대해:
  fetch_html(url) → HTML 수집  (기존 백엔드 크롤러를 여기에 주입)
  → schema_checker + copy_checker 검수
  → page_results 리스트로 집계 (qa_report 로 Excel/메일 생성 가능)

* 이 샌드박스는 samsung.com 에 접근할 수 없으므로 실제 수집은 기존 크롤러가 담당한다.
  fetch_html 을 주입만 하면 91개 사이트를 순회 검수할 수 있다(네트워크는 호출측 책임).
"""
from __future__ import annotations
import json
import os
from typing import Any, Callable, Dict, List, Optional

import schema_checker
import copy_checker
from site_registry import SiteRegistry

_HERE = os.path.dirname(__file__)


def page_type_from_url(url: str) -> str:
    u = (url or "").lower()
    if "/compare" in u:
        return "Compare"
    if "/buy" in u:
        return "Buying"
    return "PDP"


def product_from_url(url: str) -> Optional[str]:
    """URL 경로에서 마케팅 제품 판별."""
    u = (url or "").lower()
    if "galaxy-s26-ultra" in u:
        return "galaxy-s26-ultra"
    if "galaxy-s26-plus" in u or "galaxy-s26+" in u:
        return "galaxy-s26-plus"
    if "galaxy-s26" in u:
        return "galaxy-s26"
    if "galaxy-buds4-pro" in u:
        return "galaxy-buds4-pro"
    if "galaxy-buds4" in u or "galaxy-buds" in u:
        return "galaxy-buds4"
    return None


def is_smartphone(market_product: Optional[str], url: str = "") -> bool:
    """스마트폰(=Flagship PD 세트) 여부. galaxy-s26* 계열이면 True.
    판별 불가한 신규/공통 페이지는 안전하게 False(→ Simple 세트)로 폴백."""
    mp = (market_product or "").lower()
    u = (url or "").lower()
    if mp.startswith("galaxy-s") and "buds" not in mp:
        return True
    if "/smartphones/" in u and "buds" not in u:
        return True
    return False


def schema_set_for(page_type: str, market_product: Optional[str], url: str = "") -> Optional[str]:
    """페이지타입+제품군 → Word 스키마 세트 파일 접두어.
    - PDP + 스마트폰  → flagship
    - PDP + 그 외     → simple  (버즈·노트북·태블릿, 판별불가 공통페이지 포함)
    - Compare         → compare
    - Buying          → None (스키마 검사 제외)
    """
    if page_type == "Buying":
        return None
    if page_type == "Compare":
        return "compare"
    return "flagship" if is_smartphone(market_product, url) else "simple"


def load_rules(product: str = "M3", page_type: str = "PDP", market_product: str = None,
               url: str = "", schema_path: str = None, copy_path: str = None, spec_path: str = None) -> Dict[str, Any]:
    copy_path = copy_path or os.path.join(_HERE, "copy_rules.json")
    spec_path = spec_path or os.path.join(_HERE, "key_specs.json")

    # ── 스키마 규칙: Word(PTK) 세트로 재구성 — flagship/simple/compare, Buying 제외 ──
    schema_set = schema_set_for(page_type, market_product, url)
    if schema_set is None:
        sr = {"page_type": page_type, "set": None, "blocks": [], "skip": True}  # Buying: 스키마 검사 제외
    else:
        # 세트 파일: schema_rules.{set}.{PDP|Compare}.json
        set_page = "Compare" if schema_set == "compare" else "PDP"
        set_file = os.path.join(_HERE, f"schema_rules.{schema_set}.{set_page}.json")
        if os.path.exists(set_file):
            sr = json.load(open(set_file, encoding="utf-8"))
        else:
            # 폴백: 구 파일(있으면) → 빈 룰
            legacy = os.path.join(_HERE, f"schema_rules.{product}.{page_type}.json")
            sr = json.load(open(legacy, encoding="utf-8")) if os.path.exists(legacy) else {"page_type": page_type, "blocks": []}

    # 카피(스펙) 규칙: 마케팅 제품별 토큰 우선, 없으면 패밀리 폴백
    cdata = json.load(open(copy_path, encoding="utf-8"))["products"]
    cr = cdata.get(market_product) if market_product else None
    if not cr:
        cr = cdata.get(product, {})
    try:
        specs_all = json.load(open(spec_path, encoding="utf-8")).get("products", {})
    except Exception:
        specs_all = {}
    mp = market_product or ("galaxy-s26-ultra" if product == "M3" else product)
    entry = specs_all.get(mp) or specs_all.get("galaxy-s26-ultra") or {}
    ks = entry.get("specs", []) if isinstance(entry, dict) else (entry or [])
    label = entry.get("label", mp) if isinstance(entry, dict) else mp
    return {"schema": sr, "copy": cr, "key_specs": ks, "product_label": label,
            "page_type": page_type, "schema_set": schema_set}


def check_html(html: str, rules: Dict[str, Any],
               sitecode: str = None, site_lang: str = None) -> Dict[str, Any]:
    """단일 페이지 HTML 검수 → {schema, copy}."""
    pt = rules.get("page_type", "PDP")
    return {
        "schema": schema_checker.check_page(html, rules["schema"],
                                            sitecode=sitecode, site_lang=site_lang),
        "copy": copy_checker.check_copy(html, rules["copy"], key_specs=rules.get("key_specs"), page_type=pt),
    }


def run_site(site: Dict[str, Any], html: str, rules: Dict[str, Any], page_type: str = "PDP") -> Dict[str, Any]:
    res = check_html(html, rules, sitecode=site.get("sitecode"), site_lang=site.get("lang"))
    return {"sitecode": site.get("sitecode"), "url": site.get("url"),
            "region": site.get("region"), "country": site.get("country"),
            "product": site.get("product", "galaxy-s26-ultra"), "lang": site.get("lang"),
            "page_type": page_type, "schema": res["schema"], "copy": res["copy"]}


def run_all(fetch_html: Callable[[str], Optional[str]],
            product: str = "M3",
            sitecodes: Optional[List[str]] = None,
            registry: Optional[SiteRegistry] = None) -> List[Dict[str, Any]]:
    """레지스트리 순회 검수. fetch_html(url)->html|None 을 주입.
    sitecodes 를 주면 해당 사이트만 검수. 페이지타입은 URL 로 자동판별해 해당 룰 적용."""
    registry = registry or SiteRegistry()
    rules_cache: Dict[str, Dict[str, Any]] = {}

    def rules_for(pt: str, mp: str, url: str = "") -> Dict[str, Any]:
        sset = schema_set_for(pt, mp, url)
        key = f"{pt}|{mp}|{sset}"
        if key not in rules_cache:
            rules_cache[key] = load_rules(product, page_type=pt, market_product=mp, url=url)
        return rules_cache[key]

    targets = registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        targets = [t for t in targets if t["sitecode"] in want]
    results = []
    for site in targets:
        url = site.get("url", "")
        pt = site.get("page_type") or page_type_from_url(url)
        mp = product_from_url(url)
        try:
            html = fetch_html(site["url"])
        except Exception:
            html = None
        if not html:
            results.append({"sitecode": site["sitecode"], "url": site["url"],
                            "region": site.get("region"), "country": site.get("country"),
                            "page_type": pt,
                            "schema": {"summary": {}, "findings": [
                                {"block": "(수집 실패)", "status": "fail",
                                 "as_is": "HTML 수집 실패", "to_be": "URL 접근/렌더링 확인"}]},
                            "copy": {"summary": {}, "findings": []}})
            continue
        results.append(run_site(site, html, rules_for(pt, mp, url), page_type=pt))
    return results


if __name__ == "__main__":
    # 데모: 로컬 index.html 을 fetch_html 로 반환하도록 주입 (네트워크 없이 검증)
    local = open("/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()

    def fake_fetch(url):
        return local if url.endswith("/uk/smartphones/galaxy-s26-ultra/") else None

    res = run_all(fake_fetch, sitecodes=["uk", "de"])
    for r in res:
        sf = r["schema"]["summary"]; cf = r["copy"]["summary"]
        print(f"{r['sitecode']:4s} schema {sf.get('fail','?')}fail/{sf.get('warn','?')}warn · "
              f"copy {cf.get('fail','?')}fail/{cf.get('warn','?')}warn")

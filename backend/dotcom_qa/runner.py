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


def load_rules(product: str = "M3", page_type: str = "PDP",
               schema_path: str = None, copy_path: str = None, spec_path: str = None) -> Dict[str, Any]:
    schema_path = schema_path or os.path.join(_HERE, "schema_rules.json")
    copy_path = copy_path or os.path.join(_HERE, "copy_rules.json")
    spec_path = spec_path or os.path.join(_HERE, "key_specs.json")
    # 스키마 규칙: 제품×페이지타입 파일 → 제품별 파일 → 통합 파일 순으로 폴백
    by_page = os.path.join(_HERE, f"schema_rules.{product}.{page_type}.json")
    per_product = os.path.join(_HERE, f"schema_rules.{product}.json")
    if os.path.exists(by_page):
        sr = json.load(open(by_page, encoding="utf-8"))
    elif os.path.exists(per_product):
        sr = json.load(open(per_product, encoding="utf-8"))
    else:
        sr = json.load(open(schema_path, encoding="utf-8"))["products"].get(product, {})
    cr = json.load(open(copy_path, encoding="utf-8"))["products"].get(product, {})
    try:
        specs_all = json.load(open(spec_path, encoding="utf-8")).get("products", {})
    except Exception:
        specs_all = {}
    ks = specs_all.get("galaxy-s26-ultra", []) if product in ("M3",) else specs_all.get(product, [])
    return {"schema": sr, "copy": cr, "key_specs": ks}


def check_html(html: str, rules: Dict[str, Any],
               sitecode: str = None, site_lang: str = None) -> Dict[str, Any]:
    """단일 페이지 HTML 검수 → {schema, copy}."""
    return {
        "schema": schema_checker.check_page(html, rules["schema"],
                                            sitecode=sitecode, site_lang=site_lang),
        "copy": copy_checker.check_copy(html, rules["copy"], key_specs=rules.get("key_specs")),
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

    def rules_for(pt: str) -> Dict[str, Any]:
        if pt not in rules_cache:
            rules_cache[pt] = load_rules(product, page_type=pt)
        return rules_cache[pt]

    targets = registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        targets = [t for t in targets if t["sitecode"] in want]
    results = []
    for site in targets:
        pt = site.get("page_type") or page_type_from_url(site.get("url", ""))
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
        results.append(run_site(site, html, rules_for(pt), page_type=pt))
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

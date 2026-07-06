"""
runner.py — 큐비(QB) — Dotcom QA 체커 [오케스트레이터 / Phase E 어댑터]

큐비 🐝 — QA의 사촌 QB. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

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


def load_rules(product: str = "M3",
               schema_path: str = None, copy_path: str = None) -> Dict[str, Any]:
    schema_path = schema_path or os.path.join(_HERE, "schema_rules.json")
    copy_path = copy_path or os.path.join(_HERE, "copy_rules.json")
    sr = json.load(open(schema_path, encoding="utf-8"))["products"].get(product, {})
    cr = json.load(open(copy_path, encoding="utf-8"))["products"].get(product, {})
    return {"schema": sr, "copy": cr}


def check_html(html: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    """단일 페이지 HTML 검수 → {schema, copy}."""
    return {
        "schema": schema_checker.check_page(html, rules["schema"]),
        "copy": copy_checker.check_copy(html, rules["copy"]),
    }


def run_site(site: Dict[str, Any], html: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    res = check_html(html, rules)
    return {"sitecode": site.get("sitecode"), "url": site.get("url"),
            "region": site.get("region"), "country": site.get("country"),
            "schema": res["schema"], "copy": res["copy"]}


def run_all(fetch_html: Callable[[str], Optional[str]],
            product: str = "M3",
            sitecodes: Optional[List[str]] = None,
            registry: Optional[SiteRegistry] = None) -> List[Dict[str, Any]]:
    """레지스트리 순회 검수. fetch_html(url)->html|None 을 주입.
    sitecodes 를 주면 해당 사이트만 검수."""
    registry = registry or SiteRegistry()
    rules = load_rules(product)
    targets = registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        targets = [t for t in targets if t["sitecode"] in want]
    results = []
    for site in targets:
        try:
            html = fetch_html(site["url"])
        except Exception as e:
            html = None
        if not html:
            results.append({"sitecode": site["sitecode"], "url": site["url"],
                            "region": site.get("region"), "country": site.get("country"),
                            "schema": {"summary": {}, "findings": [
                                {"block": "(수집 실패)", "status": "fail",
                                 "as_is": "HTML 수집 실패", "to_be": "URL 접근/렌더링 확인"}]},
                            "copy": {"summary": {}, "findings": []}})
            continue
        results.append(run_site(site, html, rules))
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

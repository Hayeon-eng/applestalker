"""
site_registry.py — 큐비(QB) — Dotcom QA 체커 [Phase D]

큐비 🐝 — QA의 사촌 QB. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

91개 삼성닷컴 사이트 레지스트리(site_registry.json)를 로드/조회/관리한다.
각 항목: {sitecode, url, region, country, lang, product}

- URL 목록은 제공받은 앵커 URL에서 생성(사이트코드 = URL 경로 세그먼트, samsung.com.cn=cn).
- region/country 는 기획 문서(S16)에서, lang(BCP-47)은 inLanguage 시트에서 병합.
- 실제 크롤링은 기존 백엔드 크롤러가 이 URL들을 받아 HTML 을 수집 → 체커(schema/copy)에 전달.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

_DEFAULT = os.path.join(os.path.dirname(__file__), "site_registry.json")


class SiteRegistry:
    def __init__(self, path: str = _DEFAULT):
        self.path = path
        with open(path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.sites: List[Dict[str, Any]] = self.data.get("sites", [])

    # ── 조회 ──
    def all(self) -> List[Dict[str, Any]]:
        return list(self.sites)

    def get(self, sitecode: str) -> Optional[Dict[str, Any]]:
        sc = (sitecode or "").lower()
        return next((s for s in self.sites if s["sitecode"] == sc), None)

    def by_region(self) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for s in self.sites:
            out.setdefault(s.get("region") or "(미분류)", []).append(s)
        return out

    def urls(self) -> List[str]:
        return [s["url"] for s in self.sites]

    def missing_lang(self) -> List[str]:
        return [s["sitecode"] for s in self.sites if not s.get("lang")]

    # ── 관리(추가/삭제/수정) — 저장은 명시 호출로 ──
    def add(self, sitecode: str, url: str, region: str = "", country: str = "",
            lang: str = "", product: str = "galaxy-s26-ultra") -> Dict[str, Any]:
        sc = sitecode.lower()
        if self.get(sc):
            raise ValueError(f"이미 존재하는 사이트코드: {sc}")
        row = {"sitecode": sc, "url": url, "region": region, "country": country,
               "lang": lang, "product": product}
        self.sites.append(row)
        return row

    def remove(self, sitecode: str) -> bool:
        sc = sitecode.lower()
        before = len(self.sites)
        self.sites = [s for s in self.sites if s["sitecode"] != sc]
        return len(self.sites) < before

    def update(self, sitecode: str, **fields) -> Optional[Dict[str, Any]]:
        row = self.get(sitecode)
        if row:
            row.update({k: v for k, v in fields.items() if k in row})
        return row

    def save(self, path: Optional[str] = None):
        self.data["sites"] = self.sites
        self.data["count"] = len(self.sites)
        with open(path or self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    r = SiteRegistry()
    print(f"레지스트리 {len(r.all())}개 사이트")
    by = r.by_region()
    for region, sites in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"  {region}: {len(sites)}개  ({', '.join(s['sitecode'] for s in sites[:6])}{' …' if len(sites) > 6 else ''})")
    ml = r.missing_lang()
    if ml:
        print("언어코드 미지정(사람이 채울 것):", ml)

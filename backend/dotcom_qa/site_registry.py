"""
site_registry.py — 큐비 — Dotcom QA 체커 [Phase D]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

91개 삼성닷컴 사이트 레지스트리(site_registry.json)를 로드/조회/관리한다.
각 항목: {sitecode, url, region, country, lang, product}

- URL 목록은 제공받은 앵커 URL에서 생성(사이트코드 = URL 경로 세그먼트, samsung.com.cn=cn).
- region/country 는 기획 문서(S16)에서, lang(BCP-47)은 inLanguage 시트에서 병합.
- 실제 크롤링은 기존 백엔드 크롤러가 이 URL들을 받아 HTML 을 수집 → 체커(schema/copy)에 전달.
"""
from __future__ import annotations
import glob
import json
import os
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(__file__)
_DEFAULT = os.path.join(_HERE, "site_registry.json")


def _load_sites(path: str) -> Dict[str, Any]:
    """단일 site_registry.json 이 있으면 그걸, 없으면 site_registry.part*.json 을
    번호 순서로 병합해서 로드한다(대용량이라 4분할로 배포하는 경우 대응)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    parts = sorted(glob.glob(os.path.join(_HERE, "site_registry.part*.json")))
    if parts:
        merged: List[Dict[str, Any]] = []
        base: Dict[str, Any] = {}
        for p in parts:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            base = base or {k: v for k, v in d.items() if k != "sites"}
            merged.extend(d.get("sites", []))
        base["sites"] = merged
        base["count"] = len(merged)
        return base
    raise FileNotFoundError(f"site_registry.json 또는 site_registry.part*.json 을 찾을 수 없습니다: {_HERE}")


class SiteRegistry:
    def __init__(self, path: str = _DEFAULT):
        self.path = path
        self.data = _load_sites(path)
        self.sites: List[Dict[str, Any]] = self.data.get("sites", [])

    # ── 조회 ──
    def all(self) -> List[Dict[str, Any]]:
        return list(self.sites)

    def get(self, sitecode: str) -> Optional[Dict[str, Any]]:
        """sitecode 로 첫 엔트리(메타데이터 조회용). 이제 한 sitecode 에 여러 URL이
        있으므로 region/country/lang 같은 공통 메타 조회 용도로만 쓴다."""
        sc = (sitecode or "").lower()
        return next((s for s in self.sites if s["sitecode"] == sc), None)

    def for_sitecode(self, sitecode: str) -> List[Dict[str, Any]]:
        """해당 사이트코드의 모든 검수 대상(제품×페이지타입) 엔트리."""
        sc = (sitecode or "").lower()
        return [s for s in self.sites if s["sitecode"] == sc]

    def unique_sitecodes(self) -> List[str]:
        seen, out = set(), []
        for s in self.sites:
            if s["sitecode"] not in seen:
                seen.add(s["sitecode"]); out.append(s["sitecode"])
        return out

    def by_region(self) -> Dict[str, List[Dict[str, Any]]]:
        """지역→엔트리 전체(크롤 대상). 그대로 두면 사이트당 여러 엔트리가 포함된다."""
        out: Dict[str, List[Dict[str, Any]]] = {}
        for s in self.sites:
            out.setdefault(s.get("region") or "(미분류)", []).append(s)
        return out

    def by_region_unique(self) -> Dict[str, List[Dict[str, Any]]]:
        """지역→사이트(사이트코드 중복 제거) — 화면 지역 칩/목록용.
        칩에는 로케일이 1개씩만 보이고, 실제 크롤은 all()의 전체 엔트리로 수행."""
        out: Dict[str, List[Dict[str, Any]]] = {}
        seen: set = set()
        for s in self.sites:
            if s["sitecode"] in seen:
                continue
            seen.add(s["sitecode"])
            out.setdefault(s.get("region") or "(미분류)", []).append(s)
        return out

    def urls(self) -> List[str]:
        return [s["url"] for s in self.sites]

    def missing_lang(self) -> List[str]:
        return [s["sitecode"] for s in self.sites if not s.get("lang")]

    # ── 관리(추가/삭제/수정) — 저장은 명시 호출로 ──
    def add(self, sitecode: str, url: str, region: str = "", country: str = "",
            lang: str = "", product: str = "galaxy-s26-ultra", page_type: str = "PDP") -> Dict[str, Any]:
        sc = sitecode.lower()
        # 이제 한 사이트에 여러 URL 허용 → (sitecode,url) 조합으로 중복만 막는다
        if any(s["sitecode"] == sc and s.get("url") == url for s in self.sites):
            raise ValueError(f"이미 존재하는 URL: {sc} / {url}")
        row = {"sitecode": sc, "url": url, "region": region, "country": country,
               "lang": lang, "product": product, "page_type": page_type}
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

"""
discovery.py — Apple Stalker · 최신 제품 URL 자동 탐색 [2026-09 신규]

배경
  경쟁사 URL(config.SEED_TARGETS)은 코드에 고정되어 있어 신모델(iPhone 18 Pro, Apple Watch 신형, AirPods 신형 …)이
  나오면 사람이 코드를 고쳐야 했다. 여기서는 사이트맵과 URL 패턴으로 후보를 찾고 **실제 응답(HTTP 200)으로 존재를 확인한 뒤**
  등록한다 — 확인되지 않은 URL 은 절대 등록하지 않는다(추정 금지).

방식
  1) 사이트맵: https://www.apple.com/sitemap.xml (sitemapindex → 하위 sitemap) 에서 loc 을 모아
     카테고리 패턴(iphone-<n>[-pro|-pro-max|-air|-fold…], apple-watch-*, airpods*, ipad*, macbook*)에 맞는 경로를 추림
  2) 패턴 프로브: 사이트맵이 막히거나 비어 있으면 세대 번호를 현재 시드(17)에서 +1, +2 로 올려 HEAD 요청으로 존재 확인
     (예: /iphone-18-pro/, /shop/buy-iphone/iphone-18-pro)
  3) 세대 정렬: 경로의 숫자를 뽑아 가장 큰 세대를 "최신"으로 선택. 같은 계열의 기존 시드보다 세대가 높을 때만 후보로 제시
  4) 결과는 {url, status: 200|4xx, category, generation, verified: bool, source: sitemap|probe} — verified 만 등록 가능

한계(정직하게)
  · Apple 의 신제품 슬러그 관행(iphone-<n>-pro)이 유지된다는 전제. 새 제품군(예: 폴더블)의 슬러그는 알 수 없어
    후보 키워드 목록(FOLD_KEYWORDS)으로만 프로브한다 — 존재하면 잡히고, 아니면 "미확인"으로 남는다.
  · 이 모듈은 URL 존재만 확인한다. 페이지 역할(PF/PDP/Buying) 판정은 기존 config.page_role_for_url 이 한다.
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 15.0

# 카테고리별 (마케팅 페이지 패턴, 구매 페이지 패턴). {n} = 세대 번호
APPLE_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "iphone": {"pdp": ["/iphone-{n}-pro/", "/iphone-{n}-pro-max/", "/iphone-{n}/", "/iphone-{n}-air/", "/iphone-{n}e/"],
               "buy": ["/shop/buy-iphone/iphone-{n}-pro", "/shop/buy-iphone/iphone-{n}"]},
    "watch": {"pdp": ["/apple-watch-ultra-{n}/", "/apple-watch-series-{n}/", "/apple-watch-se/"],
              "buy": ["/shop/buy-watch/apple-watch-ultra", "/shop/buy-watch/apple-watch"]},
    "airpods": {"pdp": ["/airpods-pro/", "/airpods-{n}/", "/airpods-max/"],
                "buy": ["/shop/buy-airpods/airpods-pro-{n}", "/shop/buy-airpods/airpods-{n}"]},
    "ipad": {"pdp": ["/ipad-pro/", "/ipad-air/", "/ipad/"], "buy": ["/shop/buy-ipad/ipad-pro", "/shop/buy-ipad/ipad-air"]},
    "mac": {"pdp": ["/macbook-pro/", "/macbook-air/"], "buy": ["/shop/buy-mac/macbook-pro", "/shop/buy-mac/macbook-air"]},
}
# 새 제품군 후보 슬러그 — 존재가 확인되지 않은 '가설' 목록. 사용자가 추가 가능. 확인 전에는 등록되지 않는다.
FOLD_KEYWORDS = ["iphone-fold", "iphone-ultra", "iphone-duo", "iphone-flip"]
SITEMAP_HINTS = re.compile(r"/(iphone[-\w]*|apple-watch[-\w]*|airpods[-\w]*|ipad[-\w]*|macbook[-\w]*|shop/buy-(iphone|watch|airpods|ipad|mac)/[-\w]+)/?$", re.I)


def _gen(path: str) -> Optional[int]:
    m = re.search(r"-(\d{1,2})(?:[-/]|$)", path)
    return int(m.group(1)) if m else None


def _head(client: httpx.Client, url: str) -> int:
    try:
        r = client.head(url, follow_redirects=True)
        if r.status_code == 405:
            r = client.get(url, follow_redirects=True)
        # 리다이렉트로 다른 경로에 도착하면 그 URL 은 '없는 것'으로 본다(예: /iphone-19-pro/ → /iphone/)
        if str(r.url).rstrip("/") != url.rstrip("/"):
            return 404
        return r.status_code
    except Exception:
        return 0


def sitemap_paths(client: httpx.Client, root: str = "https://www.apple.com/sitemap.xml", max_children: int = 6) -> List[str]:
    """sitemapindex → 하위 sitemap(미국 영문만) → loc 경로 목록. 실패하면 []."""
    out: List[str] = []
    try:
        r = client.get(root, follow_redirects=True)
        r.raise_for_status()
        tree = ET.fromstring(r.content)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        children = [e.text for e in tree.findall(".//s:sitemap/s:loc", ns) if e.text]
        if not children:  # 단일 urlset
            children = [root]
        # 미국/영문 사이트맵 우선(로케일 경로가 없는 것)
        children = [c for c in children if not re.search(r"apple\.com/[a-z]{2}(-[a-z]{2})?/", c)] or children
        for c in children[:max_children]:
            try:
                rr = client.get(c, follow_redirects=True)
                t = ET.fromstring(rr.content)
                for loc in t.findall(".//s:url/s:loc", ns):
                    u = (loc.text or "").strip()
                    if u.startswith("https://www.apple.com/") and SITEMAP_HINTS.search(u.replace("https://www.apple.com", "")):
                        out.append(u)
            except Exception:
                continue
    except Exception:
        return []
    return sorted(set(out))


def discover_apple(current_seeds: List[str], extra_keywords: Optional[List[str]] = None, verify: bool = True) -> Dict[str, Any]:
    """현재 시드보다 새로운 세대의 Apple 제품 페이지 후보를 찾아 존재를 확인한다."""
    seeds = set(u.rstrip("/") for u in current_seeds)
    seed_gen: Dict[str, int] = {}
    for u in current_seeds:
        for cat in APPLE_PATTERNS:
            if f"/{cat}" in u or (cat == "watch" and "apple-watch" in u) or (cat == "mac" and "macbook" in u):
                g = _gen(u)
                if g:
                    seed_gen[cat] = max(seed_gen.get(cat, 0), g)
    results: List[Dict[str, Any]] = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=TIMEOUT) as client:
        # ① 사이트맵
        sm = sitemap_paths(client)
        for u in sm:
            path = u.replace("https://www.apple.com", "")
            cat = next((c for c in APPLE_PATTERNS if c in path or (c == "watch" and "apple-watch" in path) or (c == "mac" and "macbook" in path)), None)
            if not cat:
                continue
            g = _gen(path)
            if u.rstrip("/") in seeds:
                continue
            if g and g <= seed_gen.get(cat, 0) and cat in ("iphone", "watch"):
                continue  # 기존 세대 이하는 제외(iPhone/Watch 는 세대 번호가 슬러그에 있음)
            results.append({"url": u, "category": cat, "generation": g, "source": "sitemap", "verified": None, "status": None})
        # ② 패턴 프로브 — 시드 세대 +1, +2
        for cat, pats in APPLE_PATTERNS.items():
            base_g = seed_gen.get(cat)
            gens = [base_g + 1, base_g + 2] if base_g else []
            for kind, plist in pats.items():
                for p in plist:
                    if "{n}" in p:
                        for g in gens:
                            u = "https://www.apple.com" + p.format(n=g)
                            if u.rstrip("/") not in seeds and not any(r["url"].rstrip("/") == u.rstrip("/") for r in results):
                                results.append({"url": u, "category": cat, "generation": g, "source": "probe", "kind": kind, "verified": None, "status": None})
        for kw in (extra_keywords or []) + FOLD_KEYWORDS:
            u = f"https://www.apple.com/{kw.strip('/')}/"
            if not any(r["url"].rstrip("/") == u.rstrip("/") for r in results):
                results.append({"url": u, "category": "iphone", "generation": None, "source": "probe", "kind": "pdp", "verified": None, "status": None,
                                "note": "새 제품군 가설 슬러그 — 존재 확인 전"})
        # ③ 존재 확인
        if verify:
            for r in results:
                st = _head(client, r["url"])
                r["status"] = st
                r["verified"] = (st == 200)
    verified = [r for r in results if r["verified"]]
    return {"seed_generation": seed_gen, "candidates": results, "verified": verified,
            "note": "verified=true 인 URL 만 등록하세요. 프로브 후보는 슬러그 관행 가설이며 404/리다이렉트면 존재하지 않는 것입니다."}

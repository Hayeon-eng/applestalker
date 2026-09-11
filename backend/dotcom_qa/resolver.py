"""
resolver.py — 큐비 — 검수 대상 URL 자동 해석 [2026-09 신규]

배경
  레지스트리(site_registry.part*.json 610줄)를 사람이 관리하던 것을, 삼성 검색 API 로 로케일별 실제 URL 을
  해석해 자동 생성한다. 워치처럼 URL 이 국가마다 다른(SKU 슬러그 포함) 제품이 직접적 이유(soft-404 실크롤 확인).
  사람이 정의하는 것은 "제품 × 국가 × 페이지타입"이고, URL·모델코드는 해석 결과물이다.

사용 API (인증 없음, Origin/Referer 만 — sg Compare HAR 로 확인)
  finder  GET searchapi.samsung.com/v6/front/b2c/product/finder/global?siteCode=&type=<카테고리코드>&start=&num=&onlyFilterInfoYN=N
          → resultData.productList[].{fmyMarketingName, modelList[].{modelCode, modelName, displayName, pdpUrl, originPdpUrl, configuratorUrl}}
          (collector gpi-pv 가 91 로케일에서 검증한 엔드포인트. 'global' 실패 시 'newhybris' 폴백)
  spec/ia GET …/mktpd/spec/ia/?siteCode=&categoryCode=SMARTPHONE → modelNameList (비교표가 있는 베이스 모델)

해석 규칙
  · 제품 정의: Rule DB(spec_rules) 의 product / Model Code(SM-F971) / product_aliases → base_model, label, aliases
  · PDP    : finder 모델 중 base_model 로 시작하는 모델의 pdpUrl (플래그십 폰은 패밀리 URL, 워치는 SKU URL 그대로)
  · Buying : 그 모델의 configuratorUrl (없으면 생성 안 함)
  · Compare: 폰만, spec/ia 에 base_model 이 있을 때 {pdpUrl}compare/
  · cn(samsung.com.cn) 은 finder 미지원 → 해석 대상에서 제외(레지스트리/예외 유지)
  · 실패는 unresolved 로 남기고 기존 레지스트리 항목을 폴백으로 유지(site_registry 가 병합)

출력 site_registry.resolved.json
  {generated_at, products[], entries[{sitecode,url,region,country,lang,product,page_type,model_code,model_name,source,resolved_at}],
   unresolved[{sitecode,product,reason}], stats}
"""
from __future__ import annotations
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

_HERE = os.path.dirname(__file__)
RESOLVED_PATH = os.path.join(_HERE, "site_registry.resolved.json")
EXCEPTIONS_PATH = os.path.join(_HERE, "site_registry.exceptions.json")
SITE_BASE = "https://www.samsung.com"
BASE = "https://searchapi.samsung.com/v6/front/b2c/product"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
           "Accept": "application/json, text/plain, */*", "Origin": "https://www.samsung.com", "Referer": "https://www.samsung.com/"}
FINDER_TYPE = {"galaxy-s": "01010000", "galaxy-z": "01010000", "galaxy-watch": "01030000", "galaxy-buds": "01040000", "galaxy-tab": "01020000"}
PHONE_PREFIX = ("galaxy-s", "galaxy-z")
TIMEOUT = float(os.getenv("QB_RESOLVER_TIMEOUT", "20"))
SKIP_SITES = {"cn"}

STATE: Dict[str, Any] = {"running": False, "done": 0, "total": 0, "started": None, "finished": None, "error": None}


# ── 제품 정의 ───────────────────────────────────────────────────────────
def product_defs() -> List[Dict[str, Any]]:
    import spec_rule_db
    import spec_api
    out = []
    for p in spec_rule_db.list_products():
        slug = p["product"]
        rs = spec_rule_db.load(slug) or {}
        base = spec_api.base_model_of(rs)
        ftype = next((v for k, v in FINDER_TYPE.items() if slug.startswith(k)), None)
        if not base or not ftype:
            continue
        out.append({"slug": slug, "base_model": base, "label": (rs.get("product_aliases") or [slug])[0],
                    "aliases": rs.get("product_aliases") or [], "finder_type": ftype,
                    "is_phone": slug.startswith(PHONE_PREFIX),
                    "page_types": ["PDP", "Compare", "Buying"] if slug.startswith(PHONE_PREFIX) else ["PDP"]})
    return out


# ── API ────────────────────────────────────────────────────────────────
def _get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    import httpx
    r = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT, verify=(os.getenv("QB_SSL_VERIFY", "true").lower() != "false"))
    r.raise_for_status()
    return r.json()


def finder_all(sitecode: str, type_code: str, cap: int = 500) -> List[Dict[str, Any]]:
    """카테고리 전체 패밀리(모델 포함). global → newhybris 폴백. 100개씩 페이징."""
    families: List[Dict[str, Any]] = []
    for variant in ("global", "newhybris"):
        try:
            start, total = 0, None
            while True:
                d = _get(f"{BASE}/finder/{variant}", {"siteCode": sitecode, "type": type_code, "start": start, "num": 100, "onlyFilterInfoYN": "N"})
                rd = (d.get("response") or {}).get("resultData") or {}
                fams = rd.get("productList") or []
                families += fams
                total = int(((rd.get("common") or {}).get("totalRecord") or 0))
                start += 100
                if not fams or start >= min(total, cap):
                    break
            return families
        except Exception:
            families = []
            continue
    return families


def ia_models(sitecode: str, category_code: str = "SMARTPHONE") -> List[str]:
    try:
        d = _get(f"{BASE}/mktpd/spec/ia/", {"siteCode": sitecode, "categoryCode": category_code})
        return [m.upper() for m in (((d.get("response") or {}).get("resultData") or {}).get("modelNameList") or [])]
    except Exception:
        return []


# ── 매칭 ───────────────────────────────────────────────────────────────
def _abs(u: Optional[str]) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    u = u if u.startswith("http") else urljoin(SITE_BASE, u)
    u = u.split("?")[0].split("#")[0]
    return u if u.endswith("/") else u + "/"


def pick_model(families: List[Dict[str, Any]], pdef: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """base_model(SM-F971)로 시작하는 모델을 모아 대표 1개. 폰은 패밀리 URL(슬러그에 'sm-' 없음) 우선,
    'Samsung.com only/Online Exclusive' 같은 파생 패밀리는 후순위."""
    base = pdef["base_model"].upper()
    cands = []
    for fam in families:
        fname = str(fam.get("fmyMarketingName") or fam.get("fmyEngName") or "")
        derivative = bool(re.search(r"only|exclusive|re-?newed|refurb|enterprise", fname, re.I))
        for m in fam.get("modelList") or []:
            mn = str(m.get("modelName") or m.get("modelCode") or "").upper()
            if not mn.startswith(base):
                continue
            pdp = m.get("pdpUrl") or m.get("originPdpUrl") or ""
            family_url = "sm-" not in pdp.lower()
            cands.append((derivative, 0 if (pdef["is_phone"] and family_url) else 1, m, fname))
    if not cands:
        return None
    cands.sort(key=lambda t: (t[0], t[1]))
    m = dict(cands[0][2]); m["_family"] = cands[0][3]
    return m


def resolve_site(site: Dict[str, Any], pdefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    sc = site["sitecode"]
    entries, unresolved = [], []
    if sc in SKIP_SITES:
        return {"entries": [], "unresolved": [{"sitecode": sc, "product": p["slug"], "reason": "finder 미지원 도메인(samsung.com.cn) — 예외/레지스트리 유지"} for p in pdefs]}
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for t in {p["finder_type"] for p in pdefs}:
        by_type[t] = finder_all(sc, t)
    ia = ia_models(sc, "SMARTPHONE") if any(p["is_phone"] for p in pdefs) else []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for p in pdefs:
        fams = by_type.get(p["finder_type"]) or []
        if not fams:
            unresolved.append({"sitecode": sc, "product": p["slug"], "reason": "finder 응답 없음/0건(API 접근 불가 또는 카테고리 미판매)"}); continue
        m = pick_model(fams, p)
        if not m:
            unresolved.append({"sitecode": sc, "product": p["slug"], "reason": f"finder 에 {p['base_model']} 모델 없음(미출시/미판매 추정)"}); continue
        meta = {k: site.get(k, "") for k in ("region", "country", "lang")}
        common = {"sitecode": sc, **meta, "product": p["slug"], "model_code": m.get("modelCode"), "model_name": m.get("modelName"),
                  "display_name": m.get("displayName"), "family": m.get("_family"), "source": "finder", "resolved_at": now}
        pdp = _abs(m.get("pdpUrl") or m.get("originPdpUrl"))
        if pdp:
            entries.append({**common, "url": pdp, "page_type": "PDP"})
        if "Buying" in p["page_types"] and m.get("configuratorUrl"):
            entries.append({**common, "url": _abs(m["configuratorUrl"]), "page_type": "Buying"})
        if "Compare" in p["page_types"] and pdp:
            if p["base_model"].upper() in ia:
                entries.append({**common, "url": pdp + "compare/", "page_type": "Compare"})
            else:
                unresolved.append({"sitecode": sc, "product": p["slug"], "reason": "spec/ia 에 비교표 모델 없음 → Compare 생성 안 함"})
    return {"entries": entries, "unresolved": unresolved}


def resolve_all(sites: List[Dict[str, Any]], pdefs: Optional[List[Dict[str, Any]]] = None, workers: int = 6) -> Dict[str, Any]:
    pdefs = pdefs or product_defs()
    # 사이트코드별 대표 메타 1개
    seen: Dict[str, Dict[str, Any]] = {}
    for s in sites:
        seen.setdefault(s["sitecode"], {"sitecode": s["sitecode"], "region": s.get("region", ""), "country": s.get("country", ""), "lang": s.get("lang", "")})
    targets = list(seen.values())
    STATE.update(running=True, done=0, total=len(targets), started=time.time(), finished=None, error=None)
    entries, unresolved = [], []
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(lambda s: resolve_site(s, pdefs), targets):
                entries += r["entries"]; unresolved += r["unresolved"]; STATE["done"] += 1
        out = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "products": [{k: p[k] for k in ("slug", "base_model", "label", "page_types")} for p in pdefs],
               "entries": entries, "unresolved": unresolved,
               "stats": {"sites": len(targets), "entries": len(entries), "unresolved": len(unresolved)}}
        json.dump(out, open(RESOLVED_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return out
    except Exception as e:
        STATE["error"] = str(e)
        raise
    finally:
        STATE.update(running=False, finished=time.time())


def start_background(sites: List[Dict[str, Any]]):
    if STATE.get("running"):
        return False
    threading.Thread(target=lambda: resolve_all(sites), daemon=True).start()
    return True


# ── 예외(수동 등록) ─────────────────────────────────────────────────────
def load_exceptions() -> List[Dict[str, Any]]:
    try:
        return json.load(open(EXCEPTIONS_PATH, encoding="utf-8")).get("entries", [])
    except Exception:
        return []


def save_exceptions(entries: List[Dict[str, Any]]):
    json.dump({"note": "finder 로 해석되지 않는 대상(cn, 캠페인 URL 등)을 사람이 등록. source=exception", "entries": entries},
              open(EXCEPTIONS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load_resolved() -> Optional[Dict[str, Any]]:
    try:
        return json.load(open(RESOLVED_PATH, encoding="utf-8"))
    except Exception:
        return None

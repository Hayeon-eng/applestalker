"""
spec_api.py — 큐비 — Compare 스펙을 삼성 검색 API에서 직접 가져오는 수집 계층 [2026-09 신규]

배경
  Compare 페이지의 비교표는 브라우저가 아래 JSON을 받아 그리는 구조다(sg Compare HAR 로 확인, 2026-09-11).
    GET https://searchapi.samsung.com/v6/front/b2c/product/mktpd/spec/compare/
        ?siteCode={sitecode}&categoryCode={SMARTPHONE|…}&modelList={베이스모델, 예 SM-F971}
    → resultData.modelList[].compareSpec[] (그룹 → childAttr → 리프: attrEngName / attrName(현지어) / attrValue /
      disclaimer)  예) Main Display Dimension 7.6” · Weight 201 · Folded (HxWxD) 123.9 x 81.9 x 9.7 · Peak Brightness 3000 nits
  인증 없음(Origin/Referer 만). 따라서 Compare Spec QA 는 Playwright 렌더 없이 이 JSON 을 CompareQA 매트릭스로 바꿔
  판정한다. 같은 API 군의 mktpd/spec/ia/ 는 그 사이트에서 비교표가 있는 베이스 모델 목록을 준다.

사용
  matrix = compare_matrix_from_api(sitecode, "SM-F971", product_label="Galaxy Z Fold8")
  result = compare_qa.CompareQA().evaluate(matrix, market_product)      # 기존 판정 엔진 그대로

카테고리 코드: 폰은 SMARTPHONE(HAR 확인). 워치는 미확정 → CATEGORY_CANDIDATES 를 순서대로 시도하고
성공한 코드를 런타임 캐시에 기억한다(확정되면 SPEC_API_CATEGORY 에 고정).
"""
from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional

BASE = "https://searchapi.samsung.com/v6/front/b2c/product"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.samsung.com",
    "Referer": "https://www.samsung.com/",
}
SPEC_API_CATEGORY: Dict[str, str] = {          # 제품 슬러그 접두어 → categoryCode (확정된 것만)
    "galaxy-s": "SMARTPHONE", "galaxy-z": "SMARTPHONE",
}
CATEGORY_CANDIDATES: Dict[str, List[str]] = {  # 미확정 계열 — 순서대로 시도
    "galaxy-watch": ["WATCH", "WEARABLE", "SMARTWATCH", "GALAXYWATCH"],
    "galaxy-buds": ["BUDS", "AUDIO", "WEARABLE"],
    "galaxy-tab": ["TABLET"],
}
_LEARNED: Dict[str, str] = {}
TIMEOUT = float(os.getenv("QB_SPEC_API_TIMEOUT", "15"))


def category_for(product_slug: str) -> List[str]:
    for pre, code in SPEC_API_CATEGORY.items():
        if product_slug.startswith(pre):
            return [code]
    for pre, cands in CATEGORY_CANDIDATES.items():
        if product_slug.startswith(pre):
            return ([_LEARNED[pre]] if pre in _LEARNED else []) + [c for c in cands if c != _LEARNED.get(pre)]
    return ["SMARTPHONE"]


def base_model_of(ruleset: Dict[str, Any]) -> Optional[str]:
    """Rule DB 의 'Model Code' 룰(expected 'SM-F971')에서 베이스 모델을 얻는다."""
    for r in ruleset.get("rules", []):
        if re.sub(r"\s+", " ", str(r.get("attribute", ""))).strip().lower() == "model code":
            m = re.search(r"SM-[A-Z]\d{3}", str(r.get("expected", "")).upper())
            if m:
                return m.group(0)
    return None


def _get(url: str, params: Dict[str, str]) -> Dict[str, Any]:
    import httpx
    r = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT, verify=(os.getenv("QB_SSL_VERIFY", "true").lower() != "false"))
    r.raise_for_status()
    return r.json()


def fetch_compare_spec(sitecode: str, base_model: str, category_code: str) -> Dict[str, Any]:
    return _get(f"{BASE}/mktpd/spec/compare/",
                {"siteCode": sitecode, "categoryCode": category_code, "modelList": base_model})


def fetch_ia_models(sitecode: str, category_code: str) -> List[str]:
    d = _get(f"{BASE}/mktpd/spec/ia/", {"siteCode": sitecode, "categoryCode": category_code})
    return list(((d.get("response") or {}).get("resultData") or {}).get("modelNameList") or [])


def _clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def json_to_matrix(payload: Dict[str, Any], product_label: str, base_model: str = "") -> Dict[str, Any]:
    """spec/compare JSON → CompareQA 매트릭스 {"products":[label], "rows":[{category, spec, spec_local, values:[{product,value}]}]}.
    · 그룹(attrLevel 1) 이름 = category. 중간 그룹('Dummy' 제외, 예 'Cover Screen'/'Full Screen')은 spec 앞에 붙여 구분.
    · 값 안의 개행(옵션 나열 '256 GB\\n512 GB\\n1 TB')은 ' / ' 로. '-' 만 있는 값은 미노출로 보고 행에서 제외."""
    rows: List[Dict[str, Any]] = []
    models = ((payload.get("response") or {}).get("resultData") or {}).get("modelList") or []
    target = next((m for m in models if not base_model or (m.get("modelName") or "").upper() == base_model.upper()), models[0] if models else None)
    if not target:
        return {"products": [product_label], "rows": [], "pair_count": 0, "source": "api"}

    def walk(nodes, category: str, path: List[str]):
        for n in nodes or []:
            name_en = _clean(n.get("attrEngName")); name_lo = _clean(n.get("attrName"))
            kids = n.get("childAttr") or []
            if n.get("isLeaf") == "N" or kids:
                cat = category or name_en
                sub = [] if (not category or name_en.lower() == "dummy") else path + [name_en]
                walk(kids, cat, sub)
                continue
            raw = str(n.get("attrValue") or "")
            parts = [p.strip() for p in raw.split("\n") if p.strip() and p.strip() != "-"]
            if not parts:
                continue
            spec = " · ".join(path + [name_en]) if path else name_en
            rows.append({"category": category, "spec": spec, "spec_local": name_lo,
                         "values": [{"product": product_label, "value": " / ".join(parts)}],
                         "disclaimer": _clean(n.get("disclaimer"))[:200] or None})
    walk(target.get("compareSpec") or [], "", [])
    return {"products": [product_label], "rows": rows, "pair_count": len(rows), "source": "api",
            "model_name": target.get("modelName")}


def compare_matrix_from_api(sitecode: str, product_slug: str, ruleset: Dict[str, Any],
                            product_label: Optional[str] = None) -> Dict[str, Any]:
    """Rule DB 의 베이스 모델로 spec/compare 를 호출해 매트릭스를 만든다. 실패는 예외로 올린다(호출측 폴백)."""
    base = base_model_of(ruleset)
    if not base:
        raise ValueError(f"{product_slug}: Rule DB 에 'Model Code' 룰(SM-xxxx)이 없어 API 조회 불가")
    label = product_label or ruleset.get("product") or product_slug
    last: Optional[Exception] = None
    for code in category_for(product_slug):
        try:
            payload = fetch_compare_spec(sitecode, base, code)
            m = json_to_matrix(payload, label, base)
            if m["rows"]:
                pre = next((p for p in CATEGORY_CANDIDATES if product_slug.startswith(p)), None)
                if pre:
                    _LEARNED[pre] = code
                m["category_code"] = code
                return m
            last = ValueError(f"categoryCode={code}: 빈 결과")
        except Exception as e:
            last = e
    raise last or RuntimeError("spec/compare 조회 실패")

"""
product_master.py — 큐비 · 제품 마스터 [2026-11 신규]

제품 하나의 '정체성'을 한 곳에 둔다. 지금까지 표시명은 key_specs/schema_values, 스키마 세트는 슬러그 추정,
고유명사는 copy_rules, 모델 토큰은 schema_values 에 흩어져 있어 신모델마다 세 곳을 고쳐야 했다.
제품 등록 워크북(product_pack_xlsx)의 '제품정보' 시트가 여기로 저장되고, runner 가 우선 참조한다.

{ "galaxy-z-fold9": {"label": "Galaxy Z Fold9", "category": "smartphone", "schema_set": "flagship",
                     "previous_product": "galaxy-z-fold8", "proper_nouns": ["Galaxy AI"], "note": "…",
                     "updated_at": "2026-11-05T…"} }
"""
from __future__ import annotations
import json
import os
import time
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(_HERE, "product_master.json")
CATEGORIES = ["smartphone", "watch", "buds", "tablet", "laptop", "other"]
SCHEMA_SETS = ["flagship", "simple"]
_cache: Optional[Dict[str, Any]] = None


def load() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(PATH, encoding="utf-8")) if os.path.exists(PATH) else {}
        except Exception:
            _cache = {}
    return _cache


def get(product: Optional[str]) -> Dict[str, Any]:
    return dict(load().get(product or "", {}) or {})


def save(product: str, info: Dict[str, Any]) -> Dict[str, Any]:
    global _cache
    data = load()
    row = {k: v for k, v in info.items() if k in ("label", "category", "schema_set", "previous_product", "proper_nouns", "note")}
    row["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data[product] = {**data.get(product, {}), **row}
    json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _cache = data
    return data[product]


def delete(product: str) -> bool:
    global _cache
    data = load()
    if product not in data:
        return False
    data.pop(product)
    json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _cache = data
    return True


def schema_set_override(product: Optional[str]) -> Optional[str]:
    """제품 마스터에 스키마 세트가 등록돼 있으면 슬러그 추정 대신 그 값."""
    ss = get(product).get("schema_set")
    return ss if ss in SCHEMA_SETS else None


def proper_nouns_override(product: Optional[str]) -> Optional[List[str]]:
    pn = get(product).get("proper_nouns")
    return list(pn) if isinstance(pn, list) and pn else None

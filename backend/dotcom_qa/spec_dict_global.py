"""
spec_dict_global.py — 큐비 — Spec QA 전체-제품 공통(Global) Dictionary

배경: 실제 데이터로 확인한 결과, fold7↔flip7(폰) 대표 표현 23개가 100% 겹치고
(각 637개 alias), buds4↔buds4-pro 15개도 100% 겹칩니다 — 세대가 바뀌어도 번역
자체는 거의 그대로 재사용 가능하다는 뜻입니다. 신모델(watch9, foldN+1 등)이 나올
때마다 이 번역 자산을 처음부터 다시 쌓지 않도록, 제품과 무관한 "Global Dictionary"
계층을 둡니다.

저장 위치: 새 DB 테이블을 추가하지 않고, 이미 검증된 spec_rule_db의 QbSpecRules
저장/시드 폴백 경로를 그대로 재사용합니다 — product="__global__"이라는 가짜 제품
행 하나로 취급합니다. 별도 마이그레이션이 필요 없고, DB가 비어 있어도
spec_rules.seed.__global__.json 시드가 있으므로 배포 직후에도 바로 동작합니다.
(이 시드는 기존 4개 제품 dictionary 중 2개 이상 제품에서 겹치는 표현을 1회
집계해서 만든 것 — spec_dict_global.migrate_from_products() 참고)

조회 우선순위(merge_for): Global ∪ 제품별 dictionary. 같은 대표어가 양쪽에 있으면
합집합으로 합칩니다(어느 쪽도 덮어써서 유실되지 않음).
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List

import spec_rule_db

GLOBAL_KEY = "__global__"


def load() -> Dict[str, List[str]]:
    rs = spec_rule_db.load(GLOBAL_KEY)
    return dict((rs or {}).get("dictionary", {}))


def save(dictionary: Dict[str, List[str]]) -> None:
    # merge_dictionary=False — 여기서 넘기는 dictionary가 이미 최종본이므로 이중 병합 방지
    spec_rule_db.save(GLOBAL_KEY, {
        "product": GLOBAL_KEY, "version": "global", "rules": [], "dictionary": dictionary,
        "exceptions": [], "interactions": [], "country_exceptions": [], "candidates": [],
    }, merge_dictionary=False)


def add_alias(representative: str, alias: str) -> Dict[str, Any]:
    """모든 제품에 공통 적용될 alias를 Global에 승인. Dictionary 승인 화면의 기본 동작
    (요청: 신모델 나올 때 번역을 재사용하려면 기본이 공통이어야 함)."""
    d = load()
    d.setdefault(representative, [])
    if alias not in d[representative]:
        d[representative].append(alias)
    save(d)
    return {"representative": representative, "aliases": d[representative], "scope": "global"}


def merge_for(product_dictionary: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """spec_engine에 실제로 넘길 유효 사전 = Global ∪ 제품별(합집합).
    제품별 dictionary가 더 구체적인 표현을 추가로 갖고 있어도 Global 쪽을 덮어쓰지 않는다."""
    out: Dict[str, List[str]] = {k: list(v) for k, v in load().items()}
    for rep, aliases in (product_dictionary or {}).items():
        cur = out.setdefault(rep, [])
        for a in aliases:
            if a not in cur:
                cur.append(a)
    return out


def global_representatives() -> set:
    """이 대표어들은 Global에서 온 것 — 프론트엔드가 '🌐 공통' 배지를 붙일 때 사용."""
    return set(load().keys())


def migrate_from_products(products: List[str], min_products: int = 2) -> Dict[str, Any]:
    """1회성 백필: 여러 제품에 동일한 대표어로 존재하는 표현을 Global로 승격한다.
    제품별 dictionary에서는 절대 제거하지 않는다 — merge_for가 합집합으로 처리하므로
    안전하며, 실수로 제품 데이터를 건드려 유실될 위험을 만들지 않기 위함.
    관리자 엔드포인트(POST /spec-rules/dictionary/migrate)에서 호출된다."""
    per_product: Dict[str, Dict[str, List[str]]] = {}
    for p in products:
        rs = spec_rule_db.load(p)
        if rs:
            per_product[p] = rs.get("dictionary", {}) or {}

    rep_count: Dict[str, int] = defaultdict(int)
    rep_aliases: Dict[str, set] = defaultdict(set)
    for _p, d in per_product.items():
        for rep, aliases in d.items():
            rep_count[rep.strip()] += 1
            rep_aliases[rep.strip()].update(aliases)

    promoted = {rep: sorted(al) for rep, al in rep_aliases.items() if rep_count[rep] >= min_products}
    if promoted:
        g = load()
        for rep, aliases in promoted.items():
            g.setdefault(rep, [])
            for a in aliases:
                if a not in g[rep]:
                    g[rep].append(a)
        save(g)
    return {"promoted_representatives": sorted(promoted.keys()), "count": len(promoted),
            "products_scanned": list(per_product.keys())}

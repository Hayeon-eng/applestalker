"""
spec_dict_review.py — 큐비 — Spec QA Dictionary Review 집계 [보조 기능]

★ Dictionary는 Spec QA의 핵심이 아니라 보조 기능이다 ★
운영자가 가장 먼저 봐야 하는 것은 Critical Error(실제 Spec 오류)이고, Dictionary
Review는 화면에서 항상 접힌 상태로, 맨 아래에 노출된다(프론트엔드 QubiSpecQa.tsx).

spec_engine.run()은 페이지 1장 단위로만 동작하므로 "동일 표현이 여러 페이지에서
반복 발견"(요구사항 3) 여부를 알 수 없다. 이 모듈은 한 번의 검수 실행(run)에서 나온
여러 페이지 결과를 "제품" 단위로 모아, 다음 조건을 모두 만족하는 것만 최종 Dictionary
Review 후보로 승격한다.

  · Spec 영역(Attribute/Value)에서 발견 — spec_engine이 이미 SPEC_LIKE_SECTIONS로
    필터링한 candidate_hits만 입력으로 받는다.
  · 동일 제품 내 여러 페이지에서 반복 발견 (기본 3회 이상 — MIN_PRODUCT_PAGES)
  · Stopword가 아님
  · Confidence 기준 이상(Low는 자동 제외)

Confidence는 결정론적 1차 신호(구조 소스 신뢰도 + 반복 페이지 수)를 기본으로 하고,
dict_ai_suggest의 AI confidence가 있으면 등급을 보정하는 데만 보조적으로 사용한다
(spec_engine 자체의 Validation 판정에는 AI를 쓰지 않는다는 원칙은 유지 — 이 모듈은
Dictionary라는 별도 보조 기능에서만, 그것도 등급 보정 용도로만 AI를 참고한다).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

# 동일 제품 내 최소 반복 발견 페이지 수 — 이 미만이면 우연/1회성 표현으로 보고 자동 제외
MIN_PRODUCT_PAGES = 3

# 일반적인 UI/메뉴 성격 짧은 표현 — Spec 영역 필터를 통과해도 한 번 더 걸러내는 안전망.
# (본래는 header/footer/nav/button/popup 태그 단계에서 대부분 제외되지만, 스펙 표
# 내부에 우연히 섞인 "더보기"류 표현까지 잡기 위한 마지막 방어선)
_STOPWORDS = {
    "more", "detail", "details", "etc", "n/a", "-", "확인", "닫기", "열기", "보기",
    "구매", "다운로드", "설정", "메뉴", "선택", "취소", "다음", "이전", "더보기",
    "確認", "閉じる", "詳細", "もっと見る", "戻る", "开始", "关闭", "更多",
}


def _is_product_name(label: str, product: str) -> bool:
    """제품명(슬러그)과 사실상 같은 표현은 Dictionary 후보에서 제외 — 'Galaxy Z Fold8' 같은 게 뜨면 혼란만 준다.
    슬러그(galaxy-z-fold8)의 토큰이 라벨에 대부분 들어 있으면 제품명으로 본다."""
    n = re.sub(r"[^a-z0-9]+", " ", (label or "").lower()).split()
    toks = [t for t in re.sub(r"[^a-z0-9]+", " ", (product or "").lower()).split() if t not in ("galaxy",)]
    if not n or not toks:
        return False
    hit = sum(1 for t in toks if t in n)
    return hit >= max(1, len(toks) - 1)  # 슬러그 토큰이 거의 다 들어있음


def _is_stopword(label: str) -> bool:
    n = re.sub(r"\s+", "", label or "").lower()
    if not n or len(n) <= 1:
        return True
    if n.isdigit():
        return True
    return n in _STOPWORDS


def _confidence_tier(structural_high: bool, page_spread: int, ai_conf: Optional[float]) -> str:
    """규칙 기반 1차 필터(구조 소스 + 반복 페이지 수) + AI 제안 confidence로 등급 보정.
    AI confidence가 없으면 규칙 기반 점수만으로 등급을 매긴다(결정론성 유지)."""
    score = 2 if structural_high else 1          # dl/table(고신뢰) vs sibling(중간)
    score += 1 if page_spread >= MIN_PRODUCT_PAGES + 2 else 0
    if ai_conf is not None:
        score += 2 if ai_conf >= 0.75 else (1 if ai_conf >= 0.45 else 0)
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def aggregate(page_results: List[Dict[str, Any]],
              ai_confidence: Optional[Dict[str, float]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """page_results: 한 번의 검수 실행(run) 결과 전체(여러 제품 섞여 있어도 됨).
    각 pr는 runner.run_site()가 반환하는 dict(‘product’, ‘sitecode’, ‘spec_v2’ 포함)를 기대.
    ai_confidence: {alias.lower(): 0~1} — dict_ai_suggest 결과를 미리 매핑해서 넘기면
                   등급 보정에 사용(선택, 없어도 동작).

    반환: {product: [ {alias, count, confidence, sections, recommend_canonical}, ... ]}
          count 내림차순 정렬. UI에서는 이 리스트를 접힌 'Dictionary Review' 섹션에
          "GPU (15)"처럼 빈도순으로 그룹 표시한다(요구사항 5)."""
    by_product: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for pr in page_results:
        product = pr.get("product") or "unknown"
        sv = pr.get("spec_v2") or {}
        hits = sv.get("candidate_hits", [])
        groups = by_product.setdefault(product, {})
        for c in hits:
            alias = (c.get("alias") or "").strip()
            if not alias or _is_stopword(alias) or _is_product_name(alias, product):
                continue
            key = alias.lower()
            g = groups.setdefault(key, {
                "alias": alias, "count": 0, "sitecodes": set(),
                "sources": set(), "sections": set(),
            })
            g["count"] += 1
            g["sitecodes"].add(pr.get("sitecode", ""))
            g["sources"].add(c.get("source", ""))
            g["sections"].add(c.get("section", ""))

    out: Dict[str, List[Dict[str, Any]]] = {}
    for product, groups in by_product.items():
        rows = []
        for g in groups.values():
            page_spread = len(g["sitecodes"])
            if page_spread < MIN_PRODUCT_PAGES:
                continue  # 여러 페이지 반복 조건(요구사항 3) 미충족 → 자동 제외
            structural_high = bool(g["sources"] & {"dl", "table"})
            ai_conf = (ai_confidence or {}).get(g["alias"].lower())
            tier = _confidence_tier(structural_high, page_spread, ai_conf)
            if tier == "low":
                continue  # Confidence 기준 미달 → 자동 제외(요구사항 3·4 — 억지 매핑 방지)
            rows.append({
                "alias": g["alias"],
                "count": page_spread,
                "confidence": tier,                       # high | medium
                "sections": sorted(s for s in g["sections"] if s),
                "recommend_canonical": tier == "high",      # 요구사항 4: High만 자동 추천
            })
        rows.sort(key=lambda x: -x["count"])
        if rows:
            out[product] = rows
    return out

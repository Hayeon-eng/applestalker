"""
compare_pipeline.py — 큐비 — Compare Pipeline 오케스트레이터

Crawler
├── PDP Pipeline      (기존 그대로: spec_extractor.extract + spec_engine.run)
└── Compare Pipeline  (신규 — 이 모듈)
    CompareExtractor(compare_extractor.py) → CompareQA(compare_qa.py) → Compare Result

runner.py는 page_type == "Compare"일 때 run_compare_pipeline() 하나만 호출한다.
Compare 관련 세부 분기(product_hint 해석, 정답 대조 등)는 모두 이 파이프라인
내부(compare_extractor/compare_qa)에 있고, 앞으로 Tablet/Watch/TV Compare가
추가돼도 runner.py를 다시 건드릴 필요가 없다 — Rule DB에 해당 제품의
product_aliases/previous_models만 채우면 이 파이프라인이 그대로 동작한다.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

from compare_extractor import CompareExtractor
from compare_qa import CompareQA


def run_compare_pipeline(html: str, market_product: Optional[str]) -> Dict[str, Any]:
    """Compare 페이지 HTML(Playwright 렌더 완료 DOM) → Compare Result.
    {
      "products": ["Galaxy Z Fold7", "Galaxy Z Fold6", "Galaxy Z Fold5"],
      "rows": [
        {"category": "Display", "spec": "Screen Size",
         "values": [{"product": "...", "value": "8.0\"", "status": "pass", "message": "OK"}, ...]}
      ],
      "summary": {"checked": true, "per_product": [...]}
    }
    market_product이 없거나 해당 Rule DB가 없으면 summary.checked=False로, 매트릭스
    (rows/products)만 반환한다 — 추출 자체는 항상 시도한다."""
    matrix = CompareExtractor().extract(html)
    # [2026-07] 컬럼(제품)마다 자기 자신의 Rule DB를 alias로 찾아 채점하므로
    # market_product 유무와 무관하게 항상 CompareQA를 실행한다(참고용으로만 전달).
    return CompareQA().evaluate(matrix, market_product)

"""
compare_extractor.py — 큐비 — Compare Pipeline · Step 1 (CompareExtractor)

배경
  Samsung Compare 페이지는 PDP의 변형이 아니라 완전히 다른 데이터 구조(Category →
  Spec Row → Product1/2/3 Value의 Matrix)를 가진 별도 Page Type이다. 이 모듈은
  Compare 전용 추출을 담당하며, PDP 파이프라인(spec_extractor.extract 자체의 동작,
  spec_engine)은 전혀 수정하지 않는다.

재사용 범위
  · HTML → DOM 파싱은 spec_extractor.extract()를 그대로 재사용한다(중복 구현 금지).
    spec_extractor는 이미
      - data-spec-value 계열(예: <p data-spec-type="keyCamera-4" data-spec-value="...">)을
        읽을 때, DOM 순서(index)가 아니라 각 셀이 속한 <li class="__item"> 안의
        sr-only 텍스트("Galaxy Z Fold6")로 제품을 식별해 product_hint를 붙인다.
      - Compare형 <table>(값 컬럼 2개 이상)의 각 값 셀에도 헤더 행 텍스트를
        product_hint로 붙인다.
    즉 "첫 번째 값 = 첫 번째 제품" 같은 단순 DOM 순서 의존은 이미 spec_extractor
    단계에서 배제되어 있다 — 이 모듈은 그 product_hint를 안정적 식별자로 사용한다.
  · 이 모듈이 새로 하는 일은 pairs(플랫 리스트)를
        Category → Spec → [{product, value}, ...]
    형태의 Matrix로 "재구성"하는 것과, Compare Header에서 현재 비교 중인 Product
    목록(Product Map)을 명시적으로 뽑아내는 것이다.

Product 개수는 고정하지 않는다(2개 이상 모두 지원) — product_hint 값의 종류 수만큼
컬럼이 생긴다. 제품 순서 변경/추가/삭제에도 동작한다(순서에 의존하지 않으므로).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

import spec_extractor


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def build_product_map(html: str) -> List[str]:
    """Compare Header(상단 제품 선택 영역)에서 현재 비교 중인 Product 목록을 뽑는다.
    data-spec-value 계열의 product_hint(각 항목이 속한 <li>의 sr-only 텍스트)와
    동일한 소스를 헤더에서도 우선 사용해, 본문 매트릭스와 동일한 명칭 체계를 쓴다."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "lxml")
    names: List[str] = []
    seen = set()

    # ① 비교 헤더 영역(class에 compare-header/product-select 류)의 sr-only/aria-label
    header_rx = re.compile(r"compare[-_]?(header|product|select|nav|tabs?)\b", re.I)
    for el in soup.find_all(True, class_=header_rx):
        sr = el.find(class_=re.compile("sr-only"))
        text = _clean((sr or el).get_text(" ", strip=True)) or _clean(el.get("aria-label", ""))
        if text and len(text) < 80 and text not in seen:
            seen.add(text)
            names.append(text)
    if names:
        return names

    # ② 폴백: 본문 __item(li) sr-only 텍스트 등장 순서(= 상단 헤더가 안 잡힐 때만)
    for li in soup.find_all("li", class_=re.compile(r"__item\b")):
        sr = li.find(class_=re.compile("sr-only"))
        if sr is None:
            continue
        text = _clean(sr.get_text(" ", strip=True))
        if text and text not in seen:
            seen.add(text)
            names.append(text)
    return names


class CompareExtractor:
    """Compare 페이지 전용 Extractor. PDPExtractor(=spec_extractor.extract 그대로)와는
    독립적으로 동작하며, 이 클래스만 Matrix 구조를 만든다."""

    def extract(self, html: str) -> Dict[str, Any]:
        parsed = spec_extractor.extract(html)  # Playwright 렌더 완료 후 DOM(호출측 책임)
        pairs = parsed.get("pairs", [])
        products = build_product_map(html)

        # Category → Spec → {product: value} 로 그룹핑. dict 순서(3.7+)로 최초 등장
        # 순서를 그대로 유지한다.
        rows: "dict" = {}
        for p in pairs:
            hint = p.get("product_hint")
            if not hint:
                continue  # Compare 매트릭스는 product 귀속이 있는 페어만 대상으로 한다
            category = p.get("category") or ""
            spec = p.get("spec_label") or p.get("label") or ""
            if not spec:
                continue
            key = (category, spec)
            row = rows.setdefault(key, {})
            # 같은 (category, spec, product) 조합이 여러 소스에서 중복 추출되면
            # 먼저 채워진 값을 우선한다(가장 구조적인 tier인 data-attr가 먼저 순회됨).
            row.setdefault(hint, _clean(p.get("value", "")))
            if hint not in products:
                products.append(hint)

        matrix = []
        for (category, spec), value_by_product in rows.items():
            values = [{"product": prod, "value": value_by_product[prod]}
                      for prod in products if prod in value_by_product]
            # products 목록에 없는(헤더에서 못 잡은) product_hint도 누락 없이 포함
            for prod, val in value_by_product.items():
                if prod not in products:
                    values.append({"product": prod, "value": val})
            if values:
                matrix.append({"category": category, "spec": spec, "values": values})

        return {"products": products, "rows": matrix, "pair_count": len(pairs)}


def extract_compare_matrix(html: str) -> Dict[str, Any]:
    """함수형 진입점(간단 호출용) — CompareExtractor().extract(html)와 동일."""
    return CompareExtractor().extract(html)

"""
hc_provider.py — honeyComb 수집 계층 [2026-09 · 목업 단계]

설계 원칙: 엔진/화면은 provider 가 돌려주는 표준 결과(ShoppingResult)만 본다. 수집 방식이
Mock → SERP API → (선택) Merchant API 로 바뀌어도 hc_engine / 프론트는 그대로다.

  fetch_shopping(country, keyword) -> ShoppingResult
    country : hc_config.countries 항목 {code, gl, hl, ...}
    keyword : 검색어(브랜드명 또는 자연어 long-tail)
    결과    : {"items": [{"position", "title", "merchant", "price", "sale_price", "rating", "reviews",
                          "shipping", "image", "link", "is_samsung_store", "attrs": {code: value}}],
               "fetched_at", "provider", "raw_ref"}
  fetch_product_detail(country, item) -> {code: value}   # 상세패널(설명·추가이미지·영상·3D·하이라이트·Q&A…)

구현체
  MockProvider      : hc_mock_data.json 을 그대로 돌려준다(수집 없음 — 검토용).
  SerpApiProvider   : google_shopping / google_product 엔진 — 키 필요, 미구현(NotImplementedError).
  PlaywrightProvider: google.com tbm=shop 직접 렌더 — 차단·개인화 리스크, 미구현.
  MerchantApiProvider(보조): 피드 측 속성/승인 — 노출 순위는 못 준다, 미구현.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(__file__)


class Provider:
    name = "base"

    def fetch_shopping(self, country: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_product_detail(self, country: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, str]:
        raise NotImplementedError


class MockProvider(Provider):
    """hc_mock_data.json 의 runs 를 provider 결과처럼 재생한다. 목업 검토 전용."""
    name = "mock"

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(_HERE, "hc_mock_data.json")
        self.data = json.load(open(self.path, encoding="utf-8"))

    def config(self) -> Dict[str, Any]:
        return self.data["config"]

    def attributes(self) -> List[Dict[str, Any]]:
        return self.data["attributes"]

    def runs(self) -> List[Dict[str, Any]]:
        return self.data["runs"]

    def fetch_shopping(self, country, keyword):  # 목업에서는 run 단위로 이미 판정돼 있어 호출되지 않는다
        raise NotImplementedError("MockProvider 는 runs 를 직접 제공한다 — 실수집 provider 를 붙일 때 구현")


class SerpApiProvider(Provider):
    """SerpApi(google_shopping) — 환경변수 SERPAPI_KEY. 결과 JSON 의 shopping_results[].position/title/source/
    price/extracted_price/rating/reviews/delivery/thumbnail/product_link 를 표준 item 으로 매핑할 자리."""
    name = "serpapi"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")

    def fetch_shopping(self, country, keyword):
        raise NotImplementedError("수집 방식 미확정(목업 단계). 확정 시 구현.")


class PlaywrightProvider(Provider):
    name = "playwright"

    def fetch_shopping(self, country, keyword):
        raise NotImplementedError("수집 방식 미확정(목업 단계). 확정 시 구현.")


def get_provider(kind: Optional[str] = None) -> Provider:
    kind = (kind or os.getenv("HC_PROVIDER", "mock")).lower()
    return {"mock": MockProvider, "serpapi": SerpApiProvider, "playwright": PlaywrightProvider}.get(kind, MockProvider)()

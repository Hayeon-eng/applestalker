"""
qb_core.py — 큐비 API 공유 인프라 [qb_api 분할]
qb_router / SiteRegistry / fetcher 주입 / 마지막 검수 결과(LAST_RESULTS) / 공용 헬퍼.
라우트 모듈(qb_routes_*)이 여기서 qb_router를 가져가 엔드포인트를 등록한다.
상태 재할당은 반드시 `qb_core.LAST_RESULTS = ...`처럼 모듈 속성으로 접근해야
모든 모듈에서 일관되게 보인다.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))  # 패키지/스크립트 양쪽에서 flat import 허용

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
import schema_checker
import html_qa_scoring
from site_registry import SiteRegistry
from database import SessionLocal
from models import QbHistory

qb_router = APIRouter(prefix="/api/qb", tags=["qubi"])
_registry = SiteRegistry()
_fetcher: Optional[Callable[[str], Optional[str]]] = None


def set_fetcher(fn: Callable[[str], Optional[str]]):
    """기존 크롤러의 'url -> html' 함수를 주입."""
    global _fetcher
    _fetcher = fn


def enable_default_crawler(requires_js: bool = True):
    """기존 애플스토커의 HybridCrawler 를 큐비 fetcher 로 자동 연결.
    삼성닷컴은 JS 렌더링 페이지가 많아 requires_js=True 를 기본으로 둔다
    (httpx 로 충분하면 그대로 쓰고, 얇게 오면 Playwright 로 업그레이드)."""
    import asyncio

    def _fetch(url: str) -> Optional[str]:
        async def _run():
            from crawler import HybridCrawler
            c = HybridCrawler()
            await c.start()
            try:
                res = await c.crawl(url, requires_js=requires_js)
                return (res or {}).get("html_content")
            finally:
                await c.close()
        return asyncio.run(_run())

    set_fetcher(_fetch)




# ── 마지막 검수 결과 보관(Apple Stalker latest-report 패턴) ──
# 프론트가 큰 결과를 POST로 보내지 않고 GET으로 내려받게 해 CORS preflight 회피.
LAST_RESULTS: List[Dict[str, Any]] = []


def _resolve_results(payload=None, run_id: str = None):
    """우선순위: 요청 body의 results → run_id 이력 → 서버가 든 마지막 결과."""
    if payload and payload.get("results"):
        return payload["results"]
    if run_id:
        db = SessionLocal()
        try:
            row = db.query(QbHistory).filter(QbHistory.run_id == run_id).first()
            if row:
                return json.loads(row.results)
        finally:
            db.close()
    return LAST_RESULTS


def _sitecode_from_url(url: str) -> str:
    import re
    if "samsung.com.cn" in (url or ""):
        return "cn"
    m = re.search(r"samsung\.com/([^/]+)/", url or "")
    return m.group(1) if m else (url or "").strip("/").split("/")[-1]


def _v2_managed(product: str) -> bool:
    """이 제품의 기준값이 Rule DB(V2)로 관리되는지. V2 제품은 구식 편집 경로
    (key_specs/copy_rules 직접 수정)를 전부 차단해 원본을 하나로 유지한다."""
    try:
        import spec_rule_db as _srd
        return product in {p["product"] for p in _srd.list_products()}
    except Exception:
        return False


_V2_EDIT_BLOCKED = ("이 제품의 기준값은 Rule DB(V2)로 관리됩니다 — 화면 편집 불가. "
                    "값 수정은 스펙 탭의 'Rule DB 엑셀 업로드', 표현 추가는 'Dictionary 추가' 승인을 사용하세요.")


# ── 공유 상수 (여러 라우트 모듈이 함께 사용) ──────────────────────────
# [분할 버그 수정] qb_api.py를 라우트 모듈로 쪼갤 때 PAGE_TYPES/SCHEMA_TYPES가
# qb_routes_manage.py에만 들어가 /rules(check 모듈)가 NameError로 500이 났음.
# 두 상수를 여기(core)로 올려 모든 라우트 모듈이 공유한다.
PAGE_TYPES = ["PDP", "Compare", "Buying"]
SCHEMA_TYPES = [
    "WebPage", "ItemPage", "WebSite", "BreadcrumbList", "ItemList", "ListItem", "CollectionPage",
    "Product", "ProductGroup", "Offer", "AggregateOffer", "Brand", "Organization",
    "Review", "CriticReview", "AggregateRating", "BuyAction",
    "ImageObject", "VideoObject", "3DModel", "MediaObject",
    "FAQPage", "Question", "Answer", "HowTo", "Article",
    "Person", "Rating", "PropertyValue", "WebPageElement",
]

"""
qb_routes_specrules.py — Spec QA Rule DB [V2] (/spec-rules*, /spec-check) [qb_api 분할]
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
import schema_checker
import html_qa_scoring
from database import SessionLocal
from models import QbHistory

import qb_core
from qb_core import qb_router, _registry

# ═══════════════════════════════════════════════════════════════════
# Spec QA Rule DB [V2] — 엑셀 업로드/조회/Dictionary 승인
#   룰은 코드가 아니라 이 데이터로 확장된다 (spec_rule_db.py 참조)
# ═══════════════════════════════════════════════════════════════════
import spec_rule_db as _spec_rule_db  # noqa: E402


@qb_router.get("/spec-rules/products")
def qb_spec_rules_products():
    """등록된 Rule DB 제품 목록 (DB + 시드)."""
    return {"products": _spec_rule_db.list_products()}


@qb_router.get("/spec-rules")
def qb_spec_rules_get(product: str = Query(...)):
    """제품 룰셋 전체(MasterSpec/Dictionary/Exception/Interaction/Candidates)."""
    rs = _spec_rule_db.load(product)
    if not rs:
        raise HTTPException(404, f"룰셋 없음: {product} — 엑셀을 업로드하세요.")
    return rs


@qb_router.post("/spec-rules/upload")
def qb_spec_rules_upload(payload: Dict[str, Any] = Body(...)):
    """Rule DB 엑셀 업로드 → 파싱 → DB 저장.
    body: {b64: dataURL|base64, product: 'galaxy-z-fold7', version?: str}"""
    import base64
    b64 = (payload.get("b64") or "")
    product = (payload.get("product") or "").strip()
    if not b64 or not product:
        raise HTTPException(400, "b64와 product가 필요합니다.")
    if "," in b64:  # dataURL
        b64 = b64.split(",", 1)[1]
    try:
        content = base64.b64decode(b64)
        ruleset = _spec_rule_db.parse_xlsx(content, product=product,
                                           version=payload.get("version", "uploaded"))
    except Exception as e:
        raise HTTPException(400, f"엑셀 파싱 실패 — {e}")
    info = _spec_rule_db.save(product, ruleset, version=payload.get("version", ""))
    return {"ok": True, **info,
            "dictionary": len(ruleset["dictionary"]), "exceptions": len(ruleset["exceptions"]),
            "interactions": len(ruleset["interactions"])}


@qb_router.post("/spec-rules/dictionary/add")
def qb_spec_rules_dict_add(payload: Dict[str, Any] = Body(...)):
    """Dictionary Alias 추가 — 반드시 사용자 승인(버튼 클릭) 후 호출된다.
    body: {product, representative, alias}"""
    product = (payload.get("product") or "").strip()
    rep = (payload.get("representative") or "").strip()
    alias = (payload.get("alias") or "").strip()
    if not (product and rep and alias):
        raise HTTPException(400, "product/representative/alias가 필요합니다.")
    try:
        return {"ok": True, **_spec_rule_db.add_alias(product, rep, alias)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@qb_router.post("/spec-check")
def qb_spec_check(payload: Dict[str, Any] = Body(...)):
    """Spec QA V2 단독 실행 (HTML 붙여넣기 검증/디버그용).
    body: {html, product, page_type?, sitecode?} → spec_v2 결과"""
    html = payload.get("html")
    product = (payload.get("product") or "").strip()
    if not html or not product:
        raise HTTPException(400, "html과 product가 필요합니다.")
    rs = _spec_rule_db.load(product)
    if not rs:
        raise HTTPException(404, f"룰셋 없음: {product}")
    import spec_engine as _spec_engine
    return _spec_engine.run(html, rs, page_type=payload.get("page_type", "PDP"),
                            sitecode=payload.get("sitecode", ""))

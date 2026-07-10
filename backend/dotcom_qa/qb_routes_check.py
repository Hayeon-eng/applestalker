"""
qb_routes_check.py — 단일 검수 (/rules, /check, /check-url, /check-html-qa) [qb_api 분할]
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
from qb_core import qb_router, _registry, PAGE_TYPES, SCHEMA_TYPES

@qb_router.get("/rules")
def qb_rules(product: str = Query("M3"), page_type: str = Query("PDP"),
             market_product: str = Query(None)):
    """화면 '?' 기준 패널용 — 규칙을 사람이 읽는 형태로 그대로 반환."""
    rules = runner.load_rules(product, page_type=page_type, market_product=market_product)
    schema_set = rules.get("schema_set")
    set_label = {"flagship": "Flagship PD (스마트폰)", "simple": "Simple PD (버즈·노트북·태블릿 등)",
                 "compare": "Compare PD", None: "해당없음(Buying 등 검사 제외)"}.get(schema_set, str(schema_set))
    schema_blocks = [{
        "block": b["name"], "types": b["types"], "id": b.get("id_slug"),
        "required_properties": b.get("required_properties", []),
        "optional_properties": b.get("optional_properties", []),
        "haspart_ids": b.get("haspart_ids", []),
        "conditional": b.get("conditional"),
    } for b in rules["schema"].get("blocks", [])]
    return {
        "product": product, "page_type": page_type,
        "page_types": PAGE_TYPES, "schema_types": SCHEMA_TYPES,
        "schema_set": schema_set, "schema_set_label": set_label,
        "schema": {
            "설명": (f"[{set_label}] Word(PTK 2.4.14) 기준 필수 스키마 @type/@id/속성, "
                     f"Product.hasPart @id, 값 정확성, 조건부(WARN)"),
            "출처": "PTK_schema_set 크롬 확장 2.4.14 (Word) — Buying은 검사 제외",
            "blocks": schema_blocks,
        },
        "google_criteria": {
            "설명": "Google 기준은 두 층위로 나뉩니다 — ①문법이 파싱되는가 ②파싱된 뒤 리치결과 자격(필수/권장 속성)을 충족하는가. 실시간 Rich Results Test API 호출은 이 환경에서 불가 → Google 공식 문서 기준을 정적 룰로 반영.",
            "문법_오류": {
                "구글_기준": [
                    "스마트 따옴표(“ ” ‘ ’) 등 유니코드로 값이 코드 아닌 문자로 입력 → 경고",
                    "닫는 괄호/따옴표 부족(괄호 불균형) → 오류",
                    "항목 사이 쉼표 누락 → 오류",
                    "마지막 항목 뒤 후행 쉼표 → 경고(자동 보정)",
                    "비표시 문자(NBSP·제로폭·BOM) 포함 → 경고",
                ],
                "우리_기준": [
                    "위 Google Rich Result 문법 규칙을 동일하게 적용",
                    "about 이 배열([...])이면 오류가 아닌 '권장(object)' 경고로 완화",
                    "name 등 번역 대상 값은 오류가 아닌 '번역 확인' 경고",
                ],
            },
            "리치결과_필수_권장": {
                "필수_속성_누락_오류": [
                    "리치결과 필수 속성이 없으면 오류 — 그 즉시 리치결과 자격 상실(가이드 필수 ∪ Google 공식 필수 중 더 엄격한 쪽 적용)",
                    "필수 속성 값이 형식/기준과 안 맞으면 오류(URL 아님·ISO8601 아님 등)",
                ],
                "권장_속성_누락_경고": [
                    "권장 속성이 없으면 경고 — 자격은 유지되지만 품질 저하",
                ],
                "타입별_상태": {
                    "Product": "정식 적용", "VideoObject": "정식 적용",
                    "3DModel": "제한적(일반 리치결과 X, AR만 해당)",
                    "FAQPage": "폐지(2026-05-07 Google 공식 종료 — 스키마는 유효하나 SEO 감점/가점 대상 아님)",
                },
            },
        },
        "check_methods": {
            "설명": "카피덱 정답지 기준으로 값을 검사합니다. 검사 방식별로 오류/경고를 구분합니다.",
            "정확히_일치_오류": [
                "제품 주소가 정확한지 — url·@id·mainEntity·about·brand/manufacturer/publisher 주소가 기준과 다르면 오류(사이트코드만 치환, 제품 슬러그는 정확히 일치)",
                "연결된 제품 주소가 맞는지 — hasPart의 @id에 다른 제품 주소가 섞이면 오류",
                "제품명이 올바른지 — 번역은 허용하되 제품 식별어(예: S26 Ultra / Buds4 Pro)가 빠지거나 다른 모델명이 섞이면 오류",
                "고정값이 맞는지 — @type·@context·BuyAction 등 고정 키워드는 정확히 일치",
            ],
            "필수_있어야_함_오류": [
                "반드시 있어야 하는 필수 속성이 없으면 오류(Word 기준 required)",
            ],
            "확인_경고": [
                "번역 검토 — name·description 등 번역 대상 텍스트는 존재만 확인(원문과 달라도 오류 아님)",
                "이미지 경로 — 파일명 변동은 허용, 경로에 제품이 맞는지만 확인",
                "영상 길이 — PT#S 형식만 확인",
                "페이지 언어 — inLanguage가 사이트 언어와 다르면 확인(의도된 현지화일 수 있어 오류 아님)",
                "선택 속성 미적용 — Word 기준 optional은 없어도 경고 수준",
            ],
        },
        "copy": {
            "설명": "번역 불변 값만 검사 — 스펙 토큰(숫자+단위) 정확 일치, 고유명사 존재(WARN), 핵심 스펙 값 대조",
            "spec_tokens": rules["copy"].get("spec_tokens", []),
            "proper_nouns": rules["copy"].get("proper_nouns", []),
        },
    }

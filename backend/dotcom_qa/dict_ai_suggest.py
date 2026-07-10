"""
dict_ai_suggest.py — 딕셔너리 '미등록 표현'에 대한 AI 번역 제안 (승인 대기 후보 보조용)

원칙: 검수 판정 자체는 규칙기반(결정적)으로 유지한다. 이 모듈은 오직
'사람이 최종 승인하기 전에 후보에 참고용 제안을 붙이는' 용도로만 쓴다.
- GEMINI_API_KEY 가 없거나 SDK 미설치면 조용히 available=False 로 폴백(에러 안 냄).
- 반환은 '제안'일 뿐이며, 딕셔너리에 실제로 넣는 것은 사람의 승인(dictionary/add)으로만 이뤄진다.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
    _GENAI = True
except Exception:
    _GENAI = False

_MODEL = None
_READY = False


def _ensure_model():
    """지연 초기화 — 키가 있을 때만 모델을 만든다. 실패해도 예외를 밖으로 내지 않는다."""
    global _MODEL, _READY
    if _READY:
        return _MODEL
    if not _GENAI:
        return None
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "your_gemini_api_key_here":
        return None
    try:
        genai.configure(api_key=key)
        _MODEL = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
        _READY = True
        return _MODEL
    except Exception as e:
        print(f"[dict_ai] gemini init failed: {e}")
        return None


def is_available() -> bool:
    return _ensure_model() is not None


def suggest(alias: str, attributes: List[str], lang_hint: str = "") -> Dict[str, Any]:
    """미등록 표현(alias)이 attributes 중 어느 항목의 번역/표기인지 제안.
    반환: {"available": bool, "attribute": str|None, "confidence": int|None, "reason": str}
    키가 없으면 available=False 로 폴백(프론트는 '준비 중'만 표시)."""
    model = _ensure_model()
    if model is None:
        return {"available": False, "attribute": None, "confidence": None, "reason": ""}

    attr_list = ", ".join(attributes)
    prompt = (
        "You map a product-spec label found on a Samsung.com page to its canonical attribute.\n"
        f"Found label (possibly localized): \"{alias}\"\n"
        f"{('Page language hint: ' + lang_hint) if lang_hint else ''}\n"
        f"Candidate canonical attributes: {attr_list}\n\n"
        "Pick the single best match, or null if none fits. "
        "Respond ONLY with compact JSON, no markdown:\n"
        '{"attribute": "<one of the candidates or null>", "confidence": <0-100>, "reason": "<short>"}'
    )
    try:
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        attr = data.get("attribute")
        if attr not in attributes:
            attr = None
        conf = data.get("confidence")
        conf = int(conf) if isinstance(conf, (int, float)) else None
        return {"available": True, "attribute": attr, "confidence": conf,
                "reason": str(data.get("reason", ""))[:120]}
    except Exception as e:
        print(f"[dict_ai] suggest failed: {e}")
        return {"available": False, "attribute": None, "confidence": None, "reason": ""}

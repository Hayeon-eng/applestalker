"""Gemini deep health check helper.

이 파일은 GitHub 웹 에디터에서 큰 intel_engine.py를 건드리지 않기 위해 분리한
작은 진단용 모듈이다. 실제 Gemini API에 초소형 요청을 보내 인증/쿼터/모델 문제를 구분한다.
"""

import os
import re
import time
from typing import Any, Dict

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    genai = None  # type: ignore


def _api_key_diagnostics(api_key: str) -> Dict[str, Any]:
    """GEMINI_API_KEY 값의 형태만 점검한다. 실제 키 값은 절대 반환하지 않는다."""
    stripped = (api_key or "").strip()
    lower = stripped.lower()
    return {
        "present": bool(api_key),
        "length": len(stripped),
        "has_outer_whitespace": api_key != stripped,
        "looks_like_api_key": stripped.startswith("AIza"),
        "looks_like_oauth_token": lower.startswith("ya29") or lower.startswith("bearer "),
        "looks_like_json_credential": stripped.startswith("{") or "BEGIN PRIVATE KEY" in stripped,
    }


def _classify_gemini_error(error_message: str) -> str:
    msg = (error_message or "").lower()
    # [FIX] gemini-2.5+ 계열은 thinking 토큰이 max_output_tokens 예산을 같이 깎아먹어서,
    # 예산이 작으면(혹은 프롬프트가 복잡해 thinking이 길어지면) 진짜 답변 Part가 하나도
    # 안 만들어진 채 finish_reason=MAX_TOKENS로 끝나 response.text가 죽는다.
    # 이 구버전 SDK(google-generativeai)는 thinking_config 필드 자체가 없어 끄거나
    # 예산을 조절할 방법이 없다 → 별도 상태로 분류해서 바로 알아볼 수 있게 한다.
    if "quick accessor requires the response to contain a valid" in msg or (
        "finish_reason" in msg and (" 2" in msg or "max_tokens" in msg)
    ):
        return "thinking_budget_exhausted"
    if "access_token_type_unsupported" in msg or "invalid authentication credentials" in msg or "401" in msg:
        return "invalid_authentication"
    if "api_key_invalid" in msg or "api key not valid" in msg or "invalid api key" in msg:
        return "invalid_api_key"
    if "resource_exhausted" in msg or "quota" in msg or "429" in msg or "rate limit" in msg:
        return "quota_or_rate_limit"
    if "permission_denied" in msg or "403" in msg:
        return "permission_denied"
    if "not_found" in msg or ("model" in msg and "not found" in msg) or "404" in msg:
        return "model_not_found"
    if "timeout" in msg or "deadline" in msg:
        return "timeout"
    return "unknown_error"


def _redact_error(raw: str, api_key: str) -> str:
    safe = raw or ""
    if api_key:
        safe = safe.replace(api_key, "[REDACTED_GEMINI_API_KEY]")
    return re.sub(r"AIza[0-9A-Za-z_\-]{8,}", "[REDACTED_GEMINI_API_KEY]", safe)


def gemini_deep_health_check() -> Dict[str, Any]:
    """Gemini SDK 초기화뿐 아니라 실제 generate_content 호출까지 검증한다."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    diag = _api_key_diagnostics(api_key)

    base: Dict[str, Any] = {
        "ok": False,
        "sdk_available": bool(genai),
        "configured": False,
        "model": model_name,
        "api_key": diag,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if not genai:
        base.update({
            "status": "sdk_missing",
            "message": "google-generativeai 패키지를 import하지 못함",
        })
        return base

    if not api_key or api_key == "your_gemini_api_key_here":
        base.update({
            "status": "api_key_missing",
            "message": "GEMINI_API_KEY가 비어 있거나 placeholder 값임",
        })
        return base

    started = time.time()
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        base["configured"] = True
        resp = model.generate_content(
            "Return exactly OK.",
            # [FIX] 4토큰은 thinking 모델에선 thinking만 하다 끝나버림. 512로 올려서
            # 최소한 이 테스트 자체는 thinking budget 문제로 죽지 않게 함(근본 해결은 아님).
            generation_config={"temperature": 0, "max_output_tokens": 512},
            request_options={"timeout": 20},
        )
        text = (getattr(resp, "text", "") or "").strip()
        base.update({
            "ok": True,
            "status": "ok",
            "latency_ms": int((time.time() - started) * 1000),
            "sample_response": text[:40],
        })
        return base
    except Exception as e:
        raw = _redact_error(str(e), api_key)
        status = _classify_gemini_error(raw)
        hints = {
            "thinking_budget_exhausted": "gemini-2.5+ thinking 토큰이 max_output_tokens를 다 써서 실제 답변이 비어 반환됨. "
                                          "구버전 SDK(google-generativeai)는 thinking_config를 지원하지 않아 끌 수 없음 — "
                                          "google-genai SDK로 마이그레이션하거나 max_output_tokens를 넉넉히 늘려야 함",
            "invalid_authentication": "API key가 아니라 OAuth access token/Bearer token/JSON credential이 들어갔을 가능성이 큼",
            "invalid_api_key": "API key 값이 잘못됐거나 폐기됨. Google AI Studio에서 새 API key 발급 필요",
            "quota_or_rate_limit": "quota 소진 또는 rate limit. Google AI Studio/Cloud quota 확인 필요",
            "permission_denied": "해당 key/project에서 Gemini API 사용 권한 또는 API 활성화 상태 확인 필요",
            "model_not_found": "GEMINI_MODEL 값이 현재 사용 가능한 모델명인지 확인 필요",
            "timeout": "Gemini 응답 지연 또는 네트워크 timeout",
            "unknown_error": "Render 로그의 전체 에러와 GEMINI_API_KEY/GEMINI_MODEL 설정 확인 필요",
        }
        base.update({
            "status": status,
            "latency_ms": int((time.time() - started) * 1000),
            "error_type": e.__class__.__name__,
            "error_message": raw[:1200],
            "hint": hints.get(status, hints["unknown_error"]),
        })
        return base

"""
html_qa_scoring.py — 큐비 🐝 HTML QA 채점 엔진 [신규]

Schema QA → HTML QA 확장판. 채점표(큐비_HTML_QA_채점표_v0.7.xlsx) 6탭 기준을 코드로 옮긴 것.
기존 schema_checker.py / qb_api.py는 건드리지 않고 신규 모듈로 추가함(기존 화면·API 영향 없음).

구성:
  Level1  = 적용율(%)      — H1/H2/Meta/스키마 타입 존재 여부(단순 로직)
  Level2  = AEO 퀄리티 점수 — 축1 정보적합성(%) × 축2 파싱+Google리치결과 게이트 × 축3 @id연결성 게이트

축2는 "파싱에러"에서 "파싱에러 + Google 리치결과 SEO 기준"으로 확장(2026-07 결정).
실시간 Rich Results Test API 호출은 불가 → Google 공식 필수/권장 속성 목록을 정적 룰로 내장.

미구현(엑셀 5_AI판단_보류검토 / 축2 표에 '구현보류'로 명시된 항목, 정직하게 None으로 리턴):
  - 무효 속성(hallucinated) 탐지        → schema.org vocab 사전 필요
  - 이미지 최소 해상도/비율 판정         → 이미지 fetch+치수분석 필요
  - FAQPage 자기완결성·인용적합성       → AI(LLM) 문장판단 필요, 축1 가중치에서 제외(재환산 반영됨)
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

import schema_checker  # extract_jsonld / _types_of 재사용

# ──────────────────────────────────────────────────────────────────
# 0) 채점표 v0.7 "5_최종_Level2(통합)" 축1 가중치를 그대로 코드화
#    (FAQPage는 A안 반영: 자기완결성·인용적합성 제외, 남은 2항목 50/50 재환산)
#    (Product/3DModel의 subjectOf류는 '선언여부'만 — 무결성은 축3에서 채점)
# ──────────────────────────────────────────────────────────────────
AXIS1_WEIGHTS: Dict[str, Dict[str, Any]] = {
    "Product": {
        "name": 4, "image": 3, "brand": 2, "manufacturer": 2,
        "potentialAction": 2, "subjectOf": 3,
        # Simple PDP 전용(v0.7: 필수등급 밴드 3~4에 정렬)
        "offers": 4, "sku": 3,
    },
    "3DModel": {
        # [2026-07 FIX] schema_rules(*.json)엔 isPartOf/about이 필수 속성으로 정의돼 있고
        # schema_checker도 "필수 속성 누락"으로 정상 리포트하고 있었지만, 이 채점표엔 두 키가
        # 아예 없어서(가중치 0) 정보 충족률·필수 속성 카운트에 전혀 반영되지 않았다 — 화면엔
        # 빨간 "필수 속성 누락" 경고가 뜨는데 바로 아래 정보 충족률은 100%로 뜨는 모순의 원인.
        # (WebPage,ItemPage에서 mainEntity/hasPart/breadcrumb을 추가한 것과 동일한 종류의 fix.)
        "encoding_contentUrl": 4, "encoding_encodingFormat": 3, "isPartOf": 3, "about": 2,
        "gltf": 4, "usdz": 4, "subjectOf": 3, "name": 1, "image": 1,
    },
    "VideoObject": {
        "name": 4, "thumbnailUrl": 3, "uploadDate": 3, "contentUrlOrEmbedUrl": 4,
        "description": 3, "duration": 3, "contentUrlAndEmbedUrl": 1,
        "hasPartOrSeek": 1, "expiresNoError": 1,
    },
    "FAQPage": {  # A안 재환산 — 자기완결성/인용적합성은 축1에서 제외됨(참고: AI판단_보류검토 탭)
        "structure_valid": 0.5, "screen_match": 0.5,
    },
    "WebPage, ItemPage": {
        "type_combo": 4, "name": 3, "url": 3, "description": 1, "primaryImage": 1,
        # [2026-07 FIX] schema_checker/schema_values는 mainEntity(#list)·hasPart(#faq)·
        # breadcrumb(#breadcrumb)의 @id 정확 일치를 이미 val_mismatch로 잡아내고 있었지만,
        # 이 채점표에 항목 자체가 없어 그 결과가 정보 충족률/필수·권장 속성 집계에 전혀
        # 반영되지 않는 문제가 있었다(화면엔 불일치가 보이는데 상단 %는 100%로 표시).
        # required_properties가 아니라 optional_properties라 REQUIRED_GATE_PROPS엔 넣지 않고
        # (즉 없다고 0점 게이트가 발동하진 않음) 정확도를 채점에만 반영한다.
        # ⚠️ PDP의 WebPage,ItemPage 블록도 같은 optional_properties를 쓰므로, 이 항목들이
        # 이미 값이 채워져 있는 PDP 페이지에도 채점 대상으로 새로 포함된다. 배포 전 PDP
        # 몇 개를 먼저 돌려 기존에 숨어있던 mismatch가 없었는지 확인 권장.
        "mainEntity": 2, "hasPart": 2, "breadcrumb": 1,
    },
    "ItemList": {
        "numberOfItems": 4, "itemListElement": 4, "mainEntityOfPage": 3,
        "itemName_url": 2, "itemListOrder": 1,
    },
}

# 필수(Google 등급) 속성 — 0점이면 해당 블록 "필수 게이트" 발동(자격 소멸, 정보적합성 0%)
REQUIRED_GATE_PROPS: Dict[str, List[str]] = {
    "Product": ["name", "image"],
    "3DModel": ["encoding_contentUrl", "encoding_encodingFormat", "isPartOf", "about"],
    "VideoObject": ["name", "thumbnailUrl", "uploadDate", "contentUrlOrEmbedUrl"],
    "FAQPage": ["structure_valid"],
    "WebPage, ItemPage": ["type_combo", "name", "url"],
    "ItemList": ["numberOfItems", "itemListElement", "mainEntityOfPage"],
}

# Google 리치결과 공식 필수/권장 속성(정적 룰, 2026-07 Search Central 문서 기준).
# FAQPage는 2026-05-07 리치결과 폐지 → 이 표에서 제외(SEO 감점 미적용, 스키마 유효성만 참고).
GOOGLE_RICH_RESULT_REQUIRED = {
    "Product": ["name", "image"],
    "VideoObject": ["name", "thumbnailUrl", "uploadDate"],
}
GOOGLE_RICH_RESULT_RECOMMENDED = {
    "Product": ["description", "brand", "aggregateRating", "offers", "sku"],
    "VideoObject": ["description", "duration", "contentUrl", "embedUrl"],
}

# 리치결과 살아있는 타입 여부(엑셀 가이드 시트 근거)
RICH_RESULT_STATUS = {
    "Product": "정식", "VideoObject": "정식",
    "3DModel": "제한적(AR만)", "FAQPage": "폐지(2026-05-07)",
    "WebPage, ItemPage": "해당없음", "ItemList": "해당없음",
}


# ──────────────────────────────────────────────────────────────────
# 1) Level1 — 적용율 체크 (H1/H2/Meta/스키마 존재, 단순 로직)
# ──────────────────────────────────────────────────────────────────
def extract_html_signals(html: str) -> Dict[str, Any]:
    """붙여넣기/파일/URL 어느 입력이든 raw HTML만 있으면 동일하게 동작(크롤러 의존 없음)."""
    # [2026-07 FIX] 이 모듈만 표준 html.parser를 쓰고 있었다 — crawler.py/copy_checker.py/
    # compare_extractor.py/spec_extractor.py는 전부 lxml. html.parser는 lxml보다 엄격해서
    # 페이지 앞쪽의 사소한 마크업 오류(태그 안 닫힘 등) 하나로 그 뒤 파싱이 틀어지면 h3/h4처럼
    # 문서 하단부 태그를 통째로 못 찾을 수 있다 — 페이지소스엔 분명히 있는데 "없음"으로 뜨는 원인.
    # lxml은 그런 오류를 복구하고 계속 파싱하므로 나머지 모듈과 동일하게 맞춘다.
    soup = BeautifulSoup(html or "", "lxml")
    title_tag = soup.find("title")
    md = soup.find("meta", attrs={"name": "description"})
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
    # [신규] H3/H4도 화면(HtmlQaDetail)에 H1/H2 아래 순차 노출 — 채점 로직(apply_rate)에는
    # 관여하지 않는 표시 전용 시그널이라 여기서는 추출만 해둔다.
    h3s = [h.get_text(strip=True) for h in soup.find_all("h3")]
    h4s = [h.get_text(strip=True) for h in soup.find_all("h4")]
    return {
        "title": title_tag.get_text(strip=True) if title_tag else None,
        "meta_description": md.get("content", "").strip() if md else None,
        "h1_list": h1s,
        "h2_list": h2s,
        "h3_list": h3s,
        "h4_list": h4s,
    }


def level1_apply_rate(html: str, schema_rules: Dict[str, Any],
                       guide_h1_keywords: Optional[List[str]] = None,
                       guide_h2_min_count: Optional[int] = None,
                       title_max_len: int = 80, desc_max_len: int = 160,
                       title_warn_buffer: int = 10, desc_warn_buffer: int = 20) -> Dict[str, Any]:
    """가이드 적용율(%) = 실제 적용 항목 수 / 전체 항목 수.
    guide_h1_keywords/guide_h2_min_count는 마케팅 가이드 데이터가 있을 때만 채점(없으면 항목 자체를 건너뜀 — 거짓으로 O/X 매기지 않음)."""
    sig = extract_html_signals(html)
    items: List[Dict[str, Any]] = []

    h1_count = len(sig["h1_list"])
    items.append({"item": "H1 존재(1개)", "pass": h1_count == 1,
                  "detail": f"h1 {h1_count}개 발견"})

    if guide_h1_keywords:
        h1_text = " ".join(sig["h1_list"]).lower()
        hit = any(k.lower() in h1_text for k in guide_h1_keywords)
        items.append({"item": "H1 가이드 키워드 포함", "pass": hit,
                      "detail": f"기대 키워드 {guide_h1_keywords}"})
    # guide_h1_keywords 없으면 항목 생성 안 함(가이드 데이터 미연결 상태를 숨기지 않음)

    if guide_h2_min_count is not None:
        h2_count = len(sig["h2_list"])
        items.append({"item": "H2 개수(가이드 대비)", "pass": h2_count >= guide_h2_min_count,
                      "detail": f"h2 {h2_count}개 / 가이드 {guide_h2_min_count}개 이상"})

    def _len_status(length: int, max_len: int, buffer: int) -> str:
        # 60자/160자는 구글의 실제 픽셀폭 절단 기준(언어·폰트별로 다름)을 근사한 가이드라인일 뿐,
        # 하드 스펙이 아니다. 소폭 초과(버퍼 이내)는 '확인'으로만 표시하고, 크게 초과할 때만
        # '오류'로 잡는다 — 스키마 누락 같은 실제 기술 오류와 같은 무게로 다루지 않기 위함.
        if length <= max_len:
            return "pass"
        if length <= max_len + buffer:
            return "warn"
        return "fail"

    title = sig["title"] or ""
    title_status = "fail" if not title else _len_status(len(title), title_max_len, title_warn_buffer)
    items.append({"item": "Meta Title 존재·길이", "pass": title_status != "fail", "status": title_status,
                  "detail": (f"길이 {len(title)}자(권장 ≤{title_max_len}자 · {title_max_len}~{title_max_len + title_warn_buffer}자는 확인 권장)"
                             if title else "누락")})

    desc = sig["meta_description"] or ""
    desc_status = "fail" if not desc else _len_status(len(desc), desc_max_len, desc_warn_buffer)
    items.append({"item": "Meta Description 존재·길이", "pass": desc_status != "fail", "status": desc_status,
                  "detail": (f"길이 {len(desc)}자(권장 ≤{desc_max_len}자 · {desc_max_len}~{desc_max_len + desc_warn_buffer}자는 확인 권장)"
                             if desc else "누락")})

    nodes = schema_checker.extract_jsonld(html)
    found_types = set()
    for n in nodes:
        found_types |= set(schema_checker._types_of(n))
    for block in schema_rules.get("blocks", []) or []:
        if block.get("conditional"):
            continue  # 조건부 블록은 적용율 분모에서 제외(엑셀 기준: 조건부=경고, 필수 산정 대상 아님)
        types = set(block.get("types", []))
        present = bool(types & found_types)
        items.append({"item": f"스키마 타입 존재: {block.get('name')}", "pass": present,
                      "detail": ", ".join(types)})

    total = len(items)
    passed = sum(1 for i in items if i["pass"])
    return {"items": items, "applied": passed, "total": total,
            "apply_rate_pct": round(100 * passed / total, 1) if total else None,
            "signals": {  # 화면에 실제 태깅된 값을 그대로 보여주기 위한 원본 리스트
                "title": sig["title"], "meta_description": sig["meta_description"],
                "h1_list": sig["h1_list"], "h2_list": sig["h2_list"],
                "h3_list": sig["h3_list"], "h4_list": sig["h4_list"],
            }}


# ──────────────────────────────────────────────────────────────────
# 2) Level2 · 축2 — 파싱에러 + Google 리치결과 SEO 기준 (세분화)
# ──────────────────────────────────────────────────────────────────
_SYNTAX_CRITICAL = {"unbalanced", "missing_comma", "unescaped", "syntax"}
_SYNTAX_WARNING = {"trailing_comma", "smart_quote", "invisible_char"}


def axis2_parsing_and_rich_result(html: str, schema_result: Dict[str, Any],
                                   schema_type_list: List[str],
                                   rendered_by: Optional[str] = None) -> Dict[str, Any]:
    """schema_checker.check_page()의 findings를 재활용해 세분화된 오류 목록을 만든다.
    분류 3그룹: JSON-LD 문법 / Google 리치결과 SEO / 기타(구현보류 포함).

    ⚠ 게이트는 타입(블록)별로 따로 채점한다(엑셀 원본: 각 스키마 타입 시트마다 독립된 '축2' 섹션).
    JSON-LD 문법 오류는 어떤 스크립트 태그가 깨졌는지는 알아도 그 안에 어떤 타입이 있었는지는
    파싱이 안 돼서 알 수 없으므로, 그 자체로는 '어떤 타입'의 게이트도 무효화하지 않는다 —
    대신 findings에 이미 없는(=schema.missing) 타입은 axis1의 필수게이트(0%)로 이미 반영되고,
    실제로 정상 파싱된 타입(자기 블록을 찾은 타입)은 다른 스크립트 태그의 문법 오류로
    억울하게 0점 처리되지 않는다. 문법 오류 리스트 자체는 여전히 화면에 그대로 노출한다."""
    syntax_errors: List[Dict[str, Any]] = []
    by_type: Dict[str, Dict[str, Any]] = {t: {"critical": 0, "warning": 0, "detail": []} for t in schema_type_list}

    for f in schema_result.get("findings", []):
        if f.get("block") != "JSON-LD":
            continue
        cat = f.get("syntax_category", "syntax")
        sev = "Critical" if cat in _SYNTAX_CRITICAL else "Warning"
        syntax_errors.append({"group": "JSON-LD 문법 오류", "category": cat, "severity": sev,
                              "message": f.get("as_is", f.get("parse_msg", ""))})

    for f in schema_result.get("findings", []):
        block = f.get("block")
        if block == "JSON-LD" or block not in by_type:
            continue
        bucket = by_type[block]
        # 리치결과 필수 속성 '완전 누락' → Critical(게이트 무효). Google 문서: 필수속성 없으면 자격 상실.
        google_required = GOOGLE_RICH_RESULT_REQUIRED.get(block, [])
        hard_missing = [p for p in f.get("missing_props", []) if (not google_required) or (p in google_required)]
        # 리치결과 대상 타입(Product/VideoObject)은 Google 필수목록 기준, 그 외 타입은 가이드 필수(missing_props) 기준
        gate_missing = [p for p in f.get("missing_props", [])] if block not in GOOGLE_RICH_RESULT_REQUIRED else hard_missing
        if gate_missing:
            bucket["critical"] += 1
            bucket["detail"].append({"group": "Google 리치결과 SEO 기준", "category": "required_missing",
                                     "severity": "Critical", "block": block,
                                     "message": f"필수 속성 누락: {', '.join(gate_missing)}"})
        # 값 형식/불일치 → 품질 경고(Warning). 게이트를 죽이지 않음(값이 화면과 다르다는 감점 신호).
        if f.get("val_mismatch"):
            bucket["warning"] += 1
            props = ", ".join(str(vm.get("prop")) for vm in f["val_mismatch"])
            bucket["detail"].append({"group": "Google 리치결과 SEO 기준", "category": "value_mismatch",
                                     "severity": "Warning", "block": block,
                                     "message": f"값 불일치/형식 확인 필요: {props}"})
        if f.get("optional_missing"):
            bucket["warning"] += 1
            bucket["detail"].append({"group": "Google 리치결과 SEO 기준", "category": "recommended_missing",
                                     "severity": "Warning", "block": block,
                                     "message": f"권장 속성 누락: {', '.join(f['optional_missing'])}"})
        # hasPart 참조 누락 → 경고(연결 설계 이슈, 무결성은 축3에서 별도 게이트)
        if f.get("haspart_missing"):
            bucket["warning"] += 1
            bucket["detail"].append({"group": "@id 연결", "category": "haspart_missing",
                                     "severity": "Warning", "block": block,
                                     "message": f"hasPart 참조 미검출: {f['haspart_missing']}"})

    for t, bucket in by_type.items():
        bucket["gate"] = 0 if bucket["critical"] > 0 else 1

    rich_result_scope = {t: RICH_RESULT_STATUS.get(t, "해당없음") for t in schema_type_list}

    other = []
    if rendered_by:
        other.append({"category": "rendered_parse_ok",
                      "status": "OK" if "playwright" in rendered_by else "미확인(playwright 미사용)"})

    page_has_critical_syntax = any(e["severity"] == "Critical" for e in syntax_errors)
    return {"syntax_errors": syntax_errors, "by_type": by_type,
            "page_has_critical_syntax": page_has_critical_syntax,  # 참고용 — 특정 타입 게이트를 강제로 0으로 만들진 않음
            "critical_count": sum(b["critical"] for b in by_type.values()) + sum(1 for e in syntax_errors if e["severity"] == "Critical"),
            "warning_count": sum(b["warning"] for b in by_type.values()) + sum(1 for e in syntax_errors if e["severity"] == "Warning"),
            "rich_result_scope": rich_result_scope, "other": other}


# ──────────────────────────────────────────────────────────────────
# 3) Level2 · 축3 — @id 연결성 (페이지 전역, 1회)
# ──────────────────────────────────────────────────────────────────
_ABS_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def _all_ids(value: Any) -> List[str]:
    out = []
    if isinstance(value, dict):
        v = value.get("@id")
        if isinstance(v, list):
            out += [str(x) for x in v]
        elif v is not None:
            out.append(str(v))
    elif isinstance(value, list):
        for it in value:
            out += _all_ids(it)
    elif isinstance(value, str):
        out.append(value)
    return out


def axis3_id_linkage(html: str, required_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """@id 연결성. required_types = 가이드가 요구하는 핵심 스키마 타입(페이지 룰 기반).
    @id 부여율/형식은 '전체 노드'가 아니라 '가이드 필수 타입 노드'만 대상으로 채점한다
    (배너/breadcrumb 등 부가 노드에 @id 없다고 감점하지 않음 → '가이드만 준수하면 100%')."""
    nodes = schema_checker.extract_jsonld(html)
    checks: List[Dict[str, Any]] = []

    # 가이드 핵심 타입(없으면 통상적인 핵심 엔티티 기본값)
    CORE = set(required_types or ["Product", "VideoObject", "3DModel", "FAQPage",
                                  "WebPage", "ItemPage", "ItemList", "Organization", "Brand"])

    def _is_core(n):
        return bool(set(schema_checker._types_of(n)) & CORE)

    core_nodes = [n for n in nodes if _is_core(n)]
    core_with_id = [n for n in core_nodes if n.get("@id")]
    node_ids = {str(n.get("@id")) for n in nodes if n.get("@id")}

    # [2026-07 과제4] @id가 없는 핵심 노드를 "무엇이 누락됐는지" 알아볼 수 있게 목록화한다.
    #   기존엔 'X/Y' 카운트만 있어 프론트에서 어느 노드가 빠졌는지 알 수 없었다.
    #   각 항목: {"type": 대표 @type, "name": 식별용 name/헤드라인(있으면), "hint": URL 후보}
    def _id_hint(n: Dict[str, Any]) -> str:
        for k in ("url", "mainEntityOfPage", "contentUrl", "target"):
            v = n.get(k)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, dict) and isinstance(v.get("@id"), str):
                return v["@id"]
        return ""

    missing_id_nodes = [n for n in core_nodes if not n.get("@id")]
    missing_ids = [{
        "type": "/".join(schema_checker._types_of(n)) or "(unknown)",
        "name": str(n.get("name") or n.get("headline") or "")[:80],
        "hint": _id_hint(n),
    } for n in missing_id_nodes]

    # @id 부여율 — 핵심 노드가 하나도 없으면 '해당없음'(None), 있으면 그 노드들 기준
    if core_nodes:
        rate_score = 1.0 if len(core_with_id) == len(core_nodes) else (0.5 if core_with_id else 0.0)
        _detail = f"핵심 노드 {len(core_with_id)}/{len(core_nodes)}에 @id 존재"
        if missing_ids:
            _detail += " · 누락: " + ", ".join(
                (m["type"] + (f'({m["name"]})' if m["name"] else "")) for m in missing_ids)
        checks.append({"item": "@id 부여율", "weight": 3, "score": rate_score,
                       "detail": _detail, "missing_ids": missing_ids})
    else:
        checks.append({"item": "@id 부여율", "weight": 3, "score": None, "detail": "핵심 스키마 없음(해당없음)",
                       "missing_ids": []})

    core_ids = {str(n.get("@id")) for n in core_with_id}
    invalid_fmt = [i for i in core_ids if not _ABS_URL_RE.match(i)]
    if core_ids:
        checks.append({"item": "@id 형식 유효성", "weight": 2,
                      "score": 1.0 if not invalid_fmt else 0.0,
                      "detail": f"비정상 형식 {len(invalid_fmt)}건" if invalid_fmt else "전부 절대 URI"})
    else:
        checks.append({"item": "@id 형식 유효성", "weight": 2, "score": None, "detail": "해당없음"})

    # v0.9: @id 연결성은 '존재 여부(부여율·형식)'만 본다. 연결관계(Product↔Video/3D/FAQ)·
    # 참조 무결성·유일성 등 상세 항목은 채점에서 제외(가이드만 준수하면 되도록 완화).
    # 게이트도 없음 — @id 때문에 페이지 전체 점수를 0으로 만들지 않는다.
    scored = [c for c in checks if c["score"] is not None]
    total_w = sum(c["weight"] for c in scored)
    pct = round(100 * sum(c["weight"] * c["score"] for c in scored) / total_w, 1) if total_w else None

    return {"checks": checks, "id_pct": pct, "gate": 1,
            "missing_ids": missing_ids,
            "id_coverage": {"with_id": len(core_with_id), "total": len(core_nodes)}}


# ──────────────────────────────────────────────────────────────────
# 4) Level2 · 축1 — 정보 적합성(%) — schema_checker 결과를 채점표 가중치로 환산
# ──────────────────────────────────────────────────────────────────
def _prop_score(f: Dict[str, Any], prop_hint: str) -> float:
    """schema_checker의 finding(블록 단위)에서 특정 항목의 근사 점수(0/0.5/1)를 추정.
    채점표 키(encoding_contentUrl 등)를 schema_checker가 다루는 실제 속성명으로 정규화해서 대조."""
    # 채점표 세부 키 → schema_checker가 리포트하는 실제 스키마 속성명
    ALIAS = {
        "encoding_contentUrl": "encoding", "encoding_encodingFormat": "encoding",
        "gltf": "encoding", "usdz": "encoding",
        "contentUrlOrEmbedUrl": "contentUrl", "contentUrlAndEmbedUrl": "contentUrl",
        "hasPartOrSeek": "hasPart", "type_combo": "@type",
        "structure_valid": "mainEntity", "screen_match": "mainEntity",
        "itemName_url": "itemListElement", "primaryImage": "primaryImageOfPage",
    }
    targets = [prop_hint, ALIAS.get(prop_hint, prop_hint)]

    def _hit(coll_key: str, field: str = "prop") -> bool:
        for x in f.get(coll_key, []):
            val = x if isinstance(x, str) else str(x.get(field, ""))
            if any(t == val or t in val for t in targets):
                return True
        return False

    if _hit("missing_props") or any(t in p for t in targets for p in f.get("missing_props", [])):
        return 0.0
    if _hit("val_mismatch"):
        return 0.5
    if _hit("name_issue"):
        return 0.0
    if _hit("optional_missing") or any(t in p for t in targets for p in f.get("optional_missing", [])):
        return 0.5
    # translate_confirm은 '값이 존재하나 현지어 번역을 사람이 확인 권장'하는 안내일 뿐 —
    # 값 자체는 있으므로 감점하지 않는다(과거 0.5로 깎아 present 속성이 '누락'으로 표시되던 버그 수정).
    return 1.0


def axis1_info_adequacy(schema_result: Dict[str, Any], block_name: str,
                        rule_props: Optional[set] = None) -> Optional[Dict[str, Any]]:
    """block_name은 AXIS1_WEIGHTS의 키(예: 'Product'). 해당 블록 finding을 찾아 가중합(%) 계산.
    rule_props가 주어지면, 그 페이지 룰에 실제로 존재하는 속성만 채점 대상으로 한다
    (예: flagship PDP엔 offers/sku가 없으므로 Simple 전용 속성을 채점에서 제외 — 오인식 방지).
    필수 게이트: REQUIRED_GATE_PROPS 중 하나라도 0점이면 이 블록 정보적합성=0(자격 소멸)."""
    all_weights = AXIS1_WEIGHTS.get(block_name)
    if not all_weights:
        return None
    # 채점표 키 → 실제 스키마 속성명(alias)로 되돌려, 룰에 있는 속성만 남긴다
    ALIAS_TO_SCHEMA = {
        "encoding_contentUrl": "encoding", "encoding_encodingFormat": "encoding",
        "gltf": "encoding", "usdz": "encoding",
        "contentUrlOrEmbedUrl": "contentUrl", "contentUrlAndEmbedUrl": "contentUrl",
        "hasPartOrSeek": "hasPart", "type_combo": "@type",
        "structure_valid": "mainEntity", "screen_match": "mainEntity",
        "itemName_url": "itemListElement", "primaryImage": "primaryImageOfPage",
    }
    if rule_props is not None:
        def _in_rule(k):
            base = ALIAS_TO_SCHEMA.get(k, k)
            # FAQPage 재환산 키(structure_valid/screen_match)와 항상 유지 대상은 통과
            if k in ("structure_valid", "screen_match"):
                return True
            return base in rule_props or k in rule_props
        weights = {k: w for k, w in all_weights.items() if _in_rule(k)}
        if not weights:  # 룰과 교집합이 없으면 원본 가중치로 폴백(안전)
            weights = all_weights
    else:
        weights = all_weights

    f = next((x for x in schema_result.get("findings", []) if x.get("block") == block_name), None)
    if f is None or f.get("code") == "schema.missing":
        return None

    props_score = {}
    for prop in weights:
        if block_name == "FAQPage" and prop == "screen_match":
            # 마크업↔화면 일치는 렌더 없이 자동 검증 불가 → '수동 확인 필요'로 0.5 고정(자동 만점 금지)
            props_score[prop] = 0.5
        else:
            props_score[prop] = _prop_score(f, prop)
    required = [p for p in REQUIRED_GATE_PROPS.get(block_name, []) if p in weights]
    hard_missing = set(f.get("missing_props", []))
    gate_triggered = any(p in hard_missing for p in required)  # 표시용 플래그(점수엔 미반영)

    total_w = sum(weights.values())
    weighted = sum(weights[p] * props_score[p] for p in weights)
    # 게이트 제거(v1.0): 필수 누락도 그 속성 0점(가중치 감점)으로만 반영 — pct를 강제 0으로 만들지 않음.
    pct = round(100 * weighted / total_w, 1) if total_w else None

    return {"pct": pct, "gate_triggered": gate_triggered, "props": props_score,
            "weights": weights, "required": required}


# ──────────────────────────────────────────────────────────────────
# 5) 종합 — 2단계 서머리
# ──────────────────────────────────────────────────────────────────
def traffic_light(final_pct: Optional[float], any_gate_zero: bool) -> str:
    if any_gate_zero or final_pct is None:
        return "red"
    if final_pct >= 80:
        return "green"
    if final_pct >= 50:
        return "yellow"
    return "red"


def score_html_qa(html: str, schema_rules: Dict[str, Any], schema_result: Dict[str, Any],
                   rendered_by: Optional[str] = None,
                   guide_h1_keywords: Optional[List[str]] = None,
                   guide_h2_min_count: Optional[int] = None) -> Dict[str, Any]:
    """1단계(적용율%) + 2단계(AEO 퀄리티 점수, 타입별) 를 합쳐 리턴.
    schema_result는 schema_checker.check_page(html, schema_rules, ...) 결과를 그대로 받는다(재계산 안 함)."""
    schema_types_in_rules = [b.get("name") for b in (schema_rules.get("blocks") or [])]

    level1 = level1_apply_rate(html, schema_rules,
                               guide_h1_keywords=guide_h1_keywords,
                               guide_h2_min_count=guide_h2_min_count)
    axis2 = axis2_parsing_and_rich_result(html, schema_result, schema_types_in_rules, rendered_by=rendered_by)
    # 가이드 룰의 실제 타입(@type)만 핵심으로 → @id 부여율/형식을 그 노드들만 대상으로
    rule_types = []
    for b in (schema_rules.get("blocks") or []):
        rule_types += b.get("types", [])
    axis3 = axis3_id_linkage(html, required_types=rule_types or None)

    # 블록명 → 그 룰의 실제 속성 집합(required ∪ optional) 매핑
    rule_props_by_block = {}
    for b in (schema_rules.get("blocks") or []):
        rule_props_by_block[b.get("name")] = set(b.get("required_properties", [])) | set(b.get("optional_properties", []))

    per_type = {}
    for name in AXIS1_WEIGHTS:
        if name not in schema_types_in_rules:
            continue
        a1 = axis1_info_adequacy(schema_result, name, rule_props=rule_props_by_block.get(name))
        if a1 is None:
            continue  # 페이지에 없는 타입 → 해당없음, 평균에서 제외
        rich_status = RICH_RESULT_STATUS.get(name, "해당없음")
        raw_axis2_gate = axis2.get("by_type", {}).get(name, {}).get("gate", 1)
        apply_axis2 = rich_status in ("정식", "제한적(AR만)")
        eff_axis2_gate = raw_axis2_gate if apply_axis2 else 1
        # 게이트 곱셈 제거(v1.0): 크리티컬(필수 누락·파싱 실패)도 속성 가중치 감점으로만 반영.
        # 최종 = 정보적합성(%) 그대로. 게이트 값은 '표시용 경고'로만 payload에 남긴다.
        final_pct = a1["pct"]

        # 표현용 집계(이미 계산된 a1.props를 세기만 함 — 점수 로직/값은 그대로).
        props = a1.get("props", {})
        required = set(a1.get("required", []))
        req_props = [p for p in props if p in required]
        rec_props = [p for p in props if p not in required]
        req_ok = sum(1 for p in req_props if props[p] >= 1.0)
        rec_ok = sum(1 for p in rec_props if props[p] >= 1.0)
        # 부족/확인 속성(사용자가 먼저 봐야 할 것): 필수 미충족 먼저, 그다음 권장
        missing_required = [p for p in req_props if props[p] < 1.0]
        weak_recommended = [p for p in rec_props if props[p] < 1.0]

        per_type[name] = {
            "axis1_info_adequacy_pct": a1["pct"],
            "axis1_gate_triggered": a1["gate_triggered"],
            "axis2_gate": eff_axis2_gate,
            "rich_result_status": rich_status,
            "final_pct": final_pct,
            "traffic_light": traffic_light(final_pct, False),
            # ── 표현용(요구사항: 개수/부족항목/수정위치) ──
            "required_total": len(req_props),
            "required_ok": req_ok,
            "recommended_total": len(rec_props),
            "recommended_ok": rec_ok,
            "missing_required": missing_required,
            "weak_recommended": weak_recommended,
            "prop_detail": [{"prop": p, "score": props[p]} for p in props],
        }

    overall_final = None
    if per_type:
        vals = [v["final_pct"] for v in per_type.values() if v["final_pct"] is not None]
        overall_final = round(sum(vals) / len(vals), 1) if vals else None

    any_type_gate_zero = any(v.get("axis2_gate") == 0 for v in per_type.values())
    # 상단 '데이터 유무 (충족/전체)' — 모든 타입의 속성을 합산(충족=score>=1)
    prop_total = sum(v["required_total"] + v["recommended_total"] for v in per_type.values())
    prop_ok = sum(v["required_ok"] + v["recommended_ok"] for v in per_type.values())
    return {
        "level1_apply_rate": level1,
        "level2": {
            "axis2_parsing_rich_result": axis2,
            "axis3_id_linkage": axis3,
            "per_type": per_type,
        },
        "overall": {
            "final_pct": overall_final,
            "traffic_light": traffic_light(overall_final, False),
            "prop_ok": prop_ok,
            "prop_total": prop_total,
        },
    }


if __name__ == "__main__":
    import json
    import runner
    html = open("/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()
    rules = runner.load_rules("M3", page_type="PDP", market_product="galaxy-s26-ultra")
    sres = schema_checker.check_page(html, rules["schema"])
    out = score_html_qa(html, rules["schema"], sres)
    print(json.dumps(out, ensure_ascii=False, indent=2)[:4000])

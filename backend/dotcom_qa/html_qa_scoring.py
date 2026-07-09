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
        "encoding_contentUrl": 4, "encoding_encodingFormat": 3,
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
    "WebPage,ItemPage": {
        "type_combo": 4, "name": 3, "url": 3, "description": 1, "primaryImage": 1,
    },
    "ItemList": {
        "numberOfItems": 4, "itemListElement": 4, "mainEntityOfPage": 3,
        "itemName_url": 2, "itemListOrder": 1,
    },
}

# 필수(Google 등급) 속성 — 0점이면 해당 블록 "필수 게이트" 발동(자격 소멸, 정보적합성 0%)
REQUIRED_GATE_PROPS: Dict[str, List[str]] = {
    "Product": ["name", "image"],
    "3DModel": ["encoding_contentUrl", "encoding_encodingFormat"],
    "VideoObject": ["name", "thumbnailUrl", "uploadDate", "contentUrlOrEmbedUrl"],
    "FAQPage": ["structure_valid"],
    "WebPage,ItemPage": ["type_combo", "name", "url"],
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
    "WebPage,ItemPage": "해당없음", "ItemList": "해당없음",
}


# ──────────────────────────────────────────────────────────────────
# 1) Level1 — 적용율 체크 (H1/H2/Meta/스키마 존재, 단순 로직)
# ──────────────────────────────────────────────────────────────────
def extract_html_signals(html: str) -> Dict[str, Any]:
    """붙여넣기/파일/URL 어느 입력이든 raw HTML만 있으면 동일하게 동작(크롤러 의존 없음)."""
    soup = BeautifulSoup(html or "", "html.parser")
    title_tag = soup.find("title")
    md = soup.find("meta", attrs={"name": "description"})
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
    return {
        "title": title_tag.get_text(strip=True) if title_tag else None,
        "meta_description": md.get("content", "").strip() if md else None,
        "h1_list": h1s,
        "h2_list": h2s,
    }


def level1_apply_rate(html: str, schema_rules: Dict[str, Any],
                       guide_h1_keywords: Optional[List[str]] = None,
                       guide_h2_min_count: Optional[int] = None,
                       title_max_len: int = 60, desc_max_len: int = 160) -> Dict[str, Any]:
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

    title = sig["title"] or ""
    items.append({"item": "Meta Title 존재·길이", "pass": bool(title) and len(title) <= title_max_len,
                  "detail": f"길이 {len(title)}자(기준 ≤{title_max_len})" if title else "누락"})

    desc = sig["meta_description"] or ""
    items.append({"item": "Meta Description 존재·길이", "pass": bool(desc) and len(desc) <= desc_max_len,
                  "detail": f"길이 {len(desc)}자(기준 ≤{desc_max_len})" if desc else "누락"})

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
    분류 3그룹: JSON-LD 문법 / Google 리치결과 SEO / 기타(구현보류 포함)."""
    detail: List[Dict[str, Any]] = []
    critical = warning = 0

    for f in schema_result.get("findings", []):
        if f.get("block") != "JSON-LD":
            continue
        cat = f.get("syntax_category", "syntax")
        sev = "Critical" if cat in _SYNTAX_CRITICAL else "Warning"
        (critical := critical + 1) if sev == "Critical" else (warning := warning + 1)
        detail.append({"group": "JSON-LD 문법 오류", "category": cat, "severity": sev,
                       "message": f.get("as_is", f.get("parse_msg", ""))})

    for f in schema_result.get("findings", []):
        if f.get("block") == "JSON-LD":
            continue
        block = f.get("block")
        # Google 등급과 무관하게, 우리 가이드가 필수로 본 항목이 없으면 그 자체로 Critical(가이드∪Google, 더 엄격 쪽 채택)
        if f.get("missing_props"):
            critical += 1
            detail.append({"group": "Google 리치결과 SEO 기준", "category": "required_missing",
                           "severity": "Critical", "block": block,
                           "message": f"필수 속성 누락: {', '.join(f['missing_props'])}"})
        if f.get("val_mismatch"):
            critical += 1
            detail.append({"group": "Google 리치결과 SEO 기준", "category": "value_format_error",
                           "severity": "Critical", "block": block,
                           "message": f"필수 속성 값 형식/불일치: {f['val_mismatch']}"})
        if f.get("optional_missing"):
            warning += 1
            detail.append({"group": "Google 리치결과 SEO 기준", "category": "recommended_missing",
                           "severity": "Warning", "block": block,
                           "message": f"권장 속성 누락: {', '.join(f['optional_missing'])}"})
        if f.get("haspart_missing"):
            critical += 1
            detail.append({"group": "JSON-LD 문법 오류", "category": "unrecognized_reference",
                           "severity": "Critical", "block": block,
                           "message": f"hasPart 참조 누락: {f['haspart_missing']}"})

    rich_result_scope = {t: RICH_RESULT_STATUS.get(t, "해당없음") for t in schema_type_list}

    # 구현 안 된 항목(무효속성/이미지해상도)은 결과에 넣지 않음 — 없는 걸 있는 것처럼 보여주지 않음.
    # rendered_by 정보가 실제로 있을 때만 렌더링 파싱 결과를 포함.
    other = []
    if rendered_by:
        other.append({"category": "rendered_parse_ok",
                      "status": "OK" if "playwright" in rendered_by else "미확인(playwright 미사용)"})

    gate = 0 if critical > 0 else 1
    return {"critical_count": critical, "warning_count": warning, "gate": gate,
            "detail": detail, "rich_result_scope": rich_result_scope, "other": other}


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


def axis3_id_linkage(html: str) -> Dict[str, Any]:
    nodes = schema_checker.extract_jsonld(html)
    checks: List[Dict[str, Any]] = []

    node_ids = {str(n.get("@id")) for n in nodes if n.get("@id")}
    id_rate = round(100 * len(node_ids) / len(nodes), 1) if nodes else 0.0
    checks.append({"item": "@id 부여율", "weight": 3, "score": 1.0 if nodes and len(node_ids) == len(nodes) else (0.5 if node_ids else 0.0),
                  "detail": f"{len(node_ids)}/{len(nodes)} 노드에 @id 존재"})

    invalid_fmt = [i for i in node_ids if not _ABS_URL_RE.match(i)]
    checks.append({"item": "@id 형식 유효성", "weight": 2,
                  "score": 1.0 if node_ids and not invalid_fmt else (0.0 if invalid_fmt else 0.5),
                  "detail": f"비정상 형식 {len(invalid_fmt)}건" if invalid_fmt else "전부 절대 URI"})

    def type_ids(*types):
        return {str(n.get("@id")) for n in nodes if set(schema_checker._types_of(n)) & set(types) and n.get("@id")}

    product_ids = type_ids("Product")
    video_ids = type_ids("VideoObject")
    model_ids = type_ids("3DModel")
    faq_ids = type_ids("FAQPage")

    referenced: set = set()
    for n in nodes:
        if set(schema_checker._types_of(n)) & {"Product"}:
            referenced |= set(_all_ids(n.get("subjectOf")))

    v_linked = len(referenced & video_ids)
    checks.append({"item": "Product ↔ VideoObject", "weight": 4,
                  "score": (v_linked / len(video_ids)) if video_ids else None,
                  "detail": f"{v_linked}/{len(video_ids) or 0} 연결" if video_ids else "VideoObject 없음(해당없음)"})

    m_linked = 1.0 if (referenced & model_ids) else (0.0 if model_ids else None)
    checks.append({"item": "Product ↔ 3DModel", "weight": 3, "score": m_linked,
                  "detail": "연결됨" if (referenced & model_ids) else ("미연결" if model_ids else "3DModel 없음(해당없음)")})

    f_linked = 1.0 if (referenced & faq_ids) else (0.0 if faq_ids else None)
    checks.append({"item": "Product ↔ FAQPage", "weight": 2, "score": f_linked,
                  "detail": "연결됨" if (referenced & faq_ids) else ("미연결" if faq_ids else "FAQPage 없음(해당없음)")})

    # 참조 무결성(dangling) — subjectOf/mainEntity/mainEntityOfPage/hasPart 참조 대상이 실제 존재하는지
    dangling = []
    for n in nodes:
        for key in ("subjectOf", "mainEntity", "mainEntityOfPage", "hasPart"):
            for ref in _all_ids(n.get(key)):
                if ref and ref not in node_ids and _ABS_URL_RE.match(ref):
                    dangling.append({"from": n.get("@id"), "key": key, "ref": ref})
    checks.append({"item": "참조 무결성(dangling 없음) ★게이트", "weight": 4,
                  "score": 0.0 if dangling else 1.0, "detail": f"끊어진 참조 {len(dangling)}건" if dangling else "전부 유효"})

    dup = [i for i in node_ids if list(node_ids).count(i) > 1]  # node_ids는 set이라 항상 0 — 원본 리스트로 재계산
    raw_ids = [str(n.get("@id")) for n in nodes if n.get("@id")]
    dup_ids = {i for i in raw_ids if raw_ids.count(i) > 1}
    # 같은 @id가 서로 다른 @type 조합에 쓰였는지(충돌)만 문제로 봄(단순 반복 참조는 정상)
    conflict = False
    seen_types: Dict[str, set] = {}
    for n in nodes:
        nid = str(n.get("@id")) if n.get("@id") else None
        if not nid:
            continue
        t = frozenset(schema_checker._types_of(n))
        if nid in seen_types and seen_types[nid] != t:
            conflict = True
        seen_types[nid] = t
    checks.append({"item": "@id 유일성(중복·충돌 없음)", "weight": 2,
                  "score": 0.0 if conflict else 1.0, "detail": "충돌 발견" if conflict else "충돌 없음"})

    scored = [c for c in checks if c["score"] is not None]
    total_w = sum(c["weight"] for c in scored)
    pct = round(100 * sum(c["weight"] * c["score"] for c in scored) / total_w, 1) if total_w else None
    gate = 0 if dangling else 1

    return {"checks": checks, "id_pct": pct, "gate": gate, "dangling": dangling}


# ──────────────────────────────────────────────────────────────────
# 4) Level2 · 축1 — 정보 적합성(%) — schema_checker 결과를 채점표 가중치로 환산
# ──────────────────────────────────────────────────────────────────
def _prop_score(f: Dict[str, Any], prop_hint: str) -> float:
    """schema_checker의 finding(블록 단위)에서 특정 항목의 근사 점수(0/0.5/1)를 추정."""
    if any(prop_hint in p for p in f.get("missing_props", [])):
        return 0.0
    if any(prop_hint in str(vm.get("prop", "")) for vm in f.get("val_mismatch", [])):
        return 0.0
    if any(prop_hint in str(n.get("prop", "")) for n in f.get("name_issue", [])):
        return 0.0
    if any(prop_hint in str(tc.get("prop", "")) for tc in f.get("translate_confirm", [])):
        return 0.5
    if any(prop_hint in p for p in f.get("optional_missing", [])):
        return 0.5
    return 1.0


def axis1_info_adequacy(schema_result: Dict[str, Any], block_name: str) -> Optional[Dict[str, Any]]:
    """block_name은 AXIS1_WEIGHTS의 키(예: 'Product'). 해당 블록 finding을 찾아 가중합(%) 계산.
    필수 게이트: REQUIRED_GATE_PROPS 중 하나라도 0점이면 이 블록 정보적합성=0(자격 소멸)."""
    weights = AXIS1_WEIGHTS.get(block_name)
    if not weights:
        return None
    f = next((x for x in schema_result.get("findings", []) if x.get("block") == block_name), None)
    if f is None or f.get("code") == "schema.missing":
        # 블록 자체가 페이지에 없음(schema_checker가 node=None으로 판정) → 속성 채점 자체가 무의미, 즉시 0%
        return {"pct": 0.0, "gate_triggered": True, "reason": "블록 자체가 페이지에 없음", "props": {}}

    props_score = {prop: _prop_score(f, prop) for prop in weights}
    required = REQUIRED_GATE_PROPS.get(block_name, [])
    gate_triggered = any(props_score.get(p, 0.0) == 0.0 for p in required)

    total_w = sum(weights.values())
    weighted = sum(weights[p] * props_score[p] for p in weights)
    pct = 0.0 if gate_triggered else round(100 * weighted / total_w, 1) if total_w else None

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
    axis3 = axis3_id_linkage(html)

    per_type = {}
    for name in AXIS1_WEIGHTS:
        if name not in schema_types_in_rules:
            continue
        a1 = axis1_info_adequacy(schema_result, name)
        if a1 is None or a1["pct"] is None:
            continue
        final_pct = None
        if a1["pct"] is not None:
            final_pct = round(axis2["gate"] * axis3["gate"] * a1["pct"], 1)
        per_type[name] = {
            "axis1_info_adequacy_pct": a1["pct"],
            "axis1_gate_triggered": a1["gate_triggered"],
            "final_pct": final_pct,
            "traffic_light": traffic_light(final_pct, axis2["gate"] == 0 or axis3["gate"] == 0 or a1["gate_triggered"]),
        }

    overall_final = None
    if per_type:
        vals = [v["final_pct"] for v in per_type.values() if v["final_pct"] is not None]
        overall_final = round(sum(vals) / len(vals), 1) if vals else None

    return {
        "level1_apply_rate": level1,
        "level2": {
            "axis2_parsing_rich_result": axis2,
            "axis3_id_linkage": axis3,
            "per_type": per_type,
        },
        "overall": {
            "final_pct": overall_final,
            "traffic_light": traffic_light(overall_final, axis2["gate"] == 0 or axis3["gate"] == 0),
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

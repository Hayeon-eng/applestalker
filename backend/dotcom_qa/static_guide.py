"""
static_guide.py — 공통페이지 QA · 오류 유형별 as-is/to-be 수정 가이드 + 페이지/권역 집계 [2026-09-14 신규]

이 모듈은 판정을 바꾸지 않는다. static_qa.check_static_page() 결과(status·category·reasons·parse_errors 등)를
사람이 바로 조치할 수 있는 "지금 상태(as-is) → 이렇게 고치세요(to-be)" 문장으로 바꾸고,
run 결과 전체를 페이지별·권역(subs)별 정상/오류 비율로 집계한다.
"""
from __future__ import annotations
from typing import Any, Dict, List

# 상태별 기본 가이드 (as_is / to_be / who = 조치 주체)
STATUS_GUIDE: Dict[str, Dict[str, str]] = {
    "정상": {"as_is": "스키마가 모두 읽히고 전형적 오류가 없습니다.", "to_be": "조치 불필요.", "who": "-"},
    "파싱 실패": {
        "as_is": "일부 JSON-LD 블록이 문법 오류로 검색엔진에 읽히지 않습니다. 그 블록의 구조화 데이터는 리치결과에 반영되지 않습니다.",
        "to_be": "아래 블록별 원인(줄:칸)대로 HTML 의 <script type=\"application/ld+json\"> 내용을 고쳐 배포하세요. 대부분 스마트따옴표·비표시문자·괄호/쉼표 문제입니다.",
        "who": "퍼블리싱/개발"},
    "오적용": {
        "as_is": "스키마의 @id·url 에 다른 국가 사이트 주소가 섞여 있습니다(예: ca_fr 페이지가 /ca/ 를 가리킴). 검색엔진이 엉뚱한 페이지를 정본으로 인식할 수 있습니다.",
        "to_be": "해당 값의 사이트코드 경로를 이 페이지의 사이트코드로 통일하세요(공용 리소스 이미지 등 의도된 글로벌 경로는 예외).",
        "who": "개발"},
    "미해결 참조": {
        "as_is": "스키마가 가리키는 @id 가 이 페이지 안에 정의되어 있지 않습니다(hasPart/mainEntity 등). 노드 연결이 끊겨 리치결과가 불완전해질 수 있습니다.",
        "to_be": "참조하는 @id 노드를 같은 페이지에 정의하거나, 참조를 실제 존재하는 @id 로 수정하세요.",
        "who": "개발"},
    "페이지 없음": {
        "as_is": "이 국가에 해당 페이지가 없거나(404) 안내 페이지로 이동합니다.",
        "to_be": "그 국가에 페이지가 실제로 없으면 검수 대상에서 제외, 있는데 주소가 다르면 실제 주소를 담당자에게 알려 등록하세요.",
        "who": "운영"},
    "접근 실패": {
        "as_is": "403/429/네트워크 오류로 페이지를 가져오지 못했습니다. 사이트 문제가 아니라 수집 환경(프록시·인증서·차단) 문제일 수 있습니다.",
        "to_be": "PC 프로그램(exe)에서 재시도하세요(사내 인증서 자동 인식). 계속되면 config.json 의 ca_bundle_path 지정 또는 잠시 후 재수집.",
        "who": "운영"},
    "기타": {
        "as_is": "중복 @id, Google 리치결과 필수 속성 누락, 또는 스키마가 하나도 없습니다.",
        "to_be": "중복 @id 는 하나로 합치고, 누락된 필수 속성(아래 표시)을 채우세요. 스키마가 없으면 페이지에 JSON-LD 를 추가하세요.",
        "who": "개발"},
}

# 파싱 실패 세부 유형별 to-be (schema_checker 의 category 와 1:1)
PARSE_GUIDE: Dict[str, str] = {
    "smart_quote": "스마트 따옴표(“ ” ‘ ’)를 일반 따옴표(\")로 모두 바꾸세요. 편집기 자동 교정을 끄면 재발을 막습니다.",
    "invisible_char": "비표시 문자(줄바꿈 없는 공백 NBSP·제로폭 문자·BOM)를 제거하세요. 값에 눈에 안 보이는 문자가 섞인 경우입니다.",
    "missing_comma": "항목 사이 쉼표(,)를 넣으세요.",
    "trailing_comma": "마지막 항목 뒤의 불필요한 쉼표를 지우세요.",
    "unbalanced": "여는/닫는 괄호({ } [ ])와 따옴표 개수를 맞추세요.",
    "unescaped": "값 안의 따옴표·특수문자를 이스케이프(\\\") 하세요.",
    "syntax": "JSON 구조(중괄호·대괄호·콜론·쉼표)를 검토하세요.",
}


def cell_guide(cell: Dict[str, Any]) -> Dict[str, Any]:
    """한 셀(사이트×페이지) 결과 → as-is/to-be 가이드. parse_errors 가 있으면 블록별 세부 to-be 를 붙인다."""
    st = cell.get("status", "기타")
    base = STATUS_GUIDE.get(st, STATUS_GUIDE["기타"])
    g = {"status": st, "as_is": base["as_is"], "to_be": base["to_be"], "who": base["who"], "fixes": []}
    for pe in cell.get("parse_errors", []):
        if pe.get("severity", "fail") == "warn":
            continue
        cat = pe.get("category", "syntax")
        g["fixes"].append({"block": pe.get("block"), "category": cat, "where": (f"{pe.get('line')}:{pe.get('col')}" if pe.get("line") else ""),
                           "to_be": PARSE_GUIDE.get(cat, PARSE_GUIDE["syntax"])})
    for u in cell.get("foreign_refs", [])[:5]:
        g["fixes"].append({"block": "@id/url", "category": "foreign_ref", "where": u,
                           "to_be": "이 값의 국가 경로를 페이지 사이트코드로 통일(글로벌 공용 리소스는 예외)."})
    for m in cell.get("rich_missing", [])[:5]:
        g["fixes"].append({"block": m.get("type"), "category": "rich_missing", "where": ", ".join(m.get("missing", [])),
                           "to_be": f"{m.get('type')} 에 필수 속성({', '.join(m.get('missing', []))})을 추가."})
    for d in cell.get("duplicate_ids", [])[:5]:
        g["fixes"].append({"block": "@id", "category": "duplicate", "where": d, "to_be": "같은 @id 노드를 하나로 합치기."})
    return g


def _ratio(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    ok = sum(1 for r in rows if r["status"] == "정상")
    err = sum(1 for r in rows if r["status"] in ("파싱 실패", "오적용", "미해결 참조", "기타"))
    miss = sum(1 for r in rows if r["status"] in ("페이지 없음", "접근 실패"))
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    return {"total": total, "ok": ok, "err": err, "na": miss,
            "ok_pct": round(100 * ok / total) if total else 0,
            "err_pct": round(100 * err / total) if total else 0,
            "by_status": by}


def summarize(results: List[Dict[str, Any]], sites_meta: List[Dict[str, Any]]) -> Dict[str, Any]:
    """페이지별·권역(subs)별 정상/오류 비율. sites_meta 로 sitecode→subs 매핑."""
    subs_of = {s["sitecode"]: s.get("subs") or "-" for s in sites_meta}
    by_page: Dict[str, Any] = {}
    by_region: Dict[str, Any] = {}
    for r in results:
        by_page.setdefault(r.get("page_label") or r.get("page"), []).append(r)
        reg = subs_of.get(r["sitecode"], "-")
        by_region.setdefault(reg, []).append(r)
    return {
        "by_page": {k: _ratio(v) for k, v in sorted(by_page.items())},
        "by_region": {k: _ratio(v) for k, v in sorted(by_region.items(), key=lambda kv: -_ratio(kv[1])["err"])},
        "overall": _ratio(results),
    }

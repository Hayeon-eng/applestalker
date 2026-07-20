"""
qa_report_helpers.py — 큐비 — Excel/메일 리포트 공용 헬퍼 (qa_report.py 분할 1/3)

[2026-07 파일 분할] qa_report.py가 46KB를 넘어 파일 크기 제한에 걸려 4개 파일로 쪼갰다.
기능은 전혀 바꾸지 않았고 그냥 위치만 옮겼다(순수 mechanical split) — 아래 3개로 나뉜다:
  · qa_report_helpers.py (이 파일) — 텍스트/타입 판정 헬퍼 + JSON-LD 코드 조각 생성기
  · qa_report_rows.py    — schema/html_qa 결과 → Excel 행(row) 변환
  · qa_report_xlsx.py    — build_xlsx() 본체(시트 2개 작성)
  · qa_report.py          — 위 3개를 모아 기존과 동일한 공개 API(build_xlsx/summary_counts/
    build_email_draft)를 그대로 제공하는 얇은 진입점. 외부에서는 지금까지처럼
    `import qa_report; qa_report.build_xlsx(...)` 그대로 쓰면 된다 — 호출부 변경 불필요.
"""
from __future__ import annotations
import io
import json
import copy
import difflib
import re
from datetime import datetime
from typing import Any, Dict, List

from qa_messages import render

MARK = {"pass": "O", "warn": "△", "fail": "X", "-": "-"}
MARK_COLOR = {"pass": "1F9E5C", "warn": "E0A008", "fail": "D8362F", "-": "98A2B3"}
SEV_KO = {"fail": "오류", "warn": "확인", "pass": "정상", "info": "참고(사전)"}
SEV_COLOR = {"fail": "D8362F", "warn": "E0A008", "pass": "1F9E5C", "info": "98A2B3"}
_TYPE_ORDER = ["WebPage", "ItemList", "Product", "3DModel", "ImageObject", "VideoObject", "FAQPage", "BreadcrumbList"]
_WORST = {"pass": 0, "warn": 1, "fail": 2}


def _primary_type(f):
    t = f.get("types")
    if isinstance(t, list) and t:
        return "WebPage" if t[0] in ("WebPage", "ItemPage") else t[0]
    return (f.get("block", "Other") or "Other").split(",")[0].strip()


def _worse(a, b):
    return a if _WORST.get(a, 0) >= _WORST.get(b, 0) else b


def _page_type(url):
    u = (url or "").lower()
    if "/compare" in u:
        return "Compare"
    if "/buy" in u:
        return "Buying"
    return "PDP"


def _en(f):
    """finding → 영어 (as_is, to_be). code 있으면 카탈로그로, 없으면 원문."""
    if f.get("code"):
        m = render(f["code"], "en", f)
        return m["as_is"], m["to_be"]
    return f.get("as_is", ""), f.get("to_be", "")


def _flatten(page_results, tab=None):
    """검수 결과를 이슈 행으로 평탄화.
    tab="schema" → 스키마 이슈만 · tab="copy" → 스펙(spec_v2/copy) 이슈만 · None → 전체(Excel·요약용).
    Data QA(스키마)와 Spec QA(스펙)는 독자가 달라(SEO담당 vs 마케팅담당), 메일은 보고 있던 탭 것만 담는다."""
    want_schema = tab in (None, "schema")
    want_spec = tab in (None, "copy")
    rows = []
    for pr in page_results:
        base = {"sitecode": pr.get("sitecode", ""), "url": pr.get("url", ""),
                "region": pr.get("region", ""), "country": pr.get("country", "")}
        if want_schema:
            for f in (pr.get("schema") or {}).get("findings", []):
                if f.get("status") == "pass":
                    continue
                rows.append({**base, "area": "Schema", "item": f.get("block", ""),
                             "status": f.get("status"), "f": f})
        if want_spec:
            sv = pr.get("spec_v2")
            if sv:
                # [V2 정합 — 2026-07 리팩토링] Critical=fail(실제 Spec 오류),
                # Warning=warn(값은 찾았으나 추출 신뢰도가 낮아 재확인 필요한 항목).
                # Dictionary(미등록 표현)는 보조 기능이므로 Critical/Warning 집계에서 완전히
                # 분리한다 — status를 "info"로 둬서 summary_counts(fail/warn만 집계)에 잡히지
                # 않게 하고, 화면에서도 항상 별도의 접힌 섹션에서만 보여준다.
                for it in sv.get("items", []):
                    if it.get("status") not in ("fail", "warn"):
                        continue
                    exp = f'{it.get("expected", "")}{(" " + it["unit"]) if it.get("unit") else ""}'
                    rows.append({**base, "area": "Spec", "item": it.get("attribute", ""),
                                 "status": it["status"],
                                 "f": {"status": it["status"],
                                       "as_is": f'현재 {it.get("found") or "(페이지에 없음)"}',
                                       "to_be": f'기준 {exp}' + (f' — {it["fix_guide"]}' if it.get("fix_guide") else "")}})
                # Dictionary Review는 보조 정보 — fail/warn 집계에 섞이지 않도록 status="info"
                for c in sv.get("dictionary_review", []) or []:
                    rows.append({**base, "area": "Spec·Dictionary(보조)", "item": c.get("alias", ""),
                                 "status": "info",
                                 "f": {"status": "info",
                                       "as_is": f'미등록 표현(제품 내 {c.get("count","?")}개 페이지 반복, confidence={c.get("confidence","")})',
                                       "to_be": "번역/표기 확인 후 Dictionary 추가로 승인 (선택)"}})
            else:
                for f in (pr.get("copy") or {}).get("findings", []):
                    if f.get("status") == "pass":
                        continue
                    rows.append({**base, "area": "Copy·" + (f.get("kind", "") or ""), "item": f.get("token", ""),
                                 "status": f.get("status"), "f": f})
    return rows


def summary_counts(page_results):
    rows = _flatten(page_results)
    return {"pages": len(page_results),
            "fail": sum(1 for r in rows if r["status"] == "fail"),
            "warn": sum(1 for r in rows if r["status"] == "warn"),
            "issues": len(rows)}


def _schema_row(pr):
    type_status, as_is, to_be = {}, [], []
    for f in (pr.get("schema") or {}).get("findings", []):
        ty = _primary_type(f)
        type_status[ty] = _worse(type_status.get(ty, "pass"), f.get("status", "pass"))
        if f.get("status") != "pass":
            a, t = _en(f)
            if a:
                as_is.append(f"[{ty}] {a}")
            if t:
                to_be.append(f"[{ty}] {t}")
    return type_status, as_is, to_be


def _copy_row(pr):
    findings = (pr.get("copy") or {}).get("findings", [])
    summ = (pr.get("copy") or {}).get("summary", {})
    spec_total = summ.get("spec_total", 0)
    noun_total = summ.get("noun_total", 0)
    ks_total = summ.get("keyspec_total", 0)
    spec_miss = [f.get("token") for f in findings if f.get("kind") == "spec" and f.get("status") != "pass"]
    noun_miss = [f.get("token") for f in findings if f.get("kind") == "proper_noun" and f.get("status") != "pass"]
    val_issues, guides = [], []
    for f in findings:
        if f.get("kind") == "spec_value" and f.get("status") != "pass":
            a, t = _en(f)
            val_issues.append(a)
            guides.append(t)
    if spec_miss:
        guides.append("Verify these spec values appear on the page: " + ", ".join(map(str, spec_miss)))
    if noun_miss:
        guides.append("Check if these proper nouns were localized/omitted: " + ", ".join(map(str, noun_miss)))
    return {
        "spec_res": f"{spec_total - len(spec_miss)}/{spec_total}", "spec_miss": spec_miss,
        "noun_res": f"{noun_total - len(noun_miss)}/{noun_total}", "noun_miss": noun_miss,
        "val_res": f"{ks_total - len(val_issues)}/{ks_total}", "val_issues": val_issues,
        "guide": "\n".join(guides),
    }


SEV_EN = {"fail": "Error", "warn": "Check", "na": "N/A", "pass": "OK"}
SEV_COLOR2 = {"fail": "D8362F", "warn": "E0A008", "na": "98A2B3", "pass": "1F9E5C", "info": "98A2B3"}


# ── 작업자용 상세 행 빌더 — 대시보드(QubiDataQa)와 동일한 정보 밀도로 Excel 행 생성 ──
# 속성별 '수정 위치·영향' 사전(화면 PROP_HELP의 영어판 — 표현 전용, 점수 로직과 무관)
PROP_HELP_EN = {
    "name": ("Product name (name)", "Product rich result cannot be generated without a name"),
    "image": ("Main image (image)", "Rich result may not be shown without an image"),
    "brand": ("Brand (brand)", "Improves trust and entity matching"),
    "manufacturer": ("Manufacturer (manufacturer)", "Reinforces manufacturer info"),
    "potentialAction": ("Buy action (potentialAction)", "Links the purchase action"),
    "subjectOf": ("Link declaration (subjectOf)", "Declares links to Video/3D/FAQ nodes"),
    "offers": ("Price & availability (offers)", "Price/stock info — required on standalone PDP"),
    "sku": ("Product identifier (sku)", "Product identifier"),
    "structure_valid": ("FAQ structure validity", "Q&A structure must be valid to be recognized as FAQ"),
    "screen_match": ("On-screen match", "Markup must match visible Q&A content"),
    "type_combo": ("Type declaration (@type)", "Required @type combination must be declared"),
    "url": ("URL (url)", "Must match the canonical URL"),
    "numberOfItems": ("Item count (numberOfItems)", "Declared count must equal actual items"),
    "itemListElement": ("List items (itemListElement)", "List items must be complete"),
    "mainEntityOfPage": ("Page link (mainEntityOfPage)", "Cross-links the node with the page"),
    "encoding_contentUrl": ("3D file URL (encoding.contentUrl)", "Path to the 3D model file"),
    "encoding_encodingFormat": ("3D format (encoding.encodingFormat)", "Must be a valid 3D MIME type"),
    "thumbnailUrl": ("Thumbnail (thumbnailUrl)", "Video thumbnail"),
    "uploadDate": ("Upload date (uploadDate)", "ISO8601 upload date"),
    "contentUrlOrEmbedUrl": ("Video URL (contentUrl/embedUrl)", "Playable video path"),
    "duration": ("Duration (duration)", "Video length (PT#S)"),
    "description": ("Description (description)", "Summary description"),
}


def _prop_help(prop, type_name=""):
    label, why = PROP_HELP_EN.get(prop, (prop, ""))
    where = f"JSON-LD -> {type_name or '(node)'} -> {prop.replace('_', '.')}"
    return label, where, why


def _clip(s, n=160):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ── 붙여넣을 수 있는 JSON-LD 코드 조각 생성 ─────────────────────────
# 룰의 expected_values(value/kind/nested)를 실제 JSON-LD 프로퍼티 문자열로 변환한다.
# {SITECODE}/{BCP47-LANG} 등 플레이스홀더는 검수 대상 sitecode로 최대한 치환하고,
# 치환 못 하는 값은 <PLACEHOLDER> 형태로 남겨 작업자가 채우도록 한다.
def _fill_placeholders(text, pr):
    s = str(text)
    sc = pr.get("sitecode") or ""
    if sc:
        s = s.replace("{SITECODE}", sc)
    # 안내성 꼬리말(FAQ inLanguage의 *Refer to… 등) 제거
    if "*Refer to" in s:
        s = s.split("*Refer to")[0].strip()
    return s


def _prop_snippet(prop, spec, pr, indent=""):
    """expected_values의 한 항목(spec)을 JSON-LD 프로퍼티 한 줄(또는 블록)로.
    반환: '"prop": …,' 형태의 문자열(끝 콤마 포함)."""
    kind = spec.get("kind"); nested = spec.get("nested")
    val = _fill_placeholders(spec.get("value", ""), pr)

    def q(v):
        return '"' + str(v).replace('"', '\\"') + '"'

    # nested @id → {"@id": "…"} / nested @type → {"@type": "…"}
    if nested == "@id":
        return f'{indent}{q(prop)}: {{ "@id": {q(val)} }},'
    if nested == "@type":
        # 배열형(mainEntity: [{"@type":"Question", …}]) — 최소 골격 제시
        return f'{indent}{q(prop)}: [ {{ "@type": {q(val)}, "name": "<...>", "acceptedAnswer": {{ "@type": "Answer", "text": "<...>" }} }} ],'
    if kind == "enum":
        return f'{indent}{q(prop)}: {q(val)},'
    if kind == "url" or kind == "text" or kind == "exist" or kind is None:
        if not val or val.startswith("<"):
            return f'{indent}{q(prop)}: "<{prop}>",'
        return f'{indent}{q(prop)}: {q(val)},'
    if kind == "duration_fmt":
        return f'{indent}{q(prop)}: "PT#S",'
    if kind == "image_path":
        return f'{indent}{q(prop)}: "<image-url>",'
    if kind == "name_token":
        return f'{indent}{q(prop)}: {q(val)},'
    return f'{indent}{q(prop)}: {q(val)},'


def _fix_code_for_missing(prop, f, pr):
    """누락 속성 하나 — 블록 안에 추가할 한 줄(붙여넣을 최종 코드)."""
    spec = (f.get("rule_expected") or {}).get(prop)
    if spec:
        return _prop_snippet(prop, spec, pr).strip()
    return f'"{prop}": "<{prop}>",'


def _fix_code_for_block_missing(f, pr):
    """블록 자체가 없을 때 — 통째로 붙여넣을 최소 JSON-LD 스크립트."""
    types = f.get("rule_types") or f.get("types") or []
    type_str = types[0] if len(types) == 1 else types
    idp = _fill_placeholders(f.get("rule_id_pattern") or "", pr)
    exp = f.get("rule_expected") or {}
    req = f.get("rule_required") or list(exp.keys())
    lines = ['<script type="application/ld+json">', "{", '  "@context": "https://schema.org",']
    lines.append(f'  "@type": {json.dumps(type_str, ensure_ascii=False)},')
    if idp:
        lines.append(f'  "@id": "{idp}",')
    for prop in req:
        if prop in ("@context", "@type", "@id"):
            continue
        spec = exp.get(prop)
        if spec:
            lines.append("  " + _prop_snippet(prop, spec, pr))
        else:
            lines.append(f'  "{prop}": "<{prop}>",')
    # 마지막 프로퍼티의 후행 콤마 제거
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].rstrip().endswith(","):
            lines[i] = lines[i].rstrip()[:-1]
            break
    lines += ["}", "</script>"]
    return "\n".join(lines)


def _fix_code_for_value(prop, expected):
    """값 불일치/제품명/@id — 이 속성을 이 값으로 교체(최종 코드 한 줄)."""
    return f'"{prop}": "' + str(expected).replace('"', '\\"') + '"'


# ── [2026-07 신규] AS-IS 전체 블록 ↔ TO-BE 전체 블록 비교(하연 요청 — "코드가 어디 붙는지
# 모르겠다"는 피드백에 대응). 한 줄짜리 코드 조각 대신, 페이지에 실제로 있는 JSON-LD
# 블록 전체(raw)를 기준으로 고쳐야 할 속성만 바꾼 전체 블록을 나란히 보여준다. ──
def _parse_raw_node(f: Dict[str, Any]):
    """finding의 f['raw'](AS-IS 전체 블록 JSON 문자열)를 dict로 복원. 실패 시 None."""
    raw = f.get("raw") if f else None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _set_nested(obj: Dict[str, Any], dotted_prop: str, value: Any) -> None:
    """'encoding_contentUrl' 같은 '_' 구분 경로를 실제 중첩 dict 구조(encoding.contentUrl)에 반영.
    _prop_help()의 표시 규칙(prop.replace('_','.'))과 동일한 구분자를 쓴다."""
    parts = dotted_prop.split("_")
    cur = obj
    for i, p in enumerate(parts):
        if i == len(parts) - 1:
            cur[p] = value
        else:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt


def _code_pair_diff(as_is_obj, to_be_obj):
    """실제 페이지의 전체 블록(as_is_obj)과, 이 속성만 고친 전체 블록(to_be_obj)을 나란히
    비교 — 엑셀에서 달라진 줄만 빨간색으로 강조해서 그린다."""
    return {"mode": "diff", "as_is": as_is_obj, "to_be": to_be_obj}


def _code_pair_new_block(code: str):
    """블록 자체가 페이지에 없을 때 — 통째로 붙여넣을 새 블록(비교 대상 없음)."""
    return {"mode": "new_block", "code": code}


def _code_pair_text(as_is_text: str, to_be_text: str):
    """JSON 노드를 못 얻은 경우(파싱 실패/HTML 레벨 이슈/확인만 필요)의 일반 텍스트 대응."""
    return {"mode": "text", "as_is": as_is_text, "to_be": to_be_text}


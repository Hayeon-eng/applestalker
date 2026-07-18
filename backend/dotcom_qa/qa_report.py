"""
qa_report.py — 큐비 — Dotcom QA 체커 [Phase G]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

Excel 리포트(시트 2개) — QA 관례에 맞춰 전체 영어로 출력.
  · Schema QA : URL 1줄 = 타입별 O/△/X + Findings(as-is) + TO-BE guide
  · Copy QA   : URL 1줄 = spec/noun/value 결과 + 누락·불일치 + TO-BE guide
메일 초안(HTML)은 화면 흐름과 동일하게 한국어 유지.
문구는 qa_messages.render(code, 'en'/'ko', finding) 으로 렌더.
"""
from __future__ import annotations
import io
import json
import copy
import difflib
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



def _html_qa_rows(pr):
    """html_qa(대시보드 'HTML 검수' 카드)를 작업자용 영어 행으로.
    화면(HtmlQaDetail)과 동일 판정: Title<=60, Description<=160, H1==1, H2>=1.
    현재 태깅 값 전체를 As-Is에 그대로 노출해 바로 수정 가능하게 한다."""
    hq = pr.get("html_qa") or {}
    sig = ((hq.get("level1_apply_rate") or {}).get("signals")) or {}
    if not sig:
        return []
    rows = []
    title = sig.get("title") or ""
    desc = sig.get("meta_description") or ""
    h1s = sig.get("h1_list") or []
    h2s = sig.get("h2_list") or []

    # [2026-07 FIX] 60/160자는 구글의 실제 픽셀폭 절단 기준을 근사한 가이드라인이라, 소폭
    # 초과(버퍼 이내)까지 스키마 누락과 동일하게 'fail'로 잡으면 실제 기술 오류와 구분이
    # 안 된다. html_qa_scoring.level1_apply_rate와 동일한 완충 규칙을 적용한다.
    TITLE_WARN_BUFFER, DESC_WARN_BUFFER = 10, 20
    if not title:
        as_is, to_be = "(missing) — no <title> tag found", '<title>Samsung Galaxy S26 Ultra | Samsung <REGION></title>'
        rows.append(("HTML", "Meta Title", "title", "fail", as_is,
                     "Add a <title> tag (<= 60 chars) summarizing the page",
                     "<head> -> <title>", "Title shown in search / AI answers",
                     to_be, _code_pair_text(as_is, to_be)))
    elif len(title) > 60 + TITLE_WARN_BUFFER:
        as_is = f"Current title ({len(title)} chars, limit 60): \"{title}\""
        to_be = '<title><... <= 60 chars ...></title>'
        rows.append(("HTML", "Meta Title", "title", "fail", as_is,
                     "Shorten <title> to <= 60 chars, keeping product name + key value prop",
                     "<head> -> <title>", "Title shown in search / AI answers",
                     to_be, _code_pair_text(as_is, to_be)))
    elif len(title) > 60:
        as_is = f"Current title ({len(title)} chars, guideline 60): \"{title}\""
        to_be = '<title><... ~60 chars recommended ...></title>'
        rows.append(("HTML", "Meta Title", "title", "warn", as_is,
                     "Consider shortening <title> toward 60 chars (not a hard requirement, may be truncated in display)",
                     "<head> -> <title>", "Title shown in search / AI answers",
                     to_be, _code_pair_text(as_is, to_be)))
    if not desc:
        as_is = "(missing) — no meta[name=description] found"
        to_be = '<meta name="description" content="<... <= 160 chars ...>">'
        rows.append(("HTML", "Meta Description", "meta_description", "fail", as_is,
                     "Add meta[name=description] (<= 160 chars) summarizing the page",
                     "<head> -> meta[name=description]", "Snippet shown in search / AI answers",
                     to_be, _code_pair_text(as_is, to_be)))
    elif len(desc) > 160 + DESC_WARN_BUFFER:
        as_is = f"Current description ({len(desc)} chars, limit 160): \"{_clip(desc, 200)}\""
        to_be = '<meta name="description" content="<... <= 160 chars ...>">'
        rows.append(("HTML", "Meta Description", "meta_description", "fail", as_is,
                     "Shorten meta description to <= 160 chars",
                     "<head> -> meta[name=description]", "Snippet shown in search / AI answers",
                     to_be, _code_pair_text(as_is, to_be)))
    elif len(desc) > 160:
        as_is = f"Current description ({len(desc)} chars, guideline 160): \"{_clip(desc, 200)}\""
        to_be = '<meta name="description" content="<... ~160 chars recommended ...">'
        rows.append(("HTML", "Meta Description", "meta_description", "warn", as_is,
                     "Consider shortening meta description toward 160 chars (not a hard requirement)",
                     "<head> -> meta[name=description]", "Snippet shown in search / AI answers",
                     to_be, _code_pair_text(as_is, to_be)))
    if len(h1s) != 1:
        cur = "(none found)" if not h1s else f"{len(h1s)} H1 tags: " + " | ".join(f"\"{_clip(h, 60)}\"" for h in h1s[:5])
        if not h1s:
            fix_c = '<h1>Galaxy S26 Ultra</h1>'
        else:
            # 첫 번째만 h1으로 유지, 나머지는 h2로 강등한 최종 마크업
            fix_c = "\n".join(
                (f'<h1>{_clip(h, 60)}</h1>' if i == 0 else f'<h2>{_clip(h, 60)}</h2>')
                for i, h in enumerate(h1s[:5]))
        rows.append(("HTML", "H1", "h1", "fail", cur,
                     "Use exactly one <h1> per page (main page heading)",
                     "Body -> <h1>", "Primary heading signal for search / AEO", fix_c,
                     _code_pair_text(cur, fix_c)))
    if len(h2s) == 0:
        as_is = "(none found) — 0 H2 tags"
        to_be = '<h2>Camera</h2>\n<h2>Battery</h2>\n<h2>Display</h2>'
        rows.append(("HTML", "H2", "h2", "fail", as_is,
                     "Add at least one <h2> section heading",
                     "Body -> <h2>", "Content structure signal for AEO",
                     to_be, _code_pair_text(as_is, to_be)))
    return rows


def _schema_detail_rows(pr):
    """schema findings를 대시보드 '판정 근거'와 동일 단위(속성 1개 = 1행)로 분해.
    현재값(As-Is) ↔ 기대값(To-Be)을 명시해 작업자가 바로 수정할 수 있게 한다.
    반환: (area, type, prop_item, status, as_is, to_be, loc, impact, fix_code, code_pair) 리스트
    + 이미 다룬 (type,prop) 집합.
    [2026-07 신규] code_pair — 페이지에 실제 있는 JSON-LD 블록 전체(raw)를 기준으로 그
    속성만 고친 전체 블록을 같이 실어서, "이 코드를 어디에 붙이는지" 자체를 없앤다."""
    rows, covered = [], set()
    for f in (pr.get("schema") or {}).get("findings", []):
        if f.get("status") not in ("fail", "warn"):
            continue
        name = f.get("block", "") or _primary_type(f)
        ty = _primary_type(f)
        sev = f.get("status")
        types = "/".join(f.get("types", []) or [])
        idslug = f.get("id_slug", "")
        structured = False
        node = _parse_raw_node(f)  # AS-IS 전체 블록(dict) — 없으면 None(블록 자체가 없거나 파싱 실패)

        code = f.get("code", "")
        if code == "schema.missing":
            structured = True
            cond = " (conditional — add if required for this locale)" if f.get("conditional") else ""
            new_block = _fix_code_for_block_missing(f, pr)
            rows.append(("Schema", ty, "@type", sev,
                         f"{name} schema not found on the page{cond}",
                         f"Add a {name} JSON-LD block with @type={types or name}" + (f", @id={idslug}" if idslug else ""),
                         "Add new <script type=\"application/ld+json\"> in <head>/<body>",
                         "Block missing — no rich result / AEO signal for this type",
                         new_block, _code_pair_new_block(new_block)))
            # [2026-07 FIX — 리포트 중복] 블록 자체가 없는데 그 블록의 속성 누락
            # (inLanguage/about 등)을 별도 행으로 또 내리면 "FAQPage 없음" + "FAQPage의
            # inLanguage 없음"이 모순처럼 겹친다. 블록 미존재 행의 Fix Code에 전체 템플릿이
            # 이미 들어가므로, 이 finding의 속성 단위 행은 전부 생략한다.
            for prop in (f.get("missing_props") or []):
                covered.add((ty, prop))
            covered.add((ty, "@id"))
            continue  # 아래 속성 단위 분해 루프를 건너뛴다
        if code == "schema.parse_error":
            structured = True
            ln, col = f.get("parse_lineno"), f.get("parse_colno")
            loc = f"JSON-LD script — line {ln}, col {col}" if ln else "JSON-LD script (position unknown)"
            line = f.get("parse_line", "")
            as_is = f"[Google Rich Result] JSON-LD {f.get('syntax_category', 'syntax')} error — {f.get('parse_msg', '')}"
            if line:
                as_is += f" · offending line: {_clip(line, 120)}"
            fix_c = f.get("syntax_hint") or "Fix commas / quotes / braces on this line"
            rows.append(("Schema", ty, "JSON-LD syntax", sev, as_is,
                         f.get("syntax_hint") or "Fix the syntax — check trailing commas / quotes / braces",
                         loc, "Whole block unparseable — every schema in it is ignored by Google", fix_c,
                         _code_pair_text(as_is, fix_c)))  # 파싱 자체가 안 되어 전체블록 비교 불가 — 텍스트 힌트로 대체

        if f.get("id_mismatch"):
            structured = True
            covered.add((ty, "@id"))
            want_id = _fill_placeholders(f.get("rule_id_pattern") or idslug or "", pr)
            as_is_txt = f"Current @id: '{f['id_mismatch']}'"
            to_be_txt = f"Set @id to match the '{idslug}' pattern" if idslug else "Fix @id to the guide pattern"
            if node is not None:
                to_be_obj = copy.deepcopy(node); to_be_obj["@id"] = want_id
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, "@id", sev, as_is_txt, to_be_txt,
                         f"JSON-LD -> {name} -> @id", "@id mismatch breaks node linkage (subjectOf/hasPart)",
                         _fix_code_for_value("@id", want_id), cp))
        for prop in (f.get("missing_props") or []):
            structured = True
            covered.add((ty, prop))
            label, where, why = _prop_help(prop, name)
            as_is_txt = "(missing) — property not present"
            to_be_txt = f"Add '{prop.replace('_', '.')}' to the {name} block"
            if node is not None:
                to_be_obj = copy.deepcopy(node)
                spec = (f.get("rule_expected") or {}).get(prop)
                val = _fill_placeholders(spec.get("value", ""), pr) if spec else f"<{prop}>"
                _set_nested(to_be_obj, prop, val)
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, label, sev, as_is_txt, to_be_txt, where, why,
                         _fix_code_for_missing(prop, f, pr), cp))
        for hp in (f.get("haspart_missing") or []):
            structured = True
            as_is_txt = f"hasPart is missing @id '{hp}'"
            to_be_txt = f"Add @id '{hp}' to Product.hasPart"
            if node is not None:
                to_be_obj = copy.deepcopy(node)
                hp_list = to_be_obj.get("hasPart")
                if not isinstance(hp_list, list):
                    hp_list = []; to_be_obj["hasPart"] = hp_list
                hp_list.append({"@id": hp})
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, "hasPart", sev, as_is_txt, to_be_txt,
                         "JSON-LD -> Product -> hasPart", "Declares the page's Video/3D/FAQ parts",
                         f'"hasPart": [ ...existing items..., {{ "@id": "{hp}" }} ]', cp))
        for vm in (f.get("val_mismatch") or []):
            structured = True
            prop = vm.get("prop", "")
            covered.add((ty, prop))
            label, where, _why = _prop_help(prop, name)
            as_is_txt = f"Current: '{_clip(vm.get('actual'), 180)}'"
            to_be_txt = f"Change to: '{_clip(vm.get('expected'), 180)}'"
            if node is not None:
                to_be_obj = copy.deepcopy(node)
                _set_nested(to_be_obj, prop, vm.get("expected", ""))
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, label, sev, as_is_txt, to_be_txt,
                         where, "Value differs from the global guide",
                         _fix_code_for_value(prop, vm.get("expected", "")), cp))
        for ni in (f.get("name_issue") or []):
            structured = True
            covered.add((ty, "name"))
            miss = ", ".join(ni.get("missing") or []); bad = ", ".join(ni.get("forbidden") or [])
            issues = []
            if miss:
                issues.append(f"required token '{miss}' missing")
            if bad:
                issues.append(f"wrong model token '{bad}' present")
            exp_name = _fill_placeholders(((f.get("rule_expected") or {}).get("name") or {}).get("value", ""), pr)
            as_is_txt = f"Current name: '{_clip(ni.get('actual'), 120)}' — " + " · ".join(issues)
            to_be_txt = ((f"Include '{miss}'" if miss else "") + (" and " if miss and bad else "") +
                         (f"remove '{bad}'" if bad else "") + " — correct to the official product name")
            new_name = exp_name or "<official product name>"
            if node is not None:
                to_be_obj = copy.deepcopy(node); to_be_obj["name"] = new_name
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, "Product name (name)", sev, as_is_txt, to_be_txt,
                         f"JSON-LD -> {name} -> name", "Wrong product name breaks entity matching",
                         _fix_code_for_value("name", new_name), cp))
        for li in (f.get("lang_issue") or []):
            structured = True
            as_is_txt = f"inLanguage '{li.get('actual')}' differs from site language '{li.get('expected')}'"
            to_be_txt = f"OK if intended localization; otherwise set to '{li.get('expected')}'"
            if node is not None:
                to_be_obj = copy.deepcopy(node); to_be_obj["inLanguage"] = li.get("expected", "")
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, "inLanguage", "warn", as_is_txt, to_be_txt,
                         f"JSON-LD -> {name} -> inLanguage", "Language signal consistency",
                         _fix_code_for_value("inLanguage", li.get("expected", "")), cp))
        for t in (f.get("translate_confirm") or []):
            structured = True
            as_is_txt = f"Current value: '{_clip(t.get('actual'), 140)}'"
            to_be_txt = f"Confirm '{t.get('prop', '')}' is correctly localized (not an error)"
            rows.append(("Schema", ty, f"{t.get('prop', '')} (translation check)", "warn",
                         as_is_txt, to_be_txt,
                         f"JSON-LD -> {name} -> {t.get('prop', '')}", "Localization confirmation",
                         "", _code_pair_text(as_is_txt, to_be_txt)))
        for prop in (f.get("array_where_object") or []):
            structured = True
            as_is_txt = f"'{prop}' is an array ([…]) — Google allows it, guide recommends a single object"
            to_be_txt = f"Prefer a single object for '{prop}' (not an error)"
            rows.append(("Schema", ty, prop, "warn", as_is_txt, to_be_txt,
                         f"JSON-LD -> {name} -> {prop}", "Guide-preferred shape",
                         f'"{prop}": {{ "@id": "..." }}', _code_pair_text(as_is_txt, to_be_txt)))

        if not structured:  # 구조화 필드가 없는 finding — 카탈로그/원문 영어 문구로 폴백
            a, t = _en(f)
            rows.append(("Schema", ty, str(f.get("block", "")), sev, a, t,
                         f"JSON-LD -> {name}", "", "", _code_pair_text(a, t)))
    return rows, covered


def _html_qa_schema_gap_rows(pr, covered):
    """html_qa.per_type의 필수 누락/권장 보강(대시보드 'Schema 검수' 카드) 중
    schema findings에서 아직 다루지 않은 속성만 행으로 추가(중복 방지 — 화면과 동일 로직).
    코드 조각은 해당 타입의 schema finding에서 rule_expected를 찾아 재사용."""
    rows = []
    # 타입별 rule_expected 캐시(코드 조각 생성용)
    rule_by_type = {}
    for f in (pr.get("schema") or {}).get("findings", []):
        rule_by_type[_primary_type(f)] = f
    per_type = (((pr.get("html_qa") or {}).get("level2")) or {}).get("per_type") or {}
    for ty, v in per_type.items():
        base_f = rule_by_type.get(ty, {})
        node = _parse_raw_node(base_f) if base_f else None
        for prop in (v.get("missing_required") or []):
            if (ty, prop) in covered:
                continue
            label, where, why = _prop_help(prop, ty)
            as_is_txt = "(missing/insufficient) — required property"
            to_be_txt = f"Add '{prop.replace('_', '.')}' to the {ty} block"
            if node is not None:
                to_be_obj = copy.deepcopy(node)
                spec = (base_f.get("rule_expected") or {}).get(prop)
                val = _fill_placeholders(spec.get("value", ""), pr) if spec else f"<{prop}>"
                _set_nested(to_be_obj, prop, val)
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, label, "fail", as_is_txt, to_be_txt, where, why,
                         _fix_code_for_missing(prop, base_f, pr), cp))
        for prop in (v.get("weak_recommended") or []):
            if (ty, prop) in covered:
                continue
            label, where, why = _prop_help(prop, ty)
            as_is_txt = "(missing/partial) — recommended property"
            to_be_txt = f"Consider adding '{prop.replace('_', '.')}' to raise the {ty} AEO score"
            if node is not None:
                to_be_obj = copy.deepcopy(node)
                spec = (base_f.get("rule_expected") or {}).get(prop)
                val = _fill_placeholders(spec.get("value", ""), pr) if spec else f"<{prop}>"
                _set_nested(to_be_obj, prop, val)
                cp = _code_pair_diff(node, to_be_obj)
            else:
                cp = _code_pair_text(as_is_txt, to_be_txt)
            rows.append(("Schema", ty, label, "warn", as_is_txt, to_be_txt, where, why,
                         _fix_code_for_missing(prop, base_f, pr), cp))
    return rows


def build_xlsx(page_results):
    """Excel 리포트 — 화면 탭과 동일한 2시트(전체 영어), 작업자가 바로 수정 가능한 상세 단위.
      · Sheet 1 "Data QA" : 속성 1개 = 1행. 현재값(As-Is) ↔ 수정 가이드(To-Be) + 수정 위치 + 영향
      · Sheet 2 "Spec QA" : 스펙/고유명사 1건 = 1행. 기준값 ↔ 페이지 실제값 + 수정 가이드
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont

    thin = Side(style="thin", color="E4E7EC"); border = Border(thin, thin, thin, thin)
    hfont = Font(bold=True, color="FFFFFF"); hfill = PatternFill("solid", fgColor="1B2A4A")

    def _hdr(ws):
        for c in ws[1]:
            c.font = hfont; c.fill = hfill
            c.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    def _finish(ws, widths, freeze):
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.border = border
                if c.alignment.horizontal is None:
                    c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = freeze

    def _mark_cell(ws, rn, col, sev):
        cell = ws.cell(row=rn, column=col)
        cell.value = MARK.get(sev, "-")
        cell.font = Font(bold=True, color=MARK_COLOR.get(sev, "98A2B3"))
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sev_rank = {"fail": 0, "warn": 1, "info": 2}
    SEV_LABEL = {"fail": "🔴 Must Fix", "warn": "🟡 Review", "info": "⚪ Dictionary(보조)"}

    # [2026-07 신규] 어떤 제품 건인지 한눈에 보이도록 — 슬러그를 사람이 읽는 이름으로.
    # qb_routes_manage._v2_label()과 동일한 규칙(최소 버전)을 여기서도 그대로 씀.
    _PRODUCT_KNOWN = {
        "galaxy-watch8": "Galaxy Watch8",
        "galaxy-watch-ultra": "Galaxy Watch Ultra",
    }

    def _product_label(slug: str) -> str:
        if not slug:
            return ""
        if slug in _PRODUCT_KNOWN:
            return _PRODUCT_KNOWN[slug]
        out = slug.replace("galaxy-z-", "Galaxy Z ").replace("galaxy-watch", "Galaxy Watch")
        out = out.replace("fold", "Fold").replace("flip", "Flip")
        return out

    def _meta(pr):
        return (pr.get("region", ""), pr.get("country", ""), pr.get("sitecode", ""),
                pr.get("page_type") or _page_type(pr.get("url", "")), pr.get("url", ""),
                _product_label(pr.get("product", "")))

    def _site_cell(region, country, site):
        # 'uk · U.K (EHQ)' 형태로 한 셀에 합침 — 컬럼 수 축소
        bits = [str(site or "")]
        tail = " · ".join(x for x in [country, region] if x)
        return bits[0] + (f"  ({tail})" if tail else "")

    mono = Font(name="Consolas", size=10)

    # [2026-07 신규] AS-IS/TO-BE 전체 블록을 나란히 비교 — 실제로 달라지는 줄만 빨간색으로.
    _RT_RED = InlineFont(rFont="Consolas", sz=9, color="FFD8362F", b=True)
    _RT_NORMAL = InlineFont(rFont="Consolas", sz=9)

    def _rich_lines(lines, changed_flags):
        if not lines:
            return CellRichText([TextBlock(_RT_NORMAL, "(빈 블록)")])
        items = []
        n = len(lines)
        for i, (line, ch) in enumerate(zip(lines, changed_flags)):
            text = (line if line != "" else " ") + ("\n" if i < n - 1 else "")
            items.append(TextBlock(_RT_RED if ch else _RT_NORMAL, text))
        return CellRichText(items)

    def _diff_pair_richtext(as_is_obj, to_be_obj):
        a_lines = json.dumps(as_is_obj, ensure_ascii=False, indent=2).splitlines()
        b_lines = json.dumps(to_be_obj, ensure_ascii=False, indent=2).splitlines()
        sm = difflib.SequenceMatcher(a=a_lines, b=b_lines, autojunk=False)
        a_changed = [False] * len(a_lines); b_changed = [False] * len(b_lines)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                for i in range(i1, i2):
                    a_changed[i] = True
                for j in range(j1, j2):
                    b_changed[j] = True
        return _rich_lines(a_lines, a_changed), _rich_lines(b_lines, b_changed)

    def _write_code_pair(ws, rn, col_as_is, col_to_be, code_pair):
        """AS-IS/TO-BE 두 컬럼에 code_pair를 그린다.
        · diff  : 실제 페이지의 전체 JSON-LD 블록 ↔ 그 속성만 고친 전체 블록, 달라진 줄만 빨간색
        · new_block : 블록 자체가 없음 — TO-BE에 통째로 붙여넣을 새 블록만
        · text  : JSON 노드가 없는 경우(HTML 레벨/파싱 실패/확인만 필요) 일반 문장 대응"""
        c_a = ws.cell(row=rn, column=col_as_is)
        c_b = ws.cell(row=rn, column=col_to_be)
        mode = (code_pair or {}).get("mode", "text")
        if mode == "diff":
            try:
                a_rt, b_rt = _diff_pair_richtext(code_pair["as_is"], code_pair["to_be"])
                c_a.value = a_rt; c_b.value = b_rt
            except Exception:
                c_a.value = json.dumps(code_pair["as_is"], ensure_ascii=False, indent=2)
                c_b.value = json.dumps(code_pair["to_be"], ensure_ascii=False, indent=2)
            c_a.font = mono; c_b.font = mono
        elif mode == "new_block":
            c_a.value = "(이 블록 자체가 페이지에 없음 — TO-BE를 통째로 새로 추가)"
            c_b.value = code_pair.get("code", "")
            c_a.font = Font(italic=True, size=10, color="98A2B3")
            c_b.font = mono
        else:
            c_a.value = code_pair.get("as_is", "") if code_pair else ""
            c_b.value = code_pair.get("to_be", "") if code_pair else ""
            c_a.font = Font(size=10)
            c_b.font = Font(size=10, color="067647", bold=True)
        c_a.alignment = Alignment(vertical="top", wrap_text=True)
        c_b.alignment = Alignment(vertical="top", wrap_text=True)

    wb = Workbook()

    # ── Sheet 1 — Data QA (Schema + HTML) ──
    #   제품 → 위치(Where) → 무엇이(Issue) → AS-IS 전체블록 → TO-BE 전체블록(달라진 줄 빨간색) → URL
    HEAD1 = ["#", "Product", "Site", "Where", "Severity", "Issue",
             "AS-IS (현재 전체 블록)", "TO-BE (수정 후 전체 블록)", "URL"]
    W1 = [4, 16, 20, 26, 12, 26, 55, 55, 38]
    ws = wb.active; ws.title = "Data QA"
    ws.append(HEAD1); _hdr(ws)
    data_rows = []
    for pr in page_results:
        meta = _meta(pr)
        srows, covered = _schema_detail_rows(pr)
        for r in srows + _html_qa_schema_gap_rows(pr, covered) + _html_qa_rows(pr):
            data_rows.append((meta,) + tuple(r))
    data_rows.sort(key=lambda r: (r[0][1] or "zz", r[0][2] or "", sev_rank.get(r[4], 9), r[1], r[2]))
    for n, (meta, area, ty, item, sev, a, t, loc, impact, fix_code, code_pair) in enumerate(data_rows, 1):
        region, country, site, ptype, url, product = meta
        where = loc or ty
        ws.append([n, product, _site_cell(region, country, site), where, "", f"{item}", "", "", url])
        rn = ws.max_row
        sc = ws.cell(row=rn, column=5); sc.value = SEV_LABEL.get(sev, sev)
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        _write_code_pair(ws, rn, 7, 8, code_pair)
    if not data_rows:
        ws.append(["—", "", "", "", "🟢 OK", "No issues found", "", "", ""])
    _finish(ws, W1, "A2")

    # ── Sheet 2 — Spec QA — 기준값 ↔ 페이지 실제값 (핵심 컬럼만) ──
    HEAD2 = ["#", "Product", "Site", "Where", "Severity", "Spec Item", "Expected (Guide)", "Found on Page", "URL"]
    W2 = [4, 16, 20, 22, 12, 22, 30, 32, 38]
    ws2 = wb.create_sheet("Spec QA")
    ws2.append(HEAD2); _hdr(ws2)
    KIND_EN = {"spec": "Spec", "proper_noun": "Proper Noun", "spec_value": "Spec Value"}
    spec_rows = []
    for pr in page_results:
        meta = _meta(pr)
        sv = pr.get("spec_v2")
        if sv:
            # [V2 정합 — 2026-07 리팩토링] Critical=fail, Warning=warn(재확인 필요,
            # 추출 신뢰도 낮음). Dictionary(미등록 표현)는 보조 기능이라 severity를
            # "info"로 분리해 Critical/Warning 집계·정렬 우선순위를 흐리지 않게 한다.
            for it in sv.get("items", []):
                if it.get("status") not in ("fail", "warn"):
                    continue
                item = it.get("attribute", "")
                exp = f'{it.get("expected", "")}{(" " + it["unit"]) if it.get("unit") else ""}'
                found_s = str(it.get("found") or "(not found on page)")
                loc = f'{it.get("page", "")}' + (f' > {it["section"]}' if it.get("section") else "")
                if it.get("fix_guide"):
                    exp = f'{exp}  ·  Fix: {it["fix_guide"]}'
                label = "Rule · " + it.get("rule_id", "") + (" (review — not a confirmed error)" if it.get("status") == "warn" else "")
                spec_rows.append((meta, label, item, it["status"], exp, found_s, loc or "PDP"))
            for c in sv.get("dictionary_review", []) or []:
                spec_rows.append((meta, "Dictionary(보조)", c.get("alias", ""), "info",
                                  f'제품 내 {c.get("count","?")}개 페이지 반복 · confidence={c.get("confidence","")} '
                                  "· 번역/표기 확인 후 Dictionary 추가로 승인(선택)",
                                  "(unmapped label)", "Spec"))
        else:
            for f in (pr.get("copy") or {}).get("findings", []):
                if f.get("status") not in ("fail", "warn"):
                    continue
                kind = KIND_EN.get(f.get("kind", ""), f.get("kind", "") or "Spec")
                item = f.get("token", "") or f.get("category", "")
                expected = str(f.get("expected", "") or f.get("token", "") or "")
                found = f.get("found") or []
                found_s = ", ".join(map(str, found[:6])) if found else "(not found on page)"
                loc = "Disclaimer" if f.get("region") == "disclaimer" else "Body"
                spec_rows.append((meta, kind, item, f.get("status"), expected, found_s, loc))
    spec_rows.sort(key=lambda r: (r[0][1] or "zz", r[0][2] or "", sev_rank.get(r[3], 9)))
    for n, (meta, kind, item, sev, exp, found, loc) in enumerate(spec_rows, 1):
        region, country, site, ptype, url, product = meta
        ws2.append([n, product, _site_cell(region, country, site), f"{kind} → {loc}", "",
                    str(item), exp, found, url])
        rn = ws2.max_row
        sc = ws2.cell(row=rn, column=5); sc.value = SEV_LABEL.get(sev, sev)
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
    if not spec_rows:
        ws2.append(["—", "", "", "", "🟢 OK", "No issues found", "", "", ""])
    _finish(ws2, W2, "A2")

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def build_email_draft(page_results, when="", tab=None):
    from html import escape
    rows = _flatten(page_results, tab=tab)
    s = {"pages": len(page_results),
         "fail": sum(1 for r in rows if r["status"] == "fail"),
         "warn": sum(1 for r in rows if r["status"] == "warn")}
    qa_label = {"schema": "Data QA (스키마·검색 노출)", "copy": "Spec QA (스펙 정확성)"}.get(tab, "QA")
    by_site = {}
    for r in rows:
        by_site.setdefault(r["sitecode"], []).append(r)
    blocks = ""
    for sc, items in by_site.items():
        meta = next((p for p in page_results if p.get("sitecode") == sc), {})
        lis = ""
        for it in items[:20]:
            col = "#" + SEV_COLOR.get(it["status"], "000000")
            a = it["f"].get("as_is", ""); t = it["f"].get("to_be", "")  # 메일은 한국어
            lis += ("<div style='font-size:12.5px;line-height:1.5;margin-top:6px'>"
                    "<span style='font-size:10.5px;font-weight:700;color:#fff;background:" + col + ";padding:2px 6px;border-radius:5px'>"
                    + SEV_KO.get(it["status"], "") + "</span> "
                    "<b style='color:#101318'>" + escape(it["area"]) + " · " + escape(str(it["item"])[:40]) + "</b>"
                    "<div style='color:#475467;margin-top:2px'>as-is: " + escape(a) + "</div>"
                    "<div style='color:#101318'>to-be: " + escape(t) + "</div></div>")
        blocks += ("<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px;margin-top:10px'>"
                   "<div style='font-size:13px;font-weight:800;color:#101318'>" + escape(sc) + " "
                   "<span style='font-weight:400;color:#667085;font-size:11px'>" + escape((meta.get("region") or "") + " · " + (meta.get("country") or "")) + "</span></div>"
                   "<div style='font-family:monospace;color:#98A2B3;font-size:10.5px;word-break:break-all;margin:2px 0 4px'>" + escape(meta.get("url", "")) + "</div>"
                   + lis + "</div>")
    if not blocks:
        blocks = "<p style='color:#1F9E5C'>검수한 페이지에서 오류가 발견되지 않았습니다.</p>"
    return ("<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'>"
            "<div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'>"
            "<div style='font-size:12px;color:#667085;font-weight:700'>큐비 🐝 — " + escape(qa_label) + " 리포트</div>"
            "<h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + "</h1>"
            "<div style='font-size:13px;color:#667085'>검수 " + str(s["pages"]) + "페이지 · 오류 " + str(s["fail"]) + "건 · 확인 " + str(s["warn"]) + "건</div>"
            "<div style='margin-top:14px'>" + blocks + "</div></div></div>")


if __name__ == "__main__":
    import json, re, sys
    sys.path.insert(0, ".")
    import schema_checker as sch, copy_checker as cop
    schema_rules = json.load(open("schema_rules.json", encoding="utf-8"))["products"]["M3"]
    copy_rules = json.load(open("copy_rules.json", encoding="utf-8"))["products"]["M3"]
    ks = json.load(open("key_specs.json", encoding="utf-8"))["products"]["galaxy-s26-ultra"]
    good = open("/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()
    bad = re.sub(r"31\s?hours", "29 hours", good, flags=re.I).replace('"@type": "3DModel"', '"@type": "Typo"')
    results = [
        {"sitecode": "uk", "url": "https://www.samsung.com/uk/smartphones/galaxy-s26-ultra/", "region": "EHQ", "country": "U.K", "product": "S26 Ultra",
         "schema": sch.check_page(good, schema_rules), "copy": cop.check_copy(good, copy_rules, key_specs=ks)},
        {"sitecode": "de", "url": "https://www.samsung.com/de/smartphones/galaxy-s26-ultra/", "region": "EHQ", "country": "Germany", "product": "S26 Ultra",
         "schema": sch.check_page(bad, schema_rules), "copy": cop.check_copy(bad, copy_rules, key_specs=ks)},
    ]
    print("summary:", summary_counts(results))
    open("/tmp/qa_report.xlsx", "wb").write(build_xlsx(results))
    print("→ /tmp/qa_report.xlsx (Schema QA / Copy QA, English)")

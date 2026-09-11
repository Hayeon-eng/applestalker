"""
qa_report_rows.py — 큐비 — Excel 리포트 행(row) 빌더 (qa_report.py 분할 2/3)
schema/html_qa 검수 결과를 Excel 한 행(As-Is/To-Be/위치/영향/Fix Code) 단위로 변환한다.
분할 배경·전체 구조는 qa_report_helpers.py 상단 설명 참고 — 기능 변경 없는 순수 분할이다.
"""
from __future__ import annotations
import copy
from typing import Any, Dict

from qa_report_helpers import (
    _primary_type, _en, _prop_help, _clip,
    _fill_placeholders, _fix_code_for_missing, _fix_code_for_block_missing, _fix_code_for_value,
    _parse_raw_node, _set_nested, _code_pair_diff, _code_pair_new_block, _code_pair_text,
)

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
    elif len(title) > 60:  # [D11] 길이 초과는 warn 까지만(사람 검수 항목에 길이 기준 없음)
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
    elif len(desc) > 160:  # [D11] warn 까지만
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
    # [2026-09] H2 개수는 사람 검수 기준에 없는 항목(가이드 H2 최소 개수 데이터 미연결) — 오류(fail)로 내면
    # 정합성이 깨지므로 확인(warn) 등급으로만 남긴다. 화면(HtmlQaDetail)도 동일하게 맞출 것.
    if len(h2s) == 0:
        as_is = "(none found) — 0 H2 tags"
        to_be = '<h2>Camera</h2>\n<h2>Battery</h2>\n<h2>Display</h2>'
        rows.append(("HTML", "H2", "h2", "warn", as_is,
                     "Add at least one <h2> section heading",
                     "Body -> <h2>", "Content structure signal for AEO",
                     to_be, _code_pair_text(as_is, to_be)))
    return rows


_SEO_LOC = {
    "Canonical Tag": "<head> -> link[rel=canonical]",
    "Title Tag": "<head> -> <title>",
    "Meta Description": "<head> -> meta[name=description]",
    "Google Discover Opt.": "<head> -> meta[name=robots]",
    "Breadcrumb": "JSON-LD BreadcrumbList / <nav> breadcrumb",
}
_SEO_IMPACT = {
    "Canonical Tag": "Duplicate/canonical signal to search engines",
    "Title Tag": "Title shown in search / AI answers",
    "Meta Description": "Snippet shown in search / AI answers",
    "Google Discover Opt.": "Google Discover large image preview eligibility",
    "Breadcrumb": "Site hierarchy signal / breadcrumb rich result",
}


def _seo_rows(pr):
    """[2026-09 D2~D7] seo_checker 결과 → 작업자용 영어 행. 사람 리포트의 Issue Name 을 그대로 item 에
    쓰고, To-Be 는 Dictionary 의 Fix Guideline 을 사용한다. pass 항목은 행을 만들지 않는다."""
    seo = pr.get("seo") or {}
    rows = []
    for it in seo.get("items") or []:
        if it.get("status") not in ("fail", "warn"):
            continue
        el, issue = it.get("element", ""), it.get("issue", "")
        as_is = (f"Current: \"{_clip(it.get('value') or '', 200)}\"" if it.get("value") else "(missing)")
        if it.get("detail"):
            as_is += f" · {_clip(it['detail'], 160)}"
        fix = it.get("fix") or issue
        rows.append(("HTML", el, issue, it["status"], as_is, fix,
                     _SEO_LOC.get(el, "<head>"), _SEO_IMPACT.get(el, ""), fix, _code_pair_text(as_is, fix)))
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
            blk = f.get("block_label") or ""  # [D9] "#N Type" — 사람 리포트 Block 열 형식
            loc = (f"{blk} — line {ln}, col {col}" if ln else f"{blk} (position unknown)") if blk else \
                (f"JSON-LD script — line {ln}, col {col}" if ln else "JSON-LD script (position unknown)")
            if f.get("type_guess"):
                ty = f["type_guess"]
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
        # [2026-09] 번역확인(translate_confirm)은 "오류 아님·사람이 현지화 여부만 확인" 안내라 사람 검수
        # 기준에도 없고, 페이지마다 5~6행이 붙어 실제 오류를 가렸다(sec 실크롤: 12행 중 6행).
        # 엑셀에서는 행을 만들지 않고(화면 JSON 에는 그대로 남아 '판정 근거'에서 볼 수 있음) 구조화 처리만 표시.
        if f.get("translate_confirm"):
            structured = True
        for t in []:  # (구 로직 보존 — 필요 시 `f.get("translate_confirm") or []` 로 되돌리면 행이 다시 생성됨)
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
            if prop in ("screen_match",):  # [2026-09] 자동 검증 불가(수동확인 고정 0.5) 항목 — 누락 행 생성 안 함
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

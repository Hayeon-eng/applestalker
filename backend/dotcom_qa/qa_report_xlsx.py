"""
qa_report_xlsx.py — 큐비 — build_xlsx() 본체 (qa_report.py 분할 3/3)
Sheet 1 "Data QA" + Sheet 2 "Spec QA" 두 시트를 만드는 실제 openpyxl 작성 로직.
분할 배경·전체 구조는 qa_report_helpers.py 상단 설명 참고 — 기능 변경 없는 순수 분할이다.
"""
from __future__ import annotations
import io

from qa_report_helpers import MARK, MARK_COLOR, SEV_COLOR2, _page_type
from qa_report_rows import _schema_detail_rows, _html_qa_schema_gap_rows, _html_qa_rows

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
    SEV_LABEL = {"fail": "🔴 Must Fix", "warn": "🟡 Review", "info": "⚪ Dictionary (reference)"}

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
            return CellRichText([TextBlock(_RT_NORMAL, "(empty block)")])
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

    # [2026-07 신규] "달라진 부분만 빨간색" 규칙을 JSON-LD 블록뿐 아니라 일반 문장
    # (Meta Title/H1 등 HTML 항목의 as-is/to-be)에도 동일하게 적용하기 위한 단어 단위 diff.
    # 위 _diff_pair_richtext(줄 단위, JSON 블록용)와 같은 색 규칙을 문장에 맞춰 재사용한다.
    _RT_RED_TXT = InlineFont(sz=10, color="FFD8362F", b=True)
    _RT_NORMAL_TXT = InlineFont(sz=10)
    _RT_RED_TXT_TOBE = InlineFont(sz=10, color="FFD8362F", b=True)
    _RT_NORMAL_TXT_TOBE = InlineFont(sz=10, color="FF067647")

    def _word_tokens(s):
        return re.split(r"(\s+)", s or "")

    def _rich_words(tokens, changed_flags, normal_font, red_font):
        if not tokens or not any(t.strip() for t in tokens):
            return CellRichText([TextBlock(normal_font, "(none)")])
        return CellRichText([TextBlock(red_font if ch else normal_font, tok)
                              for tok, ch in zip(tokens, changed_flags)])

    def _word_diff_richtext(a_str, b_str):
        a_tok = _word_tokens(a_str); b_tok = _word_tokens(b_str)
        sm = difflib.SequenceMatcher(a=a_tok, b=b_tok, autojunk=False)
        a_changed = [False] * len(a_tok); b_changed = [False] * len(b_tok)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                for i in range(i1, i2):
                    a_changed[i] = True
                for j in range(j1, j2):
                    b_changed[j] = True
        a_rt = _rich_words(a_tok, a_changed, _RT_NORMAL_TXT, _RT_RED_TXT)
        b_rt = _rich_words(b_tok, b_changed, _RT_NORMAL_TXT_TOBE, _RT_RED_TXT_TOBE)
        return a_rt, b_rt

    # [2026-07 신규] Spec QA(기준값 ↔ 페이지 실제값)는 "4400 mAh" ↔ "4,400mAh"처럼
    # 짧은 값 안에서 글자 하나 차이가 관건인 경우가 많아, 단어 단위보다 글자 단위 diff가
    # 더 정확하다. 색 규칙은 위 문장/블록용과 동일(D8362F).
    def _rich_chars(s, changed_flags, normal_font, red_font):
        if not s:
            return CellRichText([TextBlock(normal_font, "(none)")])
        items, buf, cur = [], [], None
        for ch, flag in zip(s, changed_flags):
            if flag != cur and buf:
                items.append(TextBlock(red_font if cur else normal_font, "".join(buf))); buf = []
            buf.append(ch); cur = flag
        if buf:
            items.append(TextBlock(red_font if cur else normal_font, "".join(buf)))
        return CellRichText(items)

    def _char_diff_richtext(a_str, b_str):
        a_str = a_str or ""; b_str = b_str or ""
        sm = difflib.SequenceMatcher(a=a_str, b=b_str, autojunk=False)
        a_changed = [False] * len(a_str); b_changed = [False] * len(b_str)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                for i in range(i1, i2):
                    a_changed[i] = True
                for j in range(j1, j2):
                    b_changed[j] = True
        a_rt = _rich_chars(a_str, a_changed, _RT_NORMAL_TXT, _RT_RED_TXT)
        b_rt = _rich_chars(b_str, b_changed, _RT_NORMAL_TXT_TOBE, _RT_RED_TXT_TOBE)
        return a_rt, b_rt

    def _write_diff_cells(ws, rn, col_a, col_b, a_str, b_str):
        c_a = ws.cell(row=rn, column=col_a); c_b = ws.cell(row=rn, column=col_b)
        try:
            a_rt, b_rt = _char_diff_richtext(a_str, b_str)
            c_a.value = a_rt; c_b.value = b_rt
        except Exception:
            c_a.value = a_str; c_b.value = b_str
        c_a.alignment = Alignment(vertical="top", wrap_text=True)
        c_b.alignment = Alignment(vertical="top", wrap_text=True)

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
            c_a.value = "(This block does not exist on the page — TO-BE is the full new block to add)"
            c_b.value = code_pair.get("code", "")
            c_a.font = Font(italic=True, size=10, color="98A2B3")
            c_b.font = mono
        else:
            a_str = code_pair.get("as_is", "") if code_pair else ""
            b_str = code_pair.get("to_be", "") if code_pair else ""
            try:
                a_rt, b_rt = _word_diff_richtext(a_str, b_str)
                c_a.value = a_rt; c_b.value = b_rt
            except Exception:
                c_a.value = a_str; c_b.value = b_str
                c_a.font = Font(size=10)
                c_b.font = Font(size=10, color="067647", bold=True)
        c_a.alignment = Alignment(vertical="top", wrap_text=True)
        c_b.alignment = Alignment(vertical="top", wrap_text=True)

    wb = Workbook()

    def _issue_type_of(item: str, as_is: str) -> str:
        """작업자가 위에서 훑어보고 바로 종류를 알 수 있게 — Issue 텍스트/AS-IS 패턴에서
        요약 카테고리를 뽑는다(기존 항목 구성 방식은 그대로 두고, 순수 표시용 파생값만 추가)."""
        it = (item or "")
        a = as_is or ""
        if it == "JSON-LD syntax" or a.startswith("[Google Rich Result] JSON-LD"):
            return "Syntax Error"
        if it in ("title", "meta_description", "h1", "h2"):
            return {"title": "Meta Title Length", "meta_description": "Meta Description Length",
                    "h1": "Heading Structure (H1)", "h2": "Heading Structure (H2)"}[it]
        if it == "@type":
            return "Missing Block"
        if it == "@id":
            return "ID/URL Mismatch" if a.startswith("Current @id") else "ID/URL Issue"
        if it == "hasPart":
            return "Missing Link (hasPart)"
        if it.endswith("(translation check)"):
            return "Translation Check"
        if it == "inLanguage":
            return "Language Mismatch"
        if it.startswith("Product name"):
            return "Product Name Mismatch"
        if a.startswith("(missing) — property not present") or a.startswith("(missing/insufficient)"):
            return "Missing Property"
        if a.startswith("(missing/partial)"):
            return "Missing Recommended Property"
        if a.startswith("Current:"):
            return "Value Mismatch"
        if "is an array" in a:
            return "Structure Preference"
        if a.startswith("(missing)"):
            return "Missing Value"
        return "Other"

    # ── Sheet 1 — Data QA (Schema + HTML) ──
    #   Product -> Where -> Issue Type(요약) -> Issue(상세) -> AS-IS full block -> TO-BE full block(달라진 줄 빨간색) -> URL
    HEAD1 = ["#", "Product", "Site", "Where", "Issue Type", "Severity", "Issue",
             "AS-IS (current full block)", "TO-BE (fixed full block)", "URL"]
    W1 = [4, 16, 20, 26, 20, 12, 26, 55, 55, 38]
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
        ws.append([n, product, _site_cell(region, country, site), where, _issue_type_of(item, a), "",
                   f"{item}", "", "", url])
        rn = ws.max_row
        sc = ws.cell(row=rn, column=6); sc.value = SEV_LABEL.get(sev, sev)
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        _write_code_pair(ws, rn, 8, 9, code_pair)
    if not data_rows:
        ws.append(["—", "", "", "", "", "🟢 OK", "No issues found", "", "", ""])
    _finish(ws, W1, "A2")

    # ── Sheet 2 — Spec QA — 기준값 ↔ 페이지 실제값 (핵심 컬럼만) ──
    def _issue_type_of2(kind: str, found: str) -> str:
        k = kind or ""
        missing = found == "(not found on page)"
        if k.startswith("Rule ·"):
            return "Missing Spec Value" if missing else "Spec Value Mismatch"
        if k == "Dictionary (reference)":
            return "Dictionary Review"
        if k == "Proper Noun":
            return "Proper Noun Mismatch"
        if k == "Spec Value":
            return "Missing Spec Value" if missing else "Spec Value Mismatch"
        if k == "Spec":
            return "Missing Spec" if missing else "Spec Mismatch"
        return "Other"

    HEAD2 = ["#", "Product", "Site", "Where", "Issue Type", "Severity", "Spec Item", "Expected (Guide)", "Found on Page", "URL"]
    W2 = [4, 16, 20, 22, 20, 12, 22, 30, 32, 38]
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
                spec_rows.append((meta, "Dictionary (reference)", c.get("alias", ""), "info",
                                  f'Seen on {c.get("count","?")} pages within this product · confidence={c.get("confidence","")} '
                                  "· Review translation/wording, then approve by adding to Dictionary (optional)",
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
        ws2.append([n, product, _site_cell(region, country, site), f"{kind} → {loc}",
                    _issue_type_of2(kind, found), "", str(item), "", "", url])
        rn = ws2.max_row
        sc = ws2.cell(row=rn, column=6); sc.value = SEV_LABEL.get(sev, sev)
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        _write_diff_cells(ws2, rn, 8, 9, exp, found)
    if not spec_rows:
        ws2.append(["—", "", "", "", "", "🟢 OK", "No issues found", "", "", ""])
    _finish(ws2, W2, "A2")

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

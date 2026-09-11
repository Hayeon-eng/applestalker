"""
qa_report_xlsx.py — 큐비 — build_xlsx() 본체 (qa_report.py 분할 3/3)
Sheet 1 "Data QA" + Sheet 2 "Spec QA" 두 시트를 만드는 실제 openpyxl 작성 로직.
분할 배경·전체 구조는 qa_report_helpers.py 상단 설명 참고 — 기능 변경 없는 순수 분할이다.
"""
from __future__ import annotations
import io
import json
import re
import difflib

from qa_report_helpers import MARK, MARK_COLOR, SEV_COLOR2, _page_type
from qa_report_rows import _schema_detail_rows, _html_qa_schema_gap_rows, _html_qa_rows, _seo_rows


# ──────────────────────────────────────────────────────────────────
# [2026-07 과제5] 스키마 오류 "주체(PIC)" 판정 — Excel 리포트 전용(프론트 미노출).
#   근거: 삼성닷컴_스키마_오류_수정_가이드(2026-06)
#     · D2C : 자동 생성 스키마(페이지/컴포넌트 자동 적용) — 템플릿/구조 오류
#             → BreadcrumbList, WebPage/ItemPage, Product(구조·@id·hasPart), Organization/Brand
#     · OC  : html 생성(OC 제작/제일 디지털플랫폼 3팀) — 코드/구조 오류
#             → Quotation, 3DModel, VideoObject, FAQPage, ItemList, (title/meta/h1/h2 등 HTML)
#     · WSC : localization(현지화) — 번역/언어/현지어 텍스트 오류(블록 무관, 최우선)
#             → inLanguage, translation check, name/description 현지어 불일치 등
# ──────────────────────────────────────────────────────────────────
_D2C_TYPES = ("breadcrumblist", "webpage", "itempage", "product", "organization", "brand")
_OC_TYPES = ("quotation", "3dmodel", "videoobject", "faqpage", "itemlist")
_OC_HTML_ITEMS = ("title", "meta_description", "h1", "h2")
_LOCALIZATION_ITEMS = ("inlanguage",)


def _error_owner(block_type: str, where: str, item: str, issue_type: str) -> str:
    """(block @type, 수정위치, 속성, 요약 issue_type) → 'D2C' | 'WSC' | 'OC'.
    판정 불가하면 보수적으로 'OC'(코드 제작 주체)로 폴백한다."""
    bt = (block_type or "").lower()
    wh = (where or "").lower()
    it = (item or "").lower()
    itype = (issue_type or "").lower()
    hay = f"{bt} {wh}"

    # 1) 현지화(localization) 오류 → WSC (블록과 무관하게 최우선)
    if ("translation" in itype or "language mismatch" in itype or "product name mismatch" in itype
            or it in _LOCALIZATION_ITEMS or "(translation check)" in it
            or it.startswith("product name") or it in ("name", "description", "headline")):
        return "WSC"

    # 2) HTML 페이지 메타(제목/디스크립션/헤딩) → OC(HTML 제작)
    if it in _OC_HTML_ITEMS:
        return "OC"
    # [2026-09 D2~D7] SEO 요소: 템플릿/PIM 자동 생성 영역(canonical·robots·breadcrumb) → D2C,
    # 콘텐츠 텍스트(Title/Meta Description) → OC
    if bt in ("canonical tag", "google discover opt.", "breadcrumb"):
        return "D2C"
    if bt in ("title tag", "meta description"):
        return "OC"

    # 3) 스키마 블록 소유 주체
    if any(t in hay for t in _OC_TYPES):
        return "OC"
    if any(t in hay for t in _D2C_TYPES):
        return "D2C"

    # 4) 판정 불가(알 수 없는 블록/구문오류 등) → OC 폴백
    return "OC"

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
        "galaxy-watch9": "Galaxy Watch9",
        "galaxy-watch-ultra": "Galaxy Watch Ultra",
        "galaxy-watch-ultra2": "Galaxy Watch Ultra2",
        "galaxy-z-fold8-ultra": "Galaxy Z Fold8 Ultra",
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

    _SEO_ISSUE_NAMES = {
        "No canonical link present", "Should be canonicalized", "Title tag missing", "Model name missing",
        "Model name incomplete", "Wrong model name in tag", "Country tail missing", "Country tail duplicate",
        "Samsung keyword missing", "Spec keyword missing", "Title length over guideline",
        "Meta description missing", "Insufficient Description", "Duplicate", "No robots meta tag",
        "Robots directive missing", "No breadcrumb", "Wrong breadcrumb structure", "Wrong breadcrumb label",
        "Breadcrumb link missing", "Wrong breadcrumb link inserted", "Breadcrumb label unverifiable",
    }

    def _is_not_checked(pr) -> bool:
        """HTML 수집 실패(404/차단/타임아웃) 페이지 — qb_routes_run 이 not_checked 플래그를 붙이거나,
        구버전 결과는 findings 가 '(collection failed)' 1건뿐인 경우."""
        if pr.get("not_checked"):
            return True
        sch = (pr.get("schema") or {}).get("findings") or []
        return bool(sch) and all(f.get("block") in ("(collection failed)", "(수집 실패)") for f in sch) \
            and pr.get("html_qa") is None

    def _issue_type_of(item: str, as_is: str) -> str:
        if item in _SEO_ISSUE_NAMES:
            return item  # [D2~D7] 사람 리포트 Dictionary 의 Issue Name 그대로
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
             "AS-IS (current full block)", "TO-BE (fixed full block)", "URL",
             "오류 주체(PIC)"]  # [과제5] Excel 전용 — 프론트 미노출
    W1 = [4, 16, 20, 26, 20, 12, 26, 55, 55, 38, 13]
    ws = wb.active; ws.title = "Data QA"
    ws.append(HEAD1); _hdr(ws)
    data_rows = []
    not_checked = []  # [D8] 수집 실패/미검수 페이지 — 별도 시트(사람 리포트 'Not Checked')
    for pr in page_results:
        try:
            meta = _meta(pr)
            if _is_not_checked(pr):
                not_checked.append((meta, pr))
                continue
            srows, covered = _schema_detail_rows(pr)
            for r in srows + _html_qa_schema_gap_rows(pr, covered) + _html_qa_rows(pr) + _seo_rows(pr):
                data_rows.append((meta,) + tuple(r))
        except Exception as e:
            # [2026-07 FIX] 페이지 1건의 데이터 구조 문제로 전체 Excel 다운로드가 500 나던
            # 문제 대응 — 그 페이지만 건너뛰고 어떤 사이트가 문제였는지 눈에 보이게 남긴다.
            import traceback
            traceback.print_exc()
            meta = _meta(pr) if isinstance(pr, dict) else ("", "", pr, "", "", "")
            data_rows.append((meta, "REPORT", "REPORT", "Report generation error", "fail",
                               f"{type(e).__name__}: {e}", "", "(internal)", "", "", ""))
    data_rows.sort(key=lambda r: (r[0][1] or "zz", r[0][2] or "", sev_rank.get(r[4], 9), r[1], r[2]))
    _OWNER_COLOR = {"D2C": "1D4ED8", "OC": "B45309", "WSC": "047857"}  # 파랑/주황/초록
    for n, (meta, area, ty, item, sev, a, t, loc, impact, fix_code, code_pair) in enumerate(data_rows, 1):
        region, country, site, ptype, url, product = meta
        where = loc or ty
        issue_type = _issue_type_of(item, a)
        owner = _error_owner(ty, where, item, issue_type)  # [과제5]
        ws.append([n, product, _site_cell(region, country, site), where, issue_type, "",
                   f"{item}", "", "", url, owner])
        rn = ws.max_row
        sc = ws.cell(row=rn, column=6); sc.value = SEV_LABEL.get(sev, sev)
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        oc = ws.cell(row=rn, column=11)  # 오류 주체(PIC)
        oc.font = Font(bold=True, color=_OWNER_COLOR.get(owner, "000000"))
        oc.alignment = Alignment(horizontal="center", vertical="top")
        _write_code_pair(ws, rn, 8, 9, code_pair)
    if not data_rows:
        ws.append(["—", "", "", "", "", "🟢 OK", "No issues found", "", "", "", ""])
    _finish(ws, W1, "A2")

    # ── Sheet "Not Checked" — [D8] 수집 실패 페이지(사람 리포트 시트4와 동일 취지) ──
    if not_checked:
        wsn = wb.create_sheet("Not Checked")
        wsn.append(["#", "Product", "Site", "Page Type", "URL", "HTTP Status", "Final URL", "Reason"]); _hdr(wsn)
        for n, (meta, pr) in enumerate(not_checked, 1):
            region, country, site, ptype, url, product = meta
            reason = ""
            for f in (pr.get("schema") or {}).get("findings") or []:
                if f.get("as_is"):
                    reason = f["as_is"]; break
            wsn.append([n, product, _site_cell(region, country, site), ptype, url,
                        pr.get("http_status") or "", pr.get("final_url") or "", reason])
        _finish(wsn, [4, 16, 20, 10, 48, 10, 48, 60], "A2")

    # ── Sheet 2 — Spec QA — 기준값 ↔ 페이지 실제값 (핵심 컬럼만) ──
    def _issue_type_of2(kind: str, found: str) -> str:
        k = kind or ""
        missing = found == "(not found on page)"
        if k.startswith("Compare"):
            return "Compare Spec Mismatch"
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

    # [2026-09] "Reason" 열 추가 — 엔진 판정 메시지 + 마지막 trace. 실크롤 리포트만 보고도
    # 오탐/누락 원인을 진단할 수 있게(sec 실크롤: Thickness FAIL 의 근거를 엑셀에서 알 수 없었음).
    HEAD2 = ["#", "Product", "Site", "Where", "Issue Type", "Severity", "Spec Item", "Expected (Guide)", "Found on Page", "URL", "Reason (engine)"]
    W2 = [4, 16, 20, 22, 20, 12, 22, 30, 32, 38, 60]
    ws2 = wb.create_sheet("Spec QA")
    ws2.append(HEAD2); _hdr(ws2)
    KIND_EN = {"spec": "Spec", "proper_noun": "Proper Noun", "spec_value": "Spec Value"}
    spec_rows = []
    for pr in page_results:
        try:
            meta = _meta(pr)
            sv = pr.get("spec_v2")
            cv = pr.get("compare_v2")
            # [2026-07 FIX] Compare 페이지는 spec_v2가 아니라 compare_v2(제품별 매트릭스 QA)가
            # 실제 판정을 갖고 있는데, 지금까지 Excel Spec QA 시트는 compare_v2를 전혀 안 읽어서
            # Compare 페이지의 오기재/확인필요 항목이 화면(UI)에는 보이는데 Excel엔 하나도
            # 안 나오고 있었다 — 그것부터 채운다(있으면 이걸 우선, spec_v2/copy는 그대로 폴백).
            if cv and cv.get("summary", {}).get("checked"):
                for r in cv.get("rows", []):
                    category, spec = r.get("category", ""), r.get("spec", "")
                    for cell in r.get("values", []):
                        st = cell.get("status")
                        if st not in ("fail", "warn"):
                            continue
                        label = "Compare" + (" (review — not a confirmed error)" if st == "warn" else "")
                        item = f'{cell.get("product", "")} · {category + " — " if category else ""}{spec}'
                        spec_rows.append((meta, label, item, st, cell.get("message", ""),
                                          str(cell.get("value", "")), "Compare", cell.get("message", "")))
            elif sv:
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
                    _tr = [t.get("detail", "") for t in (it.get("trace") or []) if t.get("step") in ("value-scan", "pair", "result")]
                    reason = (it.get("message") or "") + ((" | " + " / ".join(_tr[-3:])) if _tr else "")
                    spec_rows.append((meta, label, item, it["status"], exp, found_s, loc or "PDP", reason[:900]))
                for c in sv.get("dictionary_review", []) or []:
                    spec_rows.append((meta, "Dictionary (reference)", c.get("alias", ""), "info",
                                      f'Seen on {c.get("count","?")} pages within this product · confidence={c.get("confidence","")} '
                                      "· Review translation/wording, then approve by adding to Dictionary (optional)",
                                      "(unmapped label)", "Spec", ""))
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
                    spec_rows.append((meta, kind, item, f.get("status"), expected, found_s, loc, ""))
        except Exception as e:
            import traceback
            traceback.print_exc()
            meta = _meta(pr) if isinstance(pr, dict) else ("", "", pr, "", "", "")
            spec_rows.append((meta, "REPORT", "Report generation error", "fail",
                               f"{type(e).__name__}: {e}", "(internal)", "Spec", ""))
    spec_rows.sort(key=lambda r: (r[0][1] or "zz", r[0][2] or "", sev_rank.get(r[3], 9)))
    for n, (meta, kind, item, sev, exp, found, loc, reason) in enumerate(spec_rows, 1):
        region, country, site, ptype, url, product = meta
        ws2.append([n, product, _site_cell(region, country, site), f"{kind} → {loc}",
                    _issue_type_of2(kind, found), "", str(item), "", "", url, reason])
        rn = ws2.max_row
        sc = ws2.cell(row=rn, column=6); sc.value = SEV_LABEL.get(sev, sev)
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        _write_diff_cells(ws2, rn, 8, 9, exp, found)
    if not spec_rows:
        ws2.append(["—", "", "", "", "", "🟢 OK", "No issues found", "", "", "", ""])
    _finish(ws2, W2, "A2")

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

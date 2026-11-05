"""
product_pack_xlsx.py — 큐비 · 제품 등록 워크북 (템플릿 ①)  [2026-11 신규]

"모델이 계속 바뀐다" → 제품 하나에 필요한 정답·대상을 엑셀 1개로 다룬다. 시트:
  0_안내         작성 규칙
  제품정보       제품키·표시명·카테고리·스키마 세트·전작·모델 토큰·고유명사        → product_master.json (+ schema name_tokens)
  URL            sitecode·url·region·country·lang·product·page_type(·최근 검수)   → site_registry (추가/갱신/제품 단위 교체)
  MasterSpec·Dictionary·ExceptionRule·InteractionRule·CountryException·UnitSynonym·PreviousModel·SiblingModel
                 (기존 Spec Rule DB 시트 그대로)                                     → spec_rule_db
  스키마_블록 · 스키마_기대값 (스키마 정답값 템플릿 시트 그대로)                   → schema_values.uploaded.json

세 가지 내려받기:
  template : 빈 양식 + 예시(초록) 1세트
  export   : 지금 저장된 제품 값 전부(수정 후 재업로드 = 왕복)
  draft    : 신모델 전환 초안 — 이전 제품키 → 새 제품키. 스펙 룰은 전작(PreviousModel) 시트가 이전 제품 정답으로
             자동 채워지고 기대값은 빈칸, 스키마·URL 은 슬러그 치환, 제품정보는 전작 키 자동. 사람은 빈칸만 채운다.
업로드는 시트별로 각 저장소에 반영하고 결과(어느 시트 몇 건)를 돌려준다. 시트가 없으면 그 영역은 건드리지 않는다.
"""
from __future__ import annotations
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import product_master
import schema_values_xlsx as svx
import spec_rule_db

HEAD_FILL = PatternFill("solid", fgColor="1B2A4A")
HEAD_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial", size=10)
EXAMPLE_FILL = PatternFill("solid", fgColor="E7F6EC")
DRAFT_FILL = PatternFill("solid", fgColor="FFF6DA")   # 초안에서 사람이 채워야 하는 칸

PRODUCT_HEADERS = ["제품키", "제품 표시명", "카테고리(smartphone/watch/buds/tablet/laptop/other)", "스키마 세트(flagship/simple)",
                   "전작 제품키", "모델 토큰(model_any, 쉼표)", "등급 토큰(tier_any, 쉼표)", "금지 토큰(forbid_any, 쉼표)",
                   "모델 라벨", "등급 라벨", "고유명사(쉼표)", "메모"]
URL_HEADERS = ["sitecode", "url", "region", "country", "lang", "product", "page_type", "최근 검수(내보내기 전용)"]
SPEC_SHEETS = ["MasterSpec", "Dictionary", "ExceptionRule", "InteractionRule", "CountryException", "UnitSynonym", "PreviousModel", "SiblingModel"]
SPEC_PREFIX = "스펙_"            # 워크북 안 시트명: 스펙_MasterSpec … (Rule DB 파서는 부분 일치로 찾으므로 그대로 읽힌다)
SPEC_RENAME = {n: SPEC_PREFIX + n for n in SPEC_SHEETS}
PAGE_TYPES = ["PDP", "Compare", "Buying", "Specs", "Disclaimer"]
SHEET_ORDER = ["0_안내", "제품정보", "URL"] + [SPEC_PREFIX + n for n in SPEC_SHEETS] + ["스키마_블록", "스키마_기대값"]
SHEET_DESC = [
    ("제품정보", "제품 마스터(표시명·카테고리·스키마 세트·전작·토큰·고유명사)", "필수(1행)"),
    ("URL", "큐비 모니터링 URL", "선택"),
    ("스펙_MasterSpec", "스펙 룰(정답값) — Rule DB", "선택(스펙 룰 갱신 시)"),
    ("스펙_Dictionary … 스펙_SiblingModel", "라벨 사전·예외·단위 동의어·전작·형제 모델", "선택"),
    ("스키마_블록 · 스키마_기대값", "스키마 정답값(@id 패턴·hasPart·속성 기대값)", "선택(둘은 함께)"),
]
GUIDE = [
    ("이 파일은", "제품 1개의 '정답'과 '검수 대상'을 한 번에 등록·갱신하는 워크북입니다. 시트별로 각 저장소에 반영되고, 비어 있거나 없는 시트는 건드리지 않습니다."),
    ("내려받기 3종", "① 템플릿: 빈 양식 + 초록 예시 행  ② 현재 값: 지금 저장된 값(수정 후 재업로드 = 왕복)  ③ 신모델 초안: 이전 제품 → 새 제품키를 넣으면 전작 시트·슬러그 치환이 자동, 노랑 칸만 채우면 됨"),
    ("제품키", "URL 슬러그와 같게(예: galaxy-z-fold9). 모든 시트의 제품키가 같아야 합니다."),
    ("제품정보", "카테고리가 smartphone 이면 스키마 세트 flagship, 그 외 simple(비우면 자동). 전작 제품키는 Spec QA 전작 값 판정·초안 생성에 사용. 모델/등급/금지 토큰은 스키마 Product.name 검사용. 고유명사는 DATA QA 카피 검사용."),
    ("URL", "업로드 모드: 추가(중복 건너뜀) / 갱신(같은 sitecode·product·page_type 이면 URL 교체) / 제품 단위 교체. '최근 검수' 열은 내보내기 전용(에러 페이지 = URL 점검 필요)이라 입력하지 않습니다."),
    ("스펙_* 시트", "기존 Rule DB 엑셀과 같은 형식. MasterSpec 의 Official Value 가 비어 있으면 그 룰은 '해당 없음'으로 판정됩니다(업로드 시 경고)."),
    ("스키마_* 시트", "자리표시자 {SITECODE} {PD_URL} {BCP47-LANG} 그대로 사용. 여러 개 블록(Video·Quotation·Comment·3DModel)은 '#video-1' 처럼 접두어-번호만 적으면 같은 접두어의 @id 를 모두 정상으로 봅니다."),
    ("색", "초록 = 예시 행(지우고 실제 값으로) · 노랑 = 신모델 초안에서 사람이 채울 칸 · 드롭다운이 있는 열은 목록에서 고르세요."),
]


def _style_header(ws, headers: List[str], widths: Optional[List[int]] = None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h); c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = (widths[i - 1] if widths and i - 1 < len(widths) else max(14, min(50, len(h) + 6)))
    ws.freeze_panes = "A2"


def _append(ws, row: List[Any], fill: Optional[PatternFill] = None, fill_cols: Optional[List[int]] = None):
    ws.append(row)
    for j, c in enumerate(ws[ws.max_row], 1):
        c.font = BODY_FONT; c.alignment = Alignment(wrap_text=True, vertical="top")
        if fill is not None and (fill_cols is None or j in fill_cols):
            c.fill = fill


_THIN = Side(style="thin", color="E4E9F2")


def _list_validation(ws, col_letter: str, options: List[str], title: str = ""):
    """열 전체(2~1000행)에 드롭다운. 목록이 길면 엑셀 제한(255자) 때문에 생략."""
    formula = '"' + ",".join(options) + '"'
    if len(formula) > 255:
        return
    dv = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=False, promptTitle=title or None,
                        prompt=("목록에서 선택: " + ", ".join(options)) if title else None, showInputMessage=bool(title))
    ws.add_data_validation(dv); dv.add(f"{col_letter}2:{col_letter}1000")


def _finish_sheet(ws):
    """공통 마감: 머리글 행 높이, 테두리, 자동 필터."""
    ws.row_dimensions[1].height = 30
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{max(ws.max_row, 2)}"
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
        for c in row:
            c.border = Border(bottom=_THIN)


def _apply_validations(wb: Workbook):
    import product_master as _pm
    if "제품정보" in wb.sheetnames:
        _list_validation(wb["제품정보"], "C", _pm.CATEGORIES, "카테고리"); _list_validation(wb["제품정보"], "D", _pm.SCHEMA_SETS, "스키마 세트")
    if "URL" in wb.sheetnames:
        _list_validation(wb["URL"], "G", PAGE_TYPES, "페이지 타입")
    if SPEC_PREFIX + "MasterSpec" in wb.sheetnames:
        ws = wb[SPEC_PREFIX + "MasterSpec"]
        heads = [str(c.value or "") for c in ws[1]]
        for i, h in enumerate(heads, 1):
            col = get_column_letter(i)
            if h.lower().startswith("validation"):
                _list_validation(ws, col, ["Exact", "Numeric Exact", "Prefix", "Dictionary", "Option Match"], "검증 방식")
            elif h.lower().startswith("priority"):
                _list_validation(ws, col, ["Critical", "High", "Medium", "Low"], "우선순위")
            elif h.lower().startswith("page"):
                _list_validation(ws, col, PAGE_TYPES, "페이지")
    if "스키마_블록" in wb.sheetnames:
        _list_validation(wb["스키마_블록"], "B", ["PDP", "Compare"], "페이지")
    if "스키마_기대값" in wb.sheetnames:
        ws = wb["스키마_기대값"]
        _list_validation(ws, "B", ["PDP", "Compare"], "페이지"); _list_validation(ws, "F", svx.KINDS, "종류"); _list_validation(ws, "G", svx.CHECKS, "검사")


def _order_sheets(wb: Workbook):
    order = {n: i for i, n in enumerate(SHEET_ORDER)}
    wb._sheets.sort(key=lambda ws: order.get(ws.title, 99))
    for ws in wb.worksheets:
        _finish_sheet(ws)
    _apply_validations(wb)
    # 첫 시트(안내)의 탭 색
    wb["0_안내"].sheet_properties.tabColor = "1B2A4A"
    for n in ("제품정보", "URL"):
        if n in wb.sheetnames: wb[n].sheet_properties.tabColor = "1F9E5C"
    for n in wb.sheetnames:
        if n.startswith(SPEC_PREFIX): wb[n].sheet_properties.tabColor = "E0A008"
        if n.startswith("스키마_"): wb[n].sheet_properties.tabColor = "2E6BE6"


def _save(wb: Workbook) -> bytes:
    _order_sheets(wb)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def _new_wb() -> Workbook:
    wb = Workbook(); ws = wb.active; ws.title = "0_안내"
    _style_header(ws, ["항목", "내용"], [18, 120])
    for k, v in GUIDE:
        _append(ws, [k, v]); ws.cell(ws.max_row, 1).font = Font(name="Arial", size=10, bold=True)
    ws.append([]); ws.append(["시트", "반영 대상", "필수 여부"])
    for c in ws[ws.max_row]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT
    ws.column_dimensions["C"].width = 22
    for row in SHEET_DESC:
        _append(ws, list(row))
    _style_header(wb.create_sheet("제품정보"), PRODUCT_HEADERS, [20, 22, 24, 18, 18, 30, 22, 22, 16, 12, 32, 36])
    _style_header(wb.create_sheet("URL"), URL_HEADERS, [10, 72, 10, 16, 8, 20, 12, 30])
    return wb


def _copy_sheets_from_bytes(wb: Workbook, content: bytes, names: List[str], rename: Optional[Dict[str, str]] = None,
                            fill: Optional[PatternFill] = None):
    """다른 빌더(spec_rule_db / schema_values_xlsx)가 만든 엑셀의 시트를 값 그대로 복사."""
    src = load_workbook(io.BytesIO(content), data_only=True)
    for name in names:
        s = next((src[n] for n in src.sheetnames if n == name), None)
        if s is None:
            continue
        ws = wb.create_sheet((rename or {}).get(name, name))
        rows = list(s.iter_rows(values_only=True))
        if not rows:
            continue
        _style_header(ws, [str(h or "") for h in rows[0]], [max(12, min(60, (len(str(h or "")) + 6))) for h in rows[0]])
        for col, dim in s.column_dimensions.items():
            if dim.width:
                ws.column_dimensions[col].width = dim.width
        for r in rows[1:]:
            if all(v in (None, "") for v in r):
                continue
            if str(r[0] or "").startswith("(예시"):
                continue
            _append(ws, list(r), fill)


# ── 제품정보/URL 행 ──────────────────────────────────────────────────
def _label_for(product: str, sv: Optional[Dict[str, Any]], pm: Dict[str, Any]) -> str:
    """표시명 우선순위: 제품 마스터 → Rule DB 의 product 명 → 스키마 토큰 라벨 → 슬러그"""
    if pm.get("label"):
        return pm["label"]
    try:
        rs = spec_rule_db.load(product) or {}
        if " " in str(rs.get("product", "")):      # 'Galaxy Z Fold8' 처럼 사람이 읽는 이름일 때만(슬러그 제외)
            return rs["product"]
    except Exception:
        pass
    nt = (sv or {}).get("name_tokens") or {}
    ml = nt.get("model_label") or ""
    if ml:
        return ml if ml.lower().startswith("galaxy") else f"Galaxy {ml}"
    # 슬러그 → 사람이 읽는 이름: galaxy-z-fold8 → Galaxy Z Fold8
    return " ".join(w.capitalize() if len(w) > 1 else w.upper() for w in product.split("-"))


def _guess_category(product: str) -> str:
    p = product.lower()
    if "buds" in p: return "buds"
    if "watch" in p: return "watch"
    if p.startswith(("galaxy-s", "galaxy-z", "galaxy-a")): return "smartphone"
    if "tab" in p: return "tablet"
    if "book" in p: return "laptop"
    return ""


def _product_row(product: str, sv: Optional[Dict[str, Any]], pm: Dict[str, Any]) -> List[Any]:
    nt = (sv or {}).get("name_tokens") or {}
    cat = pm.get("category") or _guess_category(product)
    return [product, _label_for(product, sv, pm), cat, pm.get("schema_set") or ("flagship" if cat == "smartphone" else ("simple" if cat else "")),
            pm.get("previous_product", ""), ", ".join(nt.get("model_any") or []), ", ".join(nt.get("tier_any") or []),
            ", ".join(nt.get("forbid_any") or []), nt.get("model_label", ""), nt.get("tier_label", ""),
            ", ".join(pm.get("proper_nouns") or []), pm.get("note", "") or (sv or {}).get("_note", "")]


def _url_rows(product: str, registry, status_by_url: Dict[str, str]) -> List[List[Any]]:
    out = []
    for e in registry.all():
        if e.get("product") != product:
            continue
        out.append([e.get("sitecode"), e.get("url"), e.get("region", ""), e.get("country", ""), e.get("lang", ""),
                    e.get("product"), e.get("page_type", "PDP"), status_by_url.get(e.get("url"), "")])
    return out


def _last_status_by_url() -> Dict[str, str]:
    """최근 실행 결과에서 URL 별 상태 — 'URL 점검 필요(에러 페이지)' / '수집 실패' / '검수됨'."""
    try:
        import qb_core
        out = {}
        for r in (qb_core.LAST_RESULTS or []):
            if r.get("url_check_needed"):
                out[r.get("url")] = "URL 점검 필요(에러 페이지)"
            elif r.get("not_checked"):
                out[r.get("url")] = "수집 실패"
            else:
                out[r.get("url")] = "검수됨"
        return out
    except Exception:
        return {}


# ── 내려받기 3종 ─────────────────────────────────────────────────────
def build_template(example_product: str, values: Dict[str, Any], registry) -> bytes:
    wb = _new_wb()
    sv = values.get(example_product)
    pm = product_master.get(example_product)
    _append(wb["제품정보"], _product_row(example_product, sv, pm), EXAMPLE_FILL)
    for r in _url_rows(example_product, registry, {})[:3]:
        _append(wb["URL"], r, EXAMPLE_FILL)
    try:
        spec_bytes = spec_rule_db.build_export_xlsx(example_product)
    except Exception:
        spec_bytes = spec_rule_db.build_template_xlsx(example_product)
    _copy_sheets_from_bytes(wb, spec_bytes, SPEC_SHEETS, SPEC_RENAME, fill=EXAMPLE_FILL)
    if SPEC_PREFIX + "SiblingModel" not in wb.sheetnames:
        _style_header(wb.create_sheet(SPEC_PREFIX + "SiblingModel"), ["Model", "Aliases", "Attribute", "Values", "Unit"])
    if sv:
        _copy_sheets_from_bytes(wb, svx.build_export_xlsx(example_product, values), ["2_블록", "3_기대값"],
                                {"2_블록": "스키마_블록", "3_기대값": "스키마_기대값"}, fill=EXAMPLE_FILL)
    else:
        _style_header(wb.create_sheet("스키마_블록"), svx.SHEETS["2_블록"]); _style_header(wb.create_sheet("스키마_기대값"), svx.SHEETS["3_기대값"])
    return _save(wb)


def build_export(product: str, values: Dict[str, Any], registry) -> bytes:
    wb = _new_wb()
    sv = values.get(product); pm = product_master.get(product)
    _append(wb["제품정보"], _product_row(product, sv, pm))
    for r in _url_rows(product, registry, _last_status_by_url()):
        _append(wb["URL"], r)
    try:
        _copy_sheets_from_bytes(wb, spec_rule_db.build_export_xlsx(product), SPEC_SHEETS, SPEC_RENAME)
    except Exception:
        _copy_sheets_from_bytes(wb, spec_rule_db.build_template_xlsx(product), SPEC_SHEETS, SPEC_RENAME)
        for n in SPEC_SHEETS:   # 템플릿 예시 행은 제거
            nn = SPEC_PREFIX + n
            if nn in wb.sheetnames and wb[nn].max_row > 1:
                wb[nn].delete_rows(2, wb[nn].max_row)
    if SPEC_PREFIX + "SiblingModel" not in wb.sheetnames:
        _style_header(wb.create_sheet(SPEC_PREFIX + "SiblingModel"), ["Model", "Aliases", "Attribute", "Values", "Unit"])
    if sv:
        _copy_sheets_from_bytes(wb, svx.build_export_xlsx(product, values), ["2_블록", "3_기대값"], {"2_블록": "스키마_블록", "3_기대값": "스키마_기대값"})
    else:
        _style_header(wb.create_sheet("스키마_블록"), svx.SHEETS["2_블록"]); _style_header(wb.create_sheet("스키마_기대값"), svx.SHEETS["3_기대값"])
    return _save(wb)


def _swap(text: Any, old: str, new: str) -> Any:
    if not isinstance(text, str) or not text:
        return text
    return text.replace(old, new)


def build_draft(from_product: str, to_product: str, to_label: str, values: Dict[str, Any], registry) -> bytes:
    """신모델 전환 초안. 노랑 = 사람이 채울 칸."""
    rs = spec_rule_db.load(from_product) or {}
    from_sv = values.get(from_product) or {}
    from_pm = product_master.get(from_product)
    from_label = _label_for(from_product, from_sv, from_pm)
    from_cat = from_pm.get("category") or _guess_category(from_product)
    from_set = from_pm.get("schema_set") or ("flagship" if from_cat == "smartphone" else ("simple" if from_cat else ""))
    to_label = to_label or re.sub(r"\d+", lambda m: str(int(m.group()) + 1), from_label, count=1)
    wb = _new_wb()
    # 제품정보: 전작 = 이전 제품키, 표시명·토큰은 숫자 +1 추정(노랑)
    nt = from_sv.get("name_tokens") or {}
    bump = lambda xs: [re.sub(r"\d+", lambda m: str(int(m.group()) + 1), x, count=1) for x in xs]
    _append(wb["제품정보"], [to_product, to_label, from_cat, from_set, from_product,
                             ", ".join(bump(nt.get("model_any") or [])), ", ".join(nt.get("tier_any") or []), ", ".join(nt.get("forbid_any") or []),
                             to_label, nt.get("tier_label", ""), ", ".join(from_pm.get("proper_nouns") or []),
                             f"{from_label} → {to_label} 초안 (자동 생성 — 노랑 칸 확인)"], DRAFT_FILL, [2, 6, 11])
    # URL: 슬러그 치환, 검수 전이므로 상태 비움
    for r in _url_rows(from_product, registry, {}):
        r2 = [_swap(v, from_product, to_product) for v in r]; r2[5] = to_product
        _append(wb["URL"], r2, DRAFT_FILL, [2])
    # 스펙 룰: MasterSpec 은 기대값 빈칸(노랑), 전작 시트 = 이전 제품의 룰이 전작 정답으로
    ws = wb.create_sheet(SPEC_PREFIX + "MasterSpec"); _style_header(ws, spec_rule_db._MASTERSPEC_HEADERS)
    for r in rs.get("rules", []):
        _append(ws, [r.get("rule_id", ""), r.get("category", ""), r.get("attribute", ""), "", r.get("unit", ""),
                     {"exact": "Exact", "numeric_exact": "Numeric Exact", "prefix": "Prefix", "dictionary": "Dictionary",
                      "option_match": "Option Match"}.get(r.get("validation", ""), r.get("validation", "")),
                     r.get("qualifier", ""), r.get("priority", ""), r.get("page", ""), r.get("interaction", ""),
                     r.get("exception", ""), r.get("fix_guide", ""), f"(이전 {from_label} 값: {r.get('expected', '')})"], DRAFT_FILL, [4])
    ws = wb.create_sheet(SPEC_PREFIX + "Dictionary"); _style_header(ws, ["Representative", "Alias"])
    for rep, aliases in (rs.get("dictionary") or {}).items():
        for a in aliases:
            _append(ws, [rep, a])
    ws = wb.create_sheet(SPEC_PREFIX + "ExceptionRule"); _style_header(ws, ["Rule", "Description"])
    for e in rs.get("exceptions", []):
        _append(ws, [e.get("rule", ""), e.get("description", "")])
    ws = wb.create_sheet(SPEC_PREFIX + "InteractionRule"); _style_header(ws, ["Section", "Action"])
    for i in rs.get("interactions", []):
        _append(ws, [i.get("section", ""), i.get("action", "")])
    ws = wb.create_sheet(SPEC_PREFIX + "CountryException"); _style_header(ws, ["Country", "Rule", "Action"])
    for c in rs.get("country_exceptions", []):
        _append(ws, [c.get("country", ""), c.get("rule", ""), c.get("action", "")])
    ws = wb.create_sheet(SPEC_PREFIX + "UnitSynonym"); _style_header(ws, ["Canonical Unit", "Synonym"])
    for canon, syns in (rs.get("unit_synonyms") or {}).items():
        for s_ in syns:
            _append(ws, [canon, s_])
    ws = wb.create_sheet(SPEC_PREFIX + "PreviousModel"); _style_header(ws, ["Model", "Aliases", "Attribute", "Values", "Unit"])
    aliases_from = ",".join(dict.fromkeys((rs.get("product_aliases") or []) + (nt.get("model_any") or [])))
    for r in rs.get("rules", []):
        if r.get("validation") in ("numeric_exact", "exact", "dictionary", "option_match") and r.get("expected"):
            _append(ws, [from_label, aliases_from, r.get("attribute", ""), str(r.get("expected", "")).replace(" / ", "|").replace("/", "|"), r.get("unit", "")])
    for pm_ in rs.get("previous_models", []):   # 2세대 전까지 유지
        for sp in pm_.get("specs", []):
            _append(ws, [pm_.get("model", ""), ",".join(pm_.get("aliases", [])), sp.get("attribute", ""), "|".join(sp.get("values", [])), sp.get("unit", "")])
    ws = wb.create_sheet(SPEC_PREFIX + "SiblingModel"); _style_header(ws, ["Model", "Aliases", "Attribute", "Values", "Unit"])
    # 스키마: 슬러그 치환, 캠페인 콘텐츠(Video/Quotation/Comment)는 접두어만 남김
    if from_sv:
        tmp = svx.build_export_xlsx(from_product, values)
        src = load_workbook(io.BytesIO(tmp), data_only=True)
        for name, new in (("2_블록", "스키마_블록"), ("3_기대값", "스키마_기대값")):
            s = src[name]; ws = wb.create_sheet(new); rows = list(s.iter_rows(values_only=True))
            _style_header(ws, [str(h or "") for h in rows[0]], [20, 14, 22, 70, 60, 14, 16, 12, 30])
            for r in rows[1:]:
                r2 = [_swap(v, from_product, to_product) for v in r]
                if r2 and r2[0]:
                    r2[0] = to_product
                blk = str(r2[2] or "")
                if name == "2_블록" and blk in ("VideoObject", "Quotation", "Comment"):
                    r2[3] = re.sub(r"#(video|mediaquote|samsung-members-comment)[\w\-]*$", lambda m: "#" + m.group(1) + "-1", str(r2[3] or ""))
                _append(ws, r2, DRAFT_FILL if name == "3_기대값" and str(r2[5] or "") == "text" else None)
    return _save(wb)


# ── 업로드 ──────────────────────────────────────────────────────────
def _find(wb, *names):
    for n in wb.sheetnames:
        if n in names:
            return wb[n]
    return None


def _rows(ws):
    for r in ws.iter_rows(min_row=2, values_only=True):
        r = list(r) + [None] * 16
        if all(v in (None, "") for v in r) or str(r[0] or "").startswith("(예시"):
            continue
        yield r


def parse_and_apply(content: bytes, registry, url_mode: str = "add", version: str = "") -> Dict[str, Any]:
    """시트별 반영. 반환: {product, applied: {sheet: summary}, warnings}"""
    wb = load_workbook(io.BytesIO(content), data_only=True)
    applied: Dict[str, Any] = {}
    warnings: List[str] = []
    product = None

    # 1) 제품정보
    ws = _find(wb, "제품정보")
    if ws is not None:
        idx = svx._header_index(ws)
        for r in _rows(ws):
            key = str(svx._col(r, idx, "제품키")).strip()
            if not key:
                continue
            product = product or key
            cat = str(svx._col(r, idx, "카테고리")).strip().lower()
            sset = str(svx._col(r, idx, "스키마 세트")).strip().lower()
            if cat and cat not in product_master.CATEGORIES:
                raise ValueError(f"제품정보: 카테고리 '{cat}' 는 {product_master.CATEGORIES} 중 하나여야 합니다.")
            if sset and sset not in product_master.SCHEMA_SETS:
                raise ValueError(f"제품정보: 스키마 세트 '{sset}' 는 flagship/simple 중 하나여야 합니다.")
            if not sset and cat:
                sset = "flagship" if cat == "smartphone" else "simple"
            info = product_master.save(key, {"label": str(svx._col(r, idx, "제품 표시명", default=key)).strip(), "category": cat,
                                             "schema_set": sset, "previous_product": str(svx._col(r, idx, "전작 제품키")).strip(),
                                             "proper_nouns": svx._split_list(svx._col(r, idx, "고유명사")), "note": str(svx._col(r, idx, "메모")).strip()})
            applied.setdefault("제품정보", []).append({"product": key, **{k: info.get(k) for k in ("label", "category", "schema_set", "previous_product")}})
    if product is None:
        # 제품키를 다른 시트에서 추정
        for name in ("URL", "스키마_블록"):
            w = _find(wb, name)
            if w is not None:
                for r in _rows(w):
                    cand = r[5] if name == "URL" else r[0]
                    if cand:
                        product = str(cand).strip(); break
            if product:
                break
    if not product:
        raise ValueError("제품키를 찾을 수 없습니다 — 제품정보 시트에 제품 행을 적어주세요.")

    # 2) URL
    ws = _find(wb, "URL")
    if ws is not None:
        header = [str(c or "").strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        ix = {c: header.index(c) for c in ("sitecode", "url", "region", "country", "lang", "product", "page_type") if c in header}
        g = lambda r, c: (str(r[ix[c]]).strip() if c in ix and r[ix[c]] not in (None, "") else "")
        file_rows = [r for r in _rows(ws) if g(r, "url")]
        added = updated = skipped = removed = 0
        if url_mode == "replace_product":
            combos = {(g(r, "product") or product, g(r, "page_type") or "PDP") for r in file_rows}
            for e in list(registry.all()):
                if (e.get("product"), e.get("page_type") or "PDP") in combos and registry.remove(e["sitecode"], e["url"]):
                    removed += 1
        for r in file_rows:
            sc, url = g(r, "sitecode").lower(), g(r, "url")
            prod, pt = g(r, "product") or product, g(r, "page_type") or "PDP"
            fields = dict(region=g(r, "region"), country=g(r, "country"), lang=g(r, "lang"), product=prod, page_type=pt)
            if not sc or not url.startswith("http"):
                warnings.append(f"URL: sitecode/url 형식 오류 — {sc} {url[:40]}"); continue
            existing_same = next((e for e in registry.all() if e["sitecode"] == sc and e.get("url") == url), None)
            if existing_same:
                registry.update(sc, url, **fields); skipped += 1; continue
            if url_mode == "upsert":
                tgt = next((e for e in registry.all() if e["sitecode"] == sc and e.get("product") == prod and (e.get("page_type") or "PDP") == pt), None)
                if tgt:
                    registry.remove(sc, tgt["url"]); registry.add(sc, url, **fields); updated += 1; continue
            registry.add(sc, url, **fields); added += 1
        registry.save()
        applied["URL"] = {"mode": url_mode, "added": added, "updated": updated, "unchanged": skipped, "removed": removed}

    # 3) 스펙 룰 (MasterSpec 가 있을 때만)
    if _find(wb, "MasterSpec", SPEC_PREFIX + "MasterSpec") is not None:
        ruleset = spec_rule_db.parse_xlsx(content, product=product, version=version or "product-pack")
        blank = [r.get("rule_id") or r.get("attribute") for r in ruleset.get("rules", []) if not str(r.get("expected", "")).strip()]
        if blank:
            warnings.append(f"MasterSpec: 기대값(Official Value)이 빈 룰 {len(blank)}건 — 채우기 전까지 해당 없음으로 판정됩니다: {', '.join(map(str, blank[:6]))}{'…' if len(blank) > 6 else ''}")
        info = spec_rule_db.save(product, ruleset, version=version or "product-pack")
        applied["스펙 룰"] = {"rules": len(ruleset.get("rules", [])), "previous_models": len(ruleset.get("previous_models", [])),
                           "dictionary": len(ruleset.get("dictionary", {})), **{k: v for k, v in (info or {}).items() if k in ("version", "updated_at")}}

    # 4) 스키마 정답값
    if _find(wb, "스키마_블록") is not None and _find(wb, "스키마_기대값") is not None:
        parsed, w = svx.parse_xlsx(content)
        warnings += w
        saved = svx.save_uploaded(parsed)
        applied["스키마 정답값"] = {"products": saved["saved_products"],
                                 "blocks": {p: len(v.get("blocks", {})) for p, v in parsed.items()}}
        try:
            import runner
            runner.reset_schema_values_cache()
        except Exception:
            pass
    return {"product": product, "applied": applied, "warnings": warnings}

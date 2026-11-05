"""
schema_values_xlsx.py — 큐비 — 스키마 정답값(schema_values) 엑셀 템플릿 내보내기/가져오기  [2026-11 신규]

배경(PPT 4번): 스키마 정답값은 언팩(신제품)마다 바뀌고 때로는 블록 구성까지 달라지는데, 지금까지는
`schema_values.part*.json` 을 손으로 편집해야 했다. Spec Rule DB(엑셀 업로드)와 같은 방식으로
"템플릿 내려받기 → 채우기 → 업로드" 왕복을 지원한다. 구조(무엇을 검사할지: schema_rules.*.json)는 그대로 두고
값(제품별 @id 패턴·기대값·hasPart·제품명 토큰)만 이 엑셀로 다룬다.

엑셀 양식(시트 4개, 모두 1행 머리글):
  0_안내      — 작성 규칙(자리표시자·종류/검사 어휘·다중 블록 접두어 규칙)
  1_제품      — 제품키 | 제품 표시명 | 모델 토큰(model_any) | 등급 토큰(tier_any) | 금지 토큰(forbid_any) | 모델 라벨 | 등급 라벨 | 메모
  2_블록      — 제품키 | 페이지(PDP/Compare) | 블록 | @id 패턴 | hasPart 참조(줄바꿈/쉼표 구분)
  3_기대값    — 제품키 | 페이지 | 블록 | 속성 | 기대값 | 종류(kind) | 검사(check) | 중첩키(nested) | 비고

자리표시자: {SITECODE} = 국가 코드(uk/fr…), {PD_URL} = 실제 크롤된 제품 페이지 URL(워치처럼 국가별 URL 이 다를 때),
           {BCP47-LANG} = 사이트 언어코드. 다중 블록(Video/Quotation/Comment/3DModel)은 '#video-1' 처럼 접두어-번호만 적으면
           실제 '#video-form-factor' 등 같은 접두어의 @id 를 모두 정상으로 본다(schema_checker D3).

저장: 업로드된 값은 `schema_values.uploaded.json` 에 제품키 단위로 저장되고 part*.json 의 같은 제품키를 덮어쓴다
(seed 파일은 건드리지 않음 → 되돌리려면 uploaded 에서 그 제품을 지우면 된다). 이력은 `schema_values.history/` 에
타임스탬프 파일로 남긴다.
"""
from __future__ import annotations
import io
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HERE = os.path.dirname(os.path.abspath(__file__))
UPLOADED_PATH = os.path.join(_HERE, "schema_values.uploaded.json")
HISTORY_DIR = os.path.join(_HERE, "schema_values.history")

KINDS = ["url", "enum", "name_token", "image_path", "text", "exist", "inlanguage", "date_fmt", "duration_fmt"]
CHECKS = ["정확히_일치", "제품명_올바른지", "경로_구조", "존재만_확인", "언어코드", "날짜_형식만", "영상길이_형식만"]
KIND_DEFAULT_CHECK = {"url": "정확히_일치", "enum": "정확히_일치", "name_token": "제품명_올바른지", "image_path": "경로_구조",
                      "text": "존재만_확인", "exist": "존재만_확인", "inlanguage": "언어코드", "date_fmt": "날짜_형식만",
                      "duration_fmt": "영상길이_형식만"}

HEAD_FILL = PatternFill("solid", fgColor="1B2A4A")
HEAD_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial", size=10)
EXAMPLE_FILL = PatternFill("solid", fgColor="E7F6EC")   # 예시 행(초록) — 지우고 실제 값으로 교체
INPUT_FILL = PatternFill("solid", fgColor="FFF6DA")     # 입력 칸 안내(노랑)
SHEETS = {
    "1_제품": ["제품키", "제품 표시명", "모델 토큰(model_any, 쉼표)", "등급 토큰(tier_any, 쉼표)", "금지 토큰(forbid_any, 쉼표)",
             "모델 라벨", "등급 라벨", "메모"],
    "2_블록": ["제품키", "페이지(PDP/Compare)", "블록(스키마 타입)", "@id 패턴", "hasPart 참조(쉼표/줄바꿈)"],
    "3_기대값": ["제품키", "페이지(PDP/Compare)", "블록(스키마 타입)", "속성", "기대값", "종류(kind)", "검사(check)", "중첩키(nested)", "비고"],
}
GUIDE_ROWS = [
    ("용도", "제품별 스키마(JSON-LD) 정답값을 이 엑셀로 등록합니다. 구조(검사 항목)는 코드에 있고, 여기에는 '값'만 적습니다."),
    ("작성 순서", "① 1_제품에 제품 1행 → ② 2_블록에 블록별 @id 패턴·hasPart → ③ 3_기대값에 속성별 기대값. 초록색 예시 행은 지우고 실제 값으로 바꾸세요."),
    ("제품키", "URL 슬러그와 같게 (예: galaxy-z-fold8, galaxy-watch8). 세 시트의 제품키가 서로 같아야 합니다."),
    ("자리표시자", "{SITECODE}=국가코드(uk/fr…), {PD_URL}=실제 크롤된 제품 페이지 URL(국가별 URL 이 다른 워치·버즈용), {BCP47-LANG}=사이트 언어코드. 그대로 적으면 런타임에 치환됩니다."),
    ("@id 패턴", "https:// 로 시작하는 전체 URL. 예: https://www.samsung.com/{SITECODE}/smartphones/galaxy-z-fold8/#webpage"),
    ("여러 개 블록", "VideoObject·Quotation·Comment·3DModel 은 캠페인마다 개수·이름이 다릅니다. '#video-1' 처럼 접두어-번호만 적으면 같은 접두어(#video-…)의 @id 는 모두 정상으로 봅니다. hasPart 도 접두어 항목은 '페이지에 있는 그 타입 노드가 모두 연결됐는가'로 검사합니다."),
    ("종류(kind)", " / ".join(KINDS) + "  — url: @id·URL 정확 일치 · enum: @type 등 열거값 · name_token: 제품명 토큰 · image_path: 경로에 제품 슬러그 포함 · text: 값 존재(비영어 사이트의 영어 원문은 참고 표시) · exist: 존재만 · inlanguage: 사이트 언어 일치 · date_fmt/duration_fmt: ISO 형식"),
    ("검사(check)", " / ".join(CHECKS) + "  — 비우면 종류에 맞는 기본값이 들어갑니다."),
    ("중첩키(nested)", "값이 객체일 때 비교할 안쪽 키. 보통 @id (예: brand → {\"@id\": …}) 또는 @type (potentialAction → BuyAction)."),
    ("조건부 블록", "Quotation 처럼 있어도 되고 없어도 되는 블록은 코드 구조(schema_rules)에서 conditional 로 관리합니다 — 값만 적으면 됩니다."),
    ("저장 방식", "업로드하면 schema_values.uploaded.json 에 제품키 단위로 저장되어 기존 seed 값을 덮어씁니다. 이력은 schema_values.history 폴더에 남습니다."),
]


def _style_header(ws, headers: List[str], widths: List[int]):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.freeze_panes = "A2"


def _write_rows(ws, rows: List[List[Any]], fill: Optional[PatternFill] = None):
    for r in rows:
        ws.append(r)
        for c in ws[ws.max_row]:
            c.font = BODY_FONT
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if fill is not None:
                c.fill = fill


def _product_rows(product: str, sv: Dict[str, Any]) -> Tuple[List[List[Any]], List[List[Any]], List[List[Any]]]:
    nt = sv.get("name_tokens") or {}
    prod_rows = [[product, nt.get("model_label") or product, ", ".join(nt.get("model_any") or []),
                  ", ".join(nt.get("tier_any") or []), ", ".join(nt.get("forbid_any") or []),
                  nt.get("model_label", ""), nt.get("tier_label", ""), sv.get("_note", "")]]
    block_rows: List[List[Any]] = []
    value_rows: List[List[Any]] = []
    for page, key in (("PDP", "blocks"), ("Compare", "compare_blocks")):
        for blk, lst in (sv.get(key) or {}).items():
            for b in (lst if isinstance(lst, list) else [lst]):
                block_rows.append([product, page, blk, b.get("id_pattern", ""), "\n".join(b.get("haspart_ids") or [])])
                for prop, spec in (b.get("expected_values") or {}).items():
                    value_rows.append([product, page, blk, prop, spec.get("value", ""), spec.get("kind", ""),
                                       spec.get("check", ""), spec.get("nested") or "", ""])
    return prod_rows, block_rows, value_rows


def _new_workbook(with_guide: bool = True) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "0_안내"
    _style_header(ws, ["항목", "내용"], [16, 110])
    _write_rows(ws, [list(r) for r in GUIDE_ROWS])
    for c in ws["A"][1:]:
        c.font = Font(name="Arial", size=10, bold=True)
    for name, heads in SHEETS.items():
        w = wb.create_sheet(name)
        widths = {"1_제품": [20, 20, 28, 22, 22, 14, 12, 40], "2_블록": [20, 14, 22, 70, 60],
                  "3_기대값": [20, 14, 22, 22, 60, 14, 16, 12, 30]}[name]
        _style_header(w, heads, widths)
    return wb


def build_template_xlsx(example_product: Optional[str] = None, values: Optional[Dict[str, Any]] = None) -> bytes:
    """빈 템플릿(+ 초록 예시 행 1세트). values 를 주면 그 제품을 예시로 쓴다."""
    wb = _new_workbook()
    ex = None
    if values:
        if example_product and example_product in values:
            ex = (example_product, values[example_product])
        elif values:
            k = sorted(values.keys())[0]
            ex = (k, values[k])
    if ex:
        p, b, v = _product_rows(*ex)
        _write_rows(wb["1_제품"], p, EXAMPLE_FILL)
        _write_rows(wb["2_블록"], b, EXAMPLE_FILL)
        _write_rows(wb["3_기대값"], v, EXAMPLE_FILL)
        for name in ("1_제품", "2_블록", "3_기대값"):
            ws = wb[name]
            ws.append(["(예시 행은 지우고 여기부터 실제 값을 적으세요)"])
            ws.cell(row=ws.max_row, column=1).fill = INPUT_FILL
            ws.cell(row=ws.max_row, column=1).font = Font(name="Arial", size=10, italic=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_export_xlsx(product: str, values: Dict[str, Any]) -> bytes:
    """지금 저장된 제품 값을 템플릿 형식으로 — 수정 후 그대로 재업로드 가능."""
    sv = values.get(product)
    if not sv:
        raise ValueError(f"'{product}' 의 스키마 정답값이 없습니다.")
    wb = _new_workbook()
    p, b, v = _product_rows(product, sv)
    _write_rows(wb["1_제품"], p)
    _write_rows(wb["2_블록"], b)
    _write_rows(wb["3_기대값"], v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── 가져오기 ──────────────────────────────────────────────────────────
def _split_list(s: Any) -> List[str]:
    return [x.strip() for x in re.split(r"[,\n;]", str(s or "")) if x and x.strip()]


def _is_placeholder_row(row: List[Any]) -> bool:
    first = str(row[0] or "").strip() if row else ""
    return (not first) or first.startswith("(예시")


def _find_ws(wb, *keys):
    for name in wb.sheetnames:
        low = name.lower()
        if any(k.lower() in low for k in keys):
            return wb[name]
    return None


def _header_index(ws) -> Dict[str, int]:
    """1행 머리글 → 열 번호. 머리글의 괄호 앞 부분(예: '모델 토큰')으로도 찾을 수 있게 둘 다 등록."""
    idx: Dict[str, int] = {}
    for i, c in enumerate(next(ws.iter_rows(min_row=1, max_row=1, values_only=True), [])):
        h = str(c or "").strip()
        if not h:
            continue
        idx[h] = i
        idx[re.split(r"[(（]", h)[0].strip()] = i
    return idx


def _col(row, idx: Dict[str, int], *names, default=""):
    for n in names:
        i = idx.get(n)
        if i is not None and i < len(row) and row[i] not in (None, ""):
            return row[i]
    return default


def parse_xlsx(content: bytes) -> Tuple[Dict[str, Any], List[str]]:
    """엑셀 → {제품키: {blocks, compare_blocks, name_tokens}} + 경고 목록. 치명 오류는 ValueError.
    [2026-11] 머리글 이름 기준으로 읽고 시트는 이름 부분 일치('제품'·'블록'·'기대값')로 찾는다 —
    독립 템플릿(1_제품/2_블록/3_기대값)과 제품 등록 워크북(제품정보/스키마_블록/스키마_기대값) 둘 다 처리."""
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws_p, ws_b, ws_v = _find_ws(wb, "제품정보", "1_제품", "제품"), _find_ws(wb, "스키마_블록", "2_블록", "블록"), _find_ws(wb, "스키마_기대값", "3_기대값", "기대값")
    if ws_p is None or ws_b is None or ws_v is None:
        raise ValueError("시트(제품 / 블록 / 기대값)가 없습니다. 템플릿 양식을 그대로 사용하세요.")
    warnings: List[str] = []
    out: Dict[str, Any] = {}

    def rows(ws):
        for r in ws.iter_rows(min_row=2, values_only=True):
            r = list(r) + [None] * 16
            if _is_placeholder_row(r):
                continue
            yield r

    ip = _header_index(ws_p)
    for r in rows(ws_p):
        key = str(_col(r, ip, "제품키")).strip()
        if not key:
            continue
        label = str(_col(r, ip, "제품 표시명", default=key)).strip()
        out[key] = {"blocks": {}, "compare_blocks": {}, "_note": str(_col(r, ip, "메모")).strip(),
                    "name_tokens": {"model_any": _split_list(_col(r, ip, "모델 토큰")), "tier_any": _split_list(_col(r, ip, "등급 토큰")),
                                    "forbid_any": _split_list(_col(r, ip, "금지 토큰")),
                                    "model_label": str(_col(r, ip, "모델 라벨", default=label)).strip(),
                                    "tier_label": str(_col(r, ip, "등급 라벨")).strip()}}
    if not out:
        raise ValueError("제품 시트에 제품 행이 없습니다.")

    ib = _header_index(ws_b)
    for r in rows(ws_b):
        key, page = str(_col(r, ib, "제품키")).strip(), str(_col(r, ib, "페이지", default="PDP")).strip()
        blk, idp = str(_col(r, ib, "블록")).strip(), str(_col(r, ib, "@id 패턴")).strip()
        if key not in out:
            raise ValueError(f"블록 시트: 제품키 '{key}' 가 제품 시트에 없습니다.")
        if not blk:
            raise ValueError(f"블록 시트: 제품 '{key}' 에 블록명이 빈 행이 있습니다.")
        if idp and not idp.startswith("http"):
            raise ValueError(f"블록 시트: {key}/{blk} @id 패턴은 https:// 로 시작해야 합니다 ('{idp}')")
        tgt = out[key]["compare_blocks" if page.lower() == "compare" else "blocks"]
        tgt.setdefault(blk, []).append({"id_pattern": idp, "expected_values": {}, "haspart_ids": _split_list(_col(r, ib, "hasPart 참조"))})

    iv = _header_index(ws_v)
    for r in rows(ws_v):
        key, page = str(_col(r, iv, "제품키")).strip(), str(_col(r, iv, "페이지", default="PDP")).strip()
        blk, prop = str(_col(r, iv, "블록")).strip(), str(_col(r, iv, "속성")).strip()
        value, kind = str(_col(r, iv, "기대값")).strip(), str(_col(r, iv, "종류")).strip()
        check, nested = str(_col(r, iv, "검사")).strip(), str(_col(r, iv, "중첩키")).strip()
        if key not in out:
            raise ValueError(f"기대값 시트: 제품키 '{key}' 가 제품 시트에 없습니다.")
        tgt = out[key]["compare_blocks" if page.lower() == "compare" else "blocks"]
        if blk not in tgt:
            raise ValueError(f"기대값 시트: {key}/{page}/{blk} 블록이 블록 시트에 없습니다. 블록 시트에 먼저 추가하세요.")
        if not prop:
            raise ValueError(f"기대값 시트: {key}/{blk} 에 속성명이 빈 행이 있습니다.")
        if kind and kind not in KINDS:
            raise ValueError(f"기대값 시트: {key}/{blk}/{prop} 종류 '{kind}' 는 허용 목록({', '.join(KINDS)})에 없습니다.")
        if not kind:
            kind = "exist" if not value else ("url" if value.startswith("http") else "text")
            warnings.append(f"{key}/{blk}/{prop}: 종류가 비어 '{kind}' 로 추정")
        if check and check not in CHECKS:
            raise ValueError(f"기대값 시트: {key}/{blk}/{prop} 검사 '{check}' 는 허용 목록({', '.join(CHECKS)})에 없습니다.")
        if not check:
            check = KIND_DEFAULT_CHECK[kind]
        if kind == "url" and value and not (value.startswith("http") or value.startswith("{")):
            warnings.append(f"{key}/{blk}/{prop}: url 종류인데 값이 URL 로 보이지 않음 ('{value[:40]}')")
        tgt[blk][0]["expected_values"][prop] = {"value": value, "kind": kind, "check": check, "nested": nested or None}

    for key, sv in out.items():
        if not sv["blocks"] and not sv["compare_blocks"]:
            warnings.append(f"{key}: 블록이 하나도 없음 — 구조 검사만 수행됨")
        if not sv["compare_blocks"]:
            sv.pop("compare_blocks")
    return out, warnings


def load_uploaded() -> Dict[str, Any]:
    if os.path.exists(UPLOADED_PATH):
        try:
            return json.load(open(UPLOADED_PATH, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_uploaded(parsed: Dict[str, Any]) -> Dict[str, Any]:
    cur = load_uploaded()
    cur.update(parsed)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    hist = os.path.join(HISTORY_DIR, f"{stamp}_{'_'.join(sorted(parsed.keys()))[:60]}.json")
    json.dump(parsed, open(hist, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(cur, open(UPLOADED_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"saved_products": sorted(parsed.keys()), "history_file": os.path.basename(hist)}


def delete_uploaded(product: str) -> bool:
    cur = load_uploaded()
    if product not in cur:
        return False
    cur.pop(product)
    json.dump(cur, open(UPLOADED_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return True

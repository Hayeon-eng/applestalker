"""
monitor_targets_xlsx.py — 모니터링 대상 워크북 (템플릿 ②)  [2026-11 신규]

appleStalker 의 모니터링 URL(당사·경쟁사)과 honeyComb 의 국가·제품·경쟁사 모델·키워드를 엑셀 1개로 내려받고(현재 값),
고쳐서 올린다. 시트:
  0_안내
  AS_URL        site_key · url · enabled(Y/N) · tier(자동) · page_role(자동) · source(seed/db, 내보내기 전용)
  HC_국가        code · label · sitecode · gl · hl · storefront · currency
  HC_제품        slug · label · report_names(쉼표)
  HC_경쟁사모델   brand · model · compare_to(쉼표: 삼성 제품 slug)
  HC_키워드      product · text · type(brand/generic/longtail…) · subtype · countries(쉼표, 비우면 전체) · enabled(Y/N) · note

반영 규칙
  AS_URL   : Y → monitored_urls 에 추가/활성화, N → 비활성(시드 URL 도 N 이면 크롤 대상에서 제외). mode=replace 면 파일에 있는
             site_key 의, 파일에 없는 URL 은 전부 N 처리.
  HC_*     : 시트가 있고 행이 있으면 그 목록을 통째로 교체(hc_config.json countries/products/competitors). 키워드는 id(product:type:text)
             기준 upsert, mode=replace 면 통째로 교체. 이력은 honeycomb/hc_config.history/ 에 저장.
"""
from __future__ import annotations
import io
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

_HERE = os.path.dirname(os.path.abspath(__file__))
HC_DIR = os.path.join(_HERE, "honeycomb")
HC_CONFIG = os.path.join(HC_DIR, "hc_config.json")
HC_KEYWORDS = os.path.join(HC_DIR, "hc_keywords.json")
HC_HISTORY = os.path.join(HC_DIR, "hc_config.history")

HEAD_FILL = PatternFill("solid", fgColor="1B2A4A"); HEAD_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial", size=10); EXAMPLE_FILL = PatternFill("solid", fgColor="E7F6EC")
SHEETS = {
    "AS_URL": ["site_key", "url", "enabled(Y/N)", "tier(자동)", "page_role(자동)", "source(내보내기 전용)"],
    "HC_국가": ["code", "label", "sitecode", "gl", "hl", "storefront", "currency"],
    "HC_제품": ["slug", "label", "report_names(쉼표)"],
    "HC_경쟁사모델": ["brand", "model", "compare_to(쉼표: 삼성 제품 slug)"],
    "HC_키워드": ["product", "text", "type", "subtype", "countries(쉼표, 비우면 전체)", "enabled(Y/N)", "note"],
}
WIDTHS = {"AS_URL": [16, 80, 12, 10, 14, 16], "HC_국가": [8, 20, 10, 6, 6, 12, 10], "HC_제품": [24, 24, 30],
          "HC_경쟁사모델": [10, 22, 50], "HC_키워드": [24, 36, 12, 10, 24, 12, 30]}
GUIDE = [
    ("이 파일은", "appleStalker 모니터링 URL(당사·경쟁사)과 honeyComb 국가·제품·경쟁사 모델·키워드를 한 번에 관리하는 워크북입니다. '현재 값'을 받아 고친 뒤 업로드하세요(관리자 비밀번호)."),
    ("AS_URL", "site_key = appleStalker 사이트 키(비우면 도메인으로 추정). enabled = Y/N — N 이면 크롤 대상에서 제외(코드에 들어있는 시드 URL 도 N 가능). tier·page_role·source 는 자동 계산·표시용."),
    ("업로드 모드", "갱신(기본): 파일의 Y/N 만 반영 · 교체: 파일에 있는 site_key 에서 파일에 없는 URL 은 모두 N, 키워드도 파일 내용으로 통째 교체"),
    ("HC_국가", "code=리포트 국가 코드(US/UK…), sitecode=큐비 사이트코드, gl/hl=Google 파라미터, storefront/currency=피드 식별. 행이 1개 이상이면 목록을 통째로 교체."),
    ("HC_제품", "slug 는 큐비 제품키와 같게(galaxy-z-fold9), report_names 는 사람 리포트 표기(Fold9). 통째로 교체."),
    ("HC_경쟁사모델", "brand(apple) · model(iPhone 18 Pro) · compare_to(비교할 삼성 제품 slug, 쉼표). HC_제품에 없는 slug 는 업로드가 거부됩니다. 통째로 교체."),
    ("HC_키워드", "product:type:text 가 id. 갱신 모드면 같은 id 는 덮어쓰고 나머지는 유지, 교체 모드면 통째로 교체. countries 비우면 전체 국가."),
    ("색", "초록 = 예시 행(지우고 실제 값으로) · 드롭다운이 있는 열은 목록에서 고르세요."),
]
SHEET_DESC = [("AS_URL", "appleStalker 모니터링 URL (monitored_urls)", "선택"), ("HC_국가", "honeyComb 국가 (hc_config.countries)", "선택"),
              ("HC_제품", "honeyComb 제품 (hc_config.products)", "선택"), ("HC_경쟁사모델", "honeyComb Apple 비교 모델 (hc_config.competitors)", "선택"),
              ("HC_키워드", "honeyComb 검색 키워드 (hc_keywords)", "선택")]
TAB_COLOR = {"AS_URL": "1F9E5C", "HC_국가": "E0A008", "HC_제품": "E0A008", "HC_경쟁사모델": "E0A008", "HC_키워드": "E0A008"}
_THIN = Side(style="thin", color="E4E9F2")


def _style_header(ws, headers, widths):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h); c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.freeze_panes = "A2"


def _append(ws, row, fill=None):
    ws.append(row)
    for c in ws[ws.max_row]:
        c.font = BODY_FONT; c.alignment = Alignment(wrap_text=True, vertical="top")
        if fill is not None:
            c.fill = fill


def _list_validation(ws, col_letter: str, options: List[str], title: str = ""):
    formula = '"' + ",".join(options) + '"'
    if len(formula) > 255:
        return
    dv = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=False, showInputMessage=bool(title),
                        promptTitle=title or None, prompt=("목록에서 선택: " + ", ".join(options)) if title else None)
    ws.add_data_validation(dv); dv.add(f"{col_letter}2:{col_letter}1000")


def _finish(wb: Workbook, site_keys: Optional[List[str]] = None):
    for ws in wb.worksheets:
        ws.row_dimensions[1].height = 30
        ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{max(ws.max_row, 2)}"
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
            for c in row:
                c.border = Border(bottom=_THIN)
        ws.sheet_properties.tabColor = TAB_COLOR.get(ws.title, "1B2A4A")
    if site_keys:
        _list_validation(wb["AS_URL"], "A", site_keys, "site_key")
    _list_validation(wb["AS_URL"], "C", ["Y", "N"], "enabled")
    _list_validation(wb["HC_키워드"], "C", ["brand", "generic", "longtail", "feature", "compare"], "type")
    _list_validation(wb["HC_키워드"], "F", ["Y", "N"], "enabled")
    _list_validation(wb["HC_경쟁사모델"], "A", ["apple", "google", "xiaomi", "oppo", "vivo"], "brand")
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def _new_wb() -> Workbook:
    wb = Workbook(); ws = wb.active; ws.title = "0_안내"
    _style_header(ws, ["항목", "내용"], [16, 120])
    for k, v in GUIDE:
        _append(ws, [k, v]); ws.cell(ws.max_row, 1).font = Font(name="Arial", size=10, bold=True)
    ws.append([]); ws.append(["시트", "반영 대상", "필수 여부"])
    for c in ws[ws.max_row]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT
    ws.column_dimensions["C"].width = 16
    for row in SHEET_DESC:
        _append(ws, list(row))
    for name, heads in SHEETS.items():
        _style_header(wb.create_sheet(name), heads, WIDTHS[name])
    return wb


def _yn(v) -> str:
    return "Y" if v in (True, 1, "1", "Y", "y", "yes", "true", "True", "TRUE") else "N"


def _load_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def current_rows(as_urls: List[Dict[str, Any]]) -> Dict[str, List[List[Any]]]:
    """as_urls: [{site_key,url,enabled,tier_level,page_role,source}] — main.py 가 시드+DB 를 합쳐 넘긴다."""
    cfg = _load_json(HC_CONFIG, {}); kw = _load_json(HC_KEYWORDS, {"keywords": []})
    return {
        "AS_URL": [[u.get("site_key"), u.get("url"), _yn(u.get("enabled", True)), u.get("tier_level", ""), u.get("page_role", ""), u.get("source", "")] for u in as_urls],
        "HC_국가": [[c.get("code"), c.get("label"), c.get("sitecode"), c.get("gl"), c.get("hl"), c.get("storefront", ""), c.get("currency", "")] for c in cfg.get("countries", [])],
        "HC_제품": [[p.get("slug"), p.get("label"), ", ".join(p.get("report_names") or [])] for p in cfg.get("products", [])],
        "HC_경쟁사모델": [[c.get("brand"), c.get("model"), ", ".join(c.get("compare_to") or [])] for c in cfg.get("competitors", [])],
        "HC_키워드": [[k.get("product"), k.get("text"), k.get("type"), k.get("subtype", ""), ", ".join(k.get("countries") or []),
                     _yn(k.get("enabled", True)), k.get("note", "")] for k in kw.get("keywords", [])],
    }


def build_template(as_urls: List[Dict[str, Any]]) -> bytes:
    wb = _new_wb(); rows = current_rows(as_urls)
    for name in SHEETS:
        for r in rows[name][:3]:
            _append(wb[name], r, EXAMPLE_FILL)
    return _finish(wb, sorted({u.get("site_key") for u in as_urls if u.get("site_key")}))


def build_export(as_urls: List[Dict[str, Any]]) -> bytes:
    wb = _new_wb(); rows = current_rows(as_urls)
    for name in SHEETS:
        for r in rows[name]:
            _append(wb[name], r)
    return _finish(wb, sorted({u.get("site_key") for u in as_urls if u.get("site_key")}))


def _rows(ws):
    heads = [str(c or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    key = lambda h: re.split(r"[(（]", h)[0].strip().lower()
    idx = {key(h): i for i, h in enumerate(heads) if h}
    for r in ws.iter_rows(min_row=2, values_only=True):
        r = list(r) + [None] * 10
        if all(v in (None, "") for v in r) or str(r[0] or "").startswith("(예시"):
            continue
        yield {k: (str(r[i]).strip() if r[i] not in (None, "") else "") for k, i in idx.items()}


def _split(s: str) -> List[str]:
    return [x.strip() for x in re.split(r"[,\n;]", s or "") if x.strip()]


def parse(content: bytes) -> Dict[str, List[Dict[str, str]]]:
    wb = load_workbook(io.BytesIO(content), data_only=True)
    out: Dict[str, List[Dict[str, str]]] = {}
    for name in SHEETS:
        if name in wb.sheetnames:
            out[name] = list(_rows(wb[name]))
    if not out:
        raise ValueError("AS_URL / HC_국가 / HC_제품 / HC_경쟁사모델 / HC_키워드 시트가 하나도 없습니다. 템플릿 양식을 그대로 사용하세요.")
    return out


def apply_hc(parsed: Dict[str, List[Dict[str, str]]], mode: str = "upsert") -> Dict[str, Any]:
    """honeyComb 설정 반영. 반환: 시트별 건수."""
    cfg = _load_json(HC_CONFIG, {}); kw = _load_json(HC_KEYWORDS, {"keywords": []})
    applied: Dict[str, Any] = {}
    os.makedirs(HC_HISTORY, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    json.dump({"config": cfg, "keywords": kw}, open(os.path.join(HC_HISTORY, f"{stamp}_before.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if parsed.get("HC_국가"):
        rows = parsed["HC_국가"]
        for r in rows:
            if not (r.get("code") and r.get("gl") and r.get("hl")):
                raise ValueError(f"HC_국가: code/gl/hl 은 필수 — {r}")
        cfg["countries"] = [{"code": r["code"].upper(), "label": r.get("label") or r["code"], "sitecode": r.get("sitecode", "").lower(),
                             "gl": r["gl"].lower(), "hl": r["hl"].lower(), "storefront": r.get("storefront", ""), "currency": r.get("currency", "").upper()} for r in rows]
        applied["HC_국가"] = len(rows)
    if parsed.get("HC_제품"):
        rows = parsed["HC_제품"]
        for r in rows:
            if not re.match(r"^[a-z0-9\-]+$", r.get("slug", "")):
                raise ValueError(f"HC_제품: slug 는 소문자·숫자·하이픈 — '{r.get('slug')}'")
        old = {p.get("slug"): p for p in cfg.get("products", [])}
        cfg["products"] = [{**old.get(r["slug"], {}), "slug": r["slug"], "label": r.get("label") or r["slug"], "report_names": _split(r.get("report_names", ""))} for r in rows]
        applied["HC_제품"] = len(rows)
    if parsed.get("HC_경쟁사모델"):
        rows = parsed["HC_경쟁사모델"]
        slugs = {p["slug"] for p in cfg.get("products", [])}
        for r in rows:
            if not (r.get("brand") and r.get("model")):
                raise ValueError(f"HC_경쟁사모델: brand/model 필수 — {r}")
            unknown = [s for s in _split(r.get("compare_to", "")) if s not in slugs]
            if unknown:
                raise ValueError(f"HC_경쟁사모델: compare_to 의 '{', '.join(unknown)}' 는 HC_제품 에 없는 slug")
        cfg["competitors"] = [{"brand": r["brand"].lower(), "model": r["model"], "compare_to": _split(r.get("compare_to", ""))} for r in rows]
        applied["HC_경쟁사모델"] = len(rows)
    if cfg:
        json.dump(cfg, open(HC_CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if parsed.get("HC_키워드"):
        rows = parsed["HC_키워드"]
        items = []
        for r in rows:
            if not (r.get("product") and r.get("text")):
                raise ValueError(f"HC_키워드: product/text 필수 — {r}")
            kt = r.get("type") or "brand"
            items.append({"id": f"{r['product']}:{kt}:{r['text']}", "product": r["product"], "text": r["text"], "type": kt,
                          "subtype": r.get("subtype", ""), "countries": _split(r.get("countries", "")), "enabled": _yn(r.get("enabled", "Y")) == "Y",
                          "note": r.get("note", "")})
        if mode == "replace":
            kw["keywords"] = items
        else:
            by_id = {k.get("id"): k for k in kw.get("keywords", [])}
            for it in items:
                by_id[it["id"]] = {**by_id.get(it["id"], {}), **it}
            kw["keywords"] = list(by_id.values())
        json.dump(kw, open(HC_KEYWORDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        applied["HC_키워드"] = {"rows": len(items), "total": len(kw["keywords"]), "mode": mode}
    return applied


def as_url_plan(parsed_rows: List[Dict[str, str]], site_key_for_url, mode: str = "upsert",
                current: Optional[List[Dict[str, Any]]] = None) -> Tuple[List[Tuple[str, str, bool]], List[str]]:
    """AS_URL 행 → [(site_key, url, enabled)] 계획. mode=replace 면 파일에 있는 site_key 의 미기재 URL 은 비활성 계획에 추가."""
    plan: List[Tuple[str, str, bool]] = []; warnings: List[str] = []
    seen = set()
    for r in parsed_rows:
        url = r.get("url", "")
        if not url.startswith("http"):
            warnings.append(f"AS_URL: URL 형식 오류 — '{url[:50]}'"); continue
        sk = r.get("site_key") or site_key_for_url(url) or "unknown"
        if sk == "unknown":
            warnings.append(f"AS_URL: site_key 를 알 수 없음 — {url[:60]} (site_key 를 적어주세요)"); continue
        plan.append((sk, url, _yn(r.get("enabled", "Y")) == "Y")); seen.add((sk, url))
    if mode == "replace" and current:
        keys = {sk for sk, _, _ in plan}
        for u in current:
            if u.get("site_key") in keys and (u["site_key"], u["url"]) not in seen:
                plan.append((u["site_key"], u["url"], False))
    return plan, warnings

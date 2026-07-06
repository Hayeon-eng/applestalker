"""
qa_report.py — 큐비 — Dotcom QA 체커 [Phase G]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

검수 결과(스키마 + 카피)를 모아:
  (1) Excel 리포트 — 시트 2개
        · 스키마 탭: URL 1줄 = 타입별 O/△/X + 발견(as-is) + TO-BE 가이드
        · 카피 탭  : URL 1줄 = 스펙 결과/누락 + 고유명사 결과/누락 + TO-BE 가이드
  (2) 메일 초안(HTML) — 사이트별 오류 요약

입력(page_results):
  [{"sitecode","url","region","country","product"(선택),"page_type"(선택),
    "schema": <schema_checker.check_page 결과>,
    "copy":   <copy_checker.check_copy 결과>}, ...]
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import Any, Dict, List

SEV_KO = {"fail": "오류", "warn": "확인", "pass": "정상"}
SEV_COLOR = {"fail": "D8362F", "warn": "E0A008", "pass": "1F9E5C"}
MARK = {"pass": "O", "warn": "△", "fail": "X", "-": "-"}
MARK_COLOR = {"pass": "1F9E5C", "warn": "E0A008", "fail": "D8362F", "-": "98A2B3"}
_TYPE_ORDER = ["WebPage", "ItemList", "Product", "3DModel", "ImageObject",
               "VideoObject", "FAQPage", "BreadcrumbList"]
_WORST = {"pass": 0, "warn": 1, "fail": 2}


# ── 공통 헬퍼 ──
def _primary_type(f: Dict[str, Any]) -> str:
    t = f.get("types")
    if isinstance(t, list) and t:
        return "WebPage" if t[0] in ("WebPage", "ItemPage") else t[0]
    return (f.get("block", "기타") or "기타").split(",")[0].strip()


def _worse(a: str, b: str) -> str:
    return a if _WORST.get(a, 0) >= _WORST.get(b, 0) else b


def _page_type(url: str) -> str:
    u = (url or "").lower()
    if "/compare" in u:
        return "Compare"
    if "/buy" in u or "/buying" in u:
        return "Buying"
    return "PDP"


def _flatten(page_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """오류/확인 행 평탄화(메일 초안용). 정상은 제외."""
    rows: List[Dict[str, Any]] = []
    for pr in page_results:
        base = {"sitecode": pr.get("sitecode", ""), "url": pr.get("url", ""),
                "region": pr.get("region", ""), "country": pr.get("country", "")}
        for f in (pr.get("schema") or {}).get("findings", []):
            if f.get("status") == "pass":
                continue
            rows.append({**base, "area": "스키마", "item": f.get("block", ""),
                         "status": f.get("status"), "as_is": f.get("as_is", ""), "to_be": f.get("to_be", "")})
        for f in (pr.get("copy") or {}).get("findings", []):
            if f.get("status") == "pass":
                continue
            rows.append({**base, "area": "카피·" + (f.get("kind", "") or ""), "item": f.get("token", ""),
                         "status": f.get("status"), "as_is": f.get("as_is", ""), "to_be": f.get("to_be", "")})
    return rows


def summary_counts(page_results: List[Dict[str, Any]]) -> Dict[str, int]:
    rows = _flatten(page_results)
    return {"pages": len(page_results),
            "fail": sum(1 for r in rows if r["status"] == "fail"),
            "warn": sum(1 for r in rows if r["status"] == "warn"),
            "issues": len(rows)}


# ── 스키마 탭 행 뷰 ──
def _schema_row(pr: Dict[str, Any]):
    type_status: Dict[str, str] = {}
    as_is, to_be = [], []
    for f in (pr.get("schema") or {}).get("findings", []):
        ty = _primary_type(f)
        type_status[ty] = _worse(type_status.get(ty, "pass"), f.get("status", "pass"))
        if f.get("status") != "pass":
            if f.get("as_is"):
                as_is.append(f"[{ty}] {f['as_is']}")
            if f.get("to_be"):
                to_be.append(f"[{ty}] {f['to_be']}")
    return type_status, as_is, to_be


# ── 카피 탭 행 뷰 (URL 1줄 요약형) ──
def _copy_row(pr: Dict[str, Any]):
    findings = (pr.get("copy") or {}).get("findings", [])
    summ = (pr.get("copy") or {}).get("summary", {})
    spec_total = summ.get("spec_total", sum(1 for f in findings if f.get("kind") == "spec"))
    noun_total = summ.get("noun_total", sum(1 for f in findings if f.get("kind") == "proper_noun"))
    spec_miss = [f.get("token") for f in findings if f.get("kind") == "spec" and f.get("status") != "pass"]
    noun_miss = [f.get("token") for f in findings if f.get("kind") == "proper_noun" and f.get("status") != "pass"]
    spec_ok = spec_total - len(spec_miss)
    noun_ok = noun_total - len(noun_miss)
    guides = []
    if spec_miss:
        guides.append("누락 스펙 값이 페이지에 노출되는지 확인(오기/삭제 점검): " + ", ".join(map(str, spec_miss)))
    if noun_miss:
        guides.append("고유명사가 현지어로 대체됐는지/누락인지 확인: " + ", ".join(map(str, noun_miss)))
    return {"spec_ok": spec_ok, "spec_total": spec_total, "spec_miss": spec_miss,
            "noun_ok": noun_ok, "noun_total": noun_total, "noun_miss": noun_miss,
            "guide": "\n".join(guides)}


def build_xlsx(page_results: List[Dict[str, Any]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    thin = Side(style="thin", color="E4E7EC"); border = Border(thin, thin, thin, thin)
    hfont = Font(bold=True, color="FFFFFF"); hfill = PatternFill("solid", fgColor="1B2A4A")

    def _style_header(ws):
        for c in ws[1]:
            c.font = hfont; c.fill = hfill
            c.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    wb = Workbook()

    # ── 시트 1: 스키마 ──
    ws = wb.active; ws.title = "스키마 QA"
    seen = set()
    for pr in page_results:
        for f in (pr.get("schema") or {}).get("findings", []):
            seen.add(_primary_type(f))
    type_cols = [t for t in _TYPE_ORDER if t in seen] + sorted(seen - set(_TYPE_ORDER))
    ctx = ["#", "Region", "Country", "Site Code", "Products", "Page Type", "Target URL"]
    ws.append(ctx + type_cols + ["발견 사항 (as-is)", "TO-BE 가이드", "Remarks"])
    _style_header(ws)
    for i, pr in enumerate(page_results, 1):
        ts, as_is, to_be = _schema_row(pr)
        row = [i, pr.get("region", ""), pr.get("country", ""), pr.get("sitecode", ""),
               pr.get("product", pr.get("products", "")),
               pr.get("page_type") or _page_type(pr.get("url", "")), pr.get("url", "")]
        row += [MARK.get(ts.get(t, "-"), "-") for t in type_cols]
        row += ["\n".join(as_is), "\n".join(to_be), ""]
        ws.append(row); rn = ws.max_row
        for k, t in enumerate(type_cols):
            cell = ws.cell(row=rn, column=len(ctx) + 1 + k)
            cell.font = Font(bold=True, color=MARK_COLOR.get(ts.get(t, "-"), "98A2B3"))
            cell.alignment = Alignment(horizontal="center", vertical="center")
    widths = [4, 14, 12, 9, 10, 9, 46] + [8] * len(type_cols) + [44, 46, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for r in ws.iter_rows(min_row=2):
        for c in r:
            c.border = border
            if c.alignment.horizontal is None:
                c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "H2"

    # ── 시트 2: 카피 ──
    ws2 = wb.create_sheet("카피 QA")
    ws2.append(["#", "Region", "Country", "Site Code", "Products", "Target URL",
                "스펙 결과", "누락 스펙 (as-is)", "고유명사 결과", "누락 고유명사 (as-is)", "TO-BE 가이드", "Remarks"])
    _style_header(ws2)
    for i, pr in enumerate(page_results, 1):
        cv = _copy_row(pr)
        spec_res = f"{cv['spec_ok']}/{cv['spec_total']}"
        noun_res = f"{cv['noun_ok']}/{cv['noun_total']}"
        ws2.append([i, pr.get("region", ""), pr.get("country", ""), pr.get("sitecode", ""),
                    pr.get("product", pr.get("products", "")), pr.get("url", ""),
                    spec_res, ", ".join(map(str, cv["spec_miss"])),
                    noun_res, ", ".join(map(str, cv["noun_miss"])), cv["guide"], ""])
        rn = ws2.max_row
        # 스펙 결과 색: 누락 있으면 빨강
        ws2.cell(row=rn, column=7).font = Font(bold=True, color=SEV_COLOR["fail"] if cv["spec_miss"] else SEV_COLOR["pass"])
        ws2.cell(row=rn, column=9).font = Font(bold=True, color=SEV_COLOR["warn"] if cv["noun_miss"] else SEV_COLOR["pass"])
        for col in (7, 9):
            ws2.cell(row=rn, column=col).alignment = Alignment(horizontal="center", vertical="center")
    widths2 = [4, 14, 12, 9, 10, 46, 9, 40, 11, 40, 46, 16]
    for i, w in enumerate(widths2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    for r in ws2.iter_rows(min_row=2):
        for c in r:
            c.border = border
            if c.alignment.horizontal is None:
                c.alignment = Alignment(vertical="top", wrap_text=True)
    ws2.freeze_panes = "G2"

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def build_email_draft(page_results: List[Dict[str, Any]], when: str = "") -> str:
    from html import escape
    s = summary_counts(page_results)
    rows = _flatten(page_results)
    by_site: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_site.setdefault(r["sitecode"], []).append(r)
    blocks = ""
    for sc, items in by_site.items():
        meta = next((p for p in page_results if p.get("sitecode") == sc), {})
        lis = ""
        for it in items[:20]:
            col = "#" + SEV_COLOR.get(it["status"], "000000")
            lis += ("<div style='font-size:12.5px;line-height:1.5;margin-top:6px'>"
                    "<span style='font-size:10.5px;font-weight:700;color:#fff;background:" + col + ";padding:2px 6px;border-radius:5px'>"
                    + SEV_KO.get(it["status"], "") + "</span> "
                    "<b style='color:#101318'>" + escape(it["area"]) + " · " + escape(str(it["item"])[:40]) + "</b>"
                    "<div style='color:#475467;margin-top:2px'>as-is: " + escape(it["as_is"]) + "</div>"
                    "<div style='color:#101318'>to-be: " + escape(it["to_be"]) + "</div></div>")
        blocks += ("<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px;margin-top:10px'>"
                   "<div style='font-size:13px;font-weight:800;color:#101318'>" + escape(sc) + " "
                   "<span style='font-weight:400;color:#667085;font-size:11px'>" + escape((meta.get("region") or "") + " · " + (meta.get("country") or "")) + "</span></div>"
                   "<div style='font-family:monospace;color:#98A2B3;font-size:10.5px;word-break:break-all;margin:2px 0 4px'>" + escape(meta.get("url", "")) + "</div>"
                   + lis + "</div>")
    if not blocks:
        blocks = "<p style='color:#1F9E5C'>검수한 페이지에서 오류가 발견되지 않았습니다.</p>"
    return ("<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'>"
            "<div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'>"
            "<div style='font-size:12px;color:#667085;font-weight:700'>큐비 🐝 — Dotcom QA 리포트</div>"
            "<h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + "</h1>"
            "<div style='font-size:13px;color:#667085'>검수 " + str(s["pages"]) + "페이지 · 오류 " + str(s["fail"]) + "건 · 확인 " + str(s["warn"]) + "건</div>"
            "<div style='margin-top:14px'>" + blocks + "</div></div></div>")


if __name__ == "__main__":
    import json, re, sys
    sys.path.insert(0, ".")
    import schema_checker as sch
    import copy_checker as cop
    schema_rules = json.load(open("schema_rules.json", encoding="utf-8"))["products"]["M3"]
    copy_rules = json.load(open("copy_rules.json", encoding="utf-8"))["products"]["M3"]
    good = open("/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()
    bad = re.sub(r"\b(5000|4900)\s?mAh\b", "BATT", good, flags=re.I).replace('"@type": "3DModel"', '"@type": "Typo"')
    results = [
        {"sitecode": "uk", "url": "https://www.samsung.com/uk/smartphones/galaxy-s26-ultra/", "region": "EHQ", "country": "U.K", "product": "S26 Ultra",
         "schema": sch.check_page(good, schema_rules), "copy": cop.check_copy(good, copy_rules)},
        {"sitecode": "de", "url": "https://www.samsung.com/de/smartphones/galaxy-s26-ultra/", "region": "EHQ", "country": "Germany", "product": "S26 Ultra",
         "schema": sch.check_page(bad, schema_rules), "copy": cop.check_copy(bad, copy_rules)},
    ]
    print("요약:", summary_counts(results))
    open("/tmp/qa_report.xlsx", "wb").write(build_xlsx(results))
    open("/tmp/qa_email.html", "w", encoding="utf-8").write(build_email_draft(results))
    print("→ /tmp/qa_report.xlsx (시트: 스키마 QA / 카피 QA), /tmp/qa_email.html")

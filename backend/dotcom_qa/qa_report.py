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
from datetime import datetime
from typing import Any, Dict, List

from qa_messages import render

MARK = {"pass": "O", "warn": "△", "fail": "X", "-": "-"}
MARK_COLOR = {"pass": "1F9E5C", "warn": "E0A008", "fail": "D8362F", "-": "98A2B3"}
SEV_KO = {"fail": "오류", "warn": "확인", "pass": "정상"}
SEV_COLOR = {"fail": "D8362F", "warn": "E0A008", "pass": "1F9E5C"}
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


def _flatten(page_results):
    rows = []
    for pr in page_results:
        base = {"sitecode": pr.get("sitecode", ""), "url": pr.get("url", ""),
                "region": pr.get("region", ""), "country": pr.get("country", "")}
        for f in (pr.get("schema") or {}).get("findings", []):
            if f.get("status") == "pass":
                continue
            rows.append({**base, "area": "Schema", "item": f.get("block", ""),
                         "status": f.get("status"), "f": f})
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
SEV_COLOR2 = {"fail": "D8362F", "warn": "E0A008", "na": "98A2B3", "pass": "1F9E5C"}


def build_xlsx(page_results):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

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

    wb = Workbook()

    # ── Sheet 1 — QA Findings (한 행 = 오류/확인 하나, 국가별 정렬) ──
    ws = wb.active; ws.title = "QA Findings"
    ws.append(["#", "Country", "Region", "Site Code", "Product", "Page Type",
               "Severity", "Area", "Item", "Location", "As-Is (issue)", "To-Be (fix)", "URL"])
    _hdr(ws)
    # 모든 오류/확인을 한 행씩으로 펼치고 국가→사이트 순 정렬
    exploded = []
    for pr in page_results:
        meta = (pr.get("country", ""), pr.get("region", ""), pr.get("sitecode", ""),
                pr.get("product", ""), pr.get("page_type") or _page_type(pr.get("url", "")), pr.get("url", ""))
        for f in (pr.get("schema") or {}).get("findings", []):
            if f.get("status") in ("fail", "warn"):
                a, t = _en(f)
                exploded.append((meta, "Schema", f.get("block", ""), f.get("block", ""), f.get("status"), a, t))
        for f in (pr.get("copy") or {}).get("findings", []):
            if f.get("status") in ("fail", "warn"):
                a, t = _en(f)
                loc = "Disclaimer" if f.get("region") == "disclaimer" else "Body"
                if f.get("found"):
                    loc += f" (page: {', '.join(f['found'][:6])})"
                exploded.append((meta, "Spec", f.get("token", "") or f.get("category", ""), loc, f.get("status"), a, t))
    # 정렬: 국가 → 사이트 → 심각도(오류 먼저)
    sev_rank = {"fail": 0, "warn": 1}
    exploded.sort(key=lambda r: (r[0][0] or "zz", r[0][2] or "", sev_rank.get(r[4], 9)))
    for n, (meta, area, item, loc, sev, a, t) in enumerate(exploded, 1):
        country, region, site, product, ptype, url = meta
        ws.append([n, country, region, site, product, ptype, SEV_EN.get(sev, sev), area, str(item), loc, a, t, url])
        rn = ws.max_row
        sc = ws.cell(row=rn, column=7)  # Severity
        sc.font = Font(bold=True, color=SEV_COLOR2.get(sev, "000000"))
        sc.alignment = Alignment(horizontal="center", vertical="center")
    if not exploded:
        ws.append(["—", "", "", "", "", "", SEV_EN["pass"], "", "", "", "No issues found", "", ""])
    _finish(ws, [4, 13, 12, 9, 16, 9, 9, 8, 22, 18, 48, 48, 40], "A2")

    # ── Sheet 2 — Schema Matrix (페이지 1줄 = 타입별 O/△/X 요약) ──
    ws2 = wb.create_sheet("Schema Matrix")
    seen = set()
    for pr in page_results:
        for f in (pr.get("schema") or {}).get("findings", []):
            if f.get("block") == "JSON-LD":
                continue
            seen.add(_primary_type(f))
    type_cols = [t for t in _TYPE_ORDER if t in seen] + sorted(seen - set(_TYPE_ORDER))
    ctx = ["#", "Region", "Country", "Site Code", "Product", "Page Type", "Target URL"]
    ws2.append(ctx + type_cols + ["Errors", "Checks"])
    _hdr(ws2)
    for i, pr in enumerate(page_results, 1):
        ts, _a, _t = _schema_row(pr)
        sf = (pr.get("schema") or {}).get("findings", [])
        nfail = sum(1 for f in sf if f.get("status") == "fail")
        nwarn = sum(1 for f in sf if f.get("status") == "warn")
        row = [i, pr.get("region", ""), pr.get("country", ""), pr.get("sitecode", ""),
               pr.get("product", ""), pr.get("page_type") or _page_type(pr.get("url", "")), pr.get("url", "")]
        row += [MARK.get(ts.get(t, "-"), "-") for t in type_cols] + [nfail, nwarn]
        ws2.append(row); rn = ws2.max_row
        for k, t in enumerate(type_cols):
            cell = ws2.cell(row=rn, column=len(ctx) + 1 + k)
            cell.font = Font(bold=True, color=MARK_COLOR.get(ts.get(t, "-"), "98A2B3"))
            cell.alignment = Alignment(horizontal="center", vertical="center")
    _finish(ws2, [4, 13, 12, 9, 16, 9, 44] + [9] * len(type_cols) + [8, 8], "H2")

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def build_email_draft(page_results, when=""):
    from html import escape
    s = summary_counts(page_results)
    rows = _flatten(page_results)
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
            "<div style='font-size:12px;color:#667085;font-weight:700'>큐비 🐝 — Dotcom QA 리포트</div>"
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

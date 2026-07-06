"""
qa_report.py — 큐비(QB) — Dotcom QA 체커 [Phase G]

큐비 🐝 — QA의 사촌 QB. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

여러 페이지의 검수 결과(스키마 + 카피)를 모아
  (1) 오류 Excel 리포트(as-is/to-be)
  (2) 메일 초안(HTML) — 사이트별 오류 요약
를 만든다.

입력 형태(page_results):
  [
    {"sitecode","url","region","country",
     "schema": <schema_checker.check_page 결과>,   # {"summary":..,"findings":[..]}
     "copy":   <copy_checker.check_copy 결과>},     # {"summary":..,"findings":[..]}
    ...
  ]
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import Any, Dict, List

SEV_KO = {"fail": "오류", "warn": "확인", "pass": "정상"}
SEV_COLOR = {"fail": "D8362F", "warn": "E0A008", "pass": "1F9E5C"}


def _flatten(page_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """검수 결과를 '오류/확인' 행 리스트로 평탄화(정상은 제외)."""
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
            rows.append({**base, "area": "카피(" + f.get("kind", "") + ")", "item": f.get("token", ""),
                         "status": f.get("status"), "as_is": f.get("as_is", ""), "to_be": f.get("to_be", "")})
    return rows


def summary_counts(page_results: List[Dict[str, Any]]) -> Dict[str, int]:
    rows = _flatten(page_results)
    return {"pages": len(page_results),
            "fail": sum(1 for r in rows if r["status"] == "fail"),
            "warn": sum(1 for r in rows if r["status"] == "warn"),
            "issues": len(rows)}


def build_xlsx(page_results: List[Dict[str, Any]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = "QA 오류 리포트"
    headers = ["사이트코드", "지역", "국가", "영역", "항목", "심각도", "as-is (현재)", "to-be (조치)", "URL"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1B2A4A")
        c.alignment = Alignment(vertical="center")
    for r in _flatten(page_results):
        ws.append([r["sitecode"], r["region"], r["country"], r["area"], r["item"],
                   SEV_KO.get(r["status"], r["status"]), r["as_is"], r["to_be"], r["url"]])
        cell = ws.cell(row=ws.max_row, column=6)
        cell.font = Font(bold=True, color=SEV_COLOR.get(r["status"], "000000"))
    widths = [12, 10, 12, 12, 22, 8, 40, 46, 44]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def build_email_draft(page_results: List[Dict[str, Any]], when: str = "") -> str:
    """사이트별 오류 요약 메일 초안(HTML, 인라인 스타일)."""
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
            lis += (
                "<div style='font-size:12.5px;line-height:1.5;margin-top:6px'>"
                "<span style='font-size:10.5px;font-weight:700;color:#fff;background:" + col + ";padding:2px 6px;border-radius:5px'>"
                + SEV_KO.get(it["status"], "") + "</span> "
                "<b style='color:#101318'>" + escape(it["area"]) + " · " + escape(str(it["item"])[:40]) + "</b>"
                "<div style='color:#475467;margin-top:2px'>as-is: " + escape(it["as_is"]) + "</div>"
                "<div style='color:#101318'>to-be: " + escape(it["to_be"]) + "</div>"
                "</div>"
            )
        blocks += (
            "<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px;margin-top:10px'>"
            "<div style='font-size:13px;font-weight:800;color:#101318'>" + escape(sc) + " "
            "<span style='font-weight:400;color:#667085;font-size:11px'>" + escape((meta.get("region") or "") + " · " + (meta.get("country") or "")) + "</span></div>"
            "<div style='font-family:monospace;color:#98A2B3;font-size:10.5px;word-break:break-all;margin:2px 0 4px'>" + escape(meta.get("url", "")) + "</div>"
            + lis + "</div>"
        )
    if not blocks:
        blocks = "<p style='color:#1F9E5C'>검수한 페이지에서 오류가 발견되지 않았습니다.</p>"

    return (
        "<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'>"
        "<div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'>"
        "<div style='font-size:12px;color:#667085;font-weight:700'>큐비 🐝 — Dotcom QA 리포트</div>"
        "<h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + "</h1>"
        "<div style='font-size:13px;color:#667085'>검수 " + str(s["pages"]) + "페이지 · 오류 " + str(s["fail"]) + "건 · 확인 " + str(s["warn"]) + "건</div>"
        "<div style='margin-top:14px'>" + blocks + "</div>"
        "</div></div>"
    )


if __name__ == "__main__":
    # 스키마 + 카피 체커로 index.html(정상) + 훼손본을 검수해 리포트 생성 데모
    import json, re, sys
    sys.path.insert(0, ".")
    import schema_checker as sch
    import copy_checker as cop

    schema_rules = json.load(open("schema_rules.json", encoding="utf-8"))["products"]["M3"]
    copy_rules = json.load(open("copy_rules.json", encoding="utf-8"))["products"]["M3"]
    good = open("/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()
    bad = re.sub(r"\b(5000|4900)\s?mAh\b", "BATTERY", good, flags=re.I).replace('"@type": "3DModel"', '"@type": "Typo"')

    results = [
        {"sitecode": "uk", "url": "https://www.samsung.com/uk/smartphones/galaxy-s26-ultra/",
         "region": "EHQ", "country": "U.K",
         "schema": sch.check_page(good, schema_rules), "copy": cop.check_copy(good, copy_rules)},
        {"sitecode": "de", "url": "https://www.samsung.com/de/smartphones/galaxy-s26-ultra/",
         "region": "EHQ", "country": "Germany",
         "schema": sch.check_page(bad, schema_rules), "copy": cop.check_copy(bad, copy_rules)},
    ]
    print("요약:", summary_counts(results))
    open("/tmp/qa_report.xlsx", "wb").write(build_xlsx(results))
    open("/tmp/qa_email.html", "w", encoding="utf-8").write(build_email_draft(results))
    print("→ /tmp/qa_report.xlsx, /tmp/qa_email.html 생성")

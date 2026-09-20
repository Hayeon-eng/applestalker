"""
qa_report.py — 큐비 — Dotcom QA 체커 [Phase G] — 진입점(공개 API)

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

Excel 리포트(시트 2개) — QA 관례에 맞춰 전체 영어로 출력.
  · Schema QA : URL 1줄 = 타입별 O/△/X + Findings(as-is) + TO-BE guide
  · Copy QA   : URL 1줄 = spec/noun/value 결과 + 누락·불일치 + TO-BE guide
메일 초안(HTML)은 화면 흐름과 동일하게 한국어 유지.
문구는 qa_messages.render(code, 'en'/'ko', finding) 으로 렌더.

[2026-07 파일 분할] 파일 크기 제한(46KB) 때문에 4개로 쪼갰다. 이 파일은 얇은 진입점으로,
아래 3개 모듈에서 필요한 걸 모아 지금까지와 동일한 공개 API를 그대로 제공한다 — 외부
호출부(qb_routes_*.py 등)는 지금처럼 `import qa_report; qa_report.build_xlsx(...)` /
`qa_report.summary_counts(...)` / `qa_report.build_email_draft(...)` 그대로 쓰면 된다.
  · qa_report_helpers.py — 텍스트/타입 판정 헬퍼 + JSON-LD 코드 조각 생성기
  · qa_report_rows.py    — schema/html_qa 결과 → Excel 행(row) 변환
  · qa_report_xlsx.py    — build_xlsx() 본체(시트 2개 작성)
"""
from __future__ import annotations
import re
import json
import difflib
from datetime import datetime

from qa_report_helpers import _flatten, summary_counts, SEV_KO, SEV_COLOR  # re-export: qa_report.summary_counts
from qa_report_xlsx import build_xlsx  # re-export: qa_report.build_xlsx

def _word_diff_html(a_str, b_str):
    """xlsx의 '달라진 부분만 빨간색' 규칙을 메일(HTML)에도 동일하게 적용.
    단어 단위 diff — 바뀐 단어만 빨간 볼드, 나머지는 그대로."""
    from html import escape
    a_tok = re.split(r"(\s+)", a_str or ""); b_tok = re.split(r"(\s+)", b_str or "")
    sm = difflib.SequenceMatcher(a=a_tok, b=b_tok, autojunk=False)
    a_changed = [False] * len(a_tok); b_changed = [False] * len(b_tok)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            for i in range(i1, i2):
                a_changed[i] = True
            for j in range(j1, j2):
                b_changed[j] = True

    def _render(tokens, flags):
        out = []
        for tok, ch in zip(tokens, flags):
            e = escape(tok)
            out.append("<span style='color:#D8362F;font-weight:700'>" + e + "</span>" if ch else e)
        return "".join(out) or "(없음)"

    return _render(a_tok, a_changed), _render(b_tok, b_changed)


def _section_block_schema_copy(page_results, tab):
    """기존 Data QA/Spec QA 메일 렌더링 — 섹션별로 재사용할 수 있게 함수로 분리(내용은 그대로)."""
    from html import escape
    rows = _flatten(page_results, tab=tab)
    fail = sum(1 for r in rows if r["status"] == "fail")
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
            a_html, t_html = _word_diff_html(a, t)
            lis += ("<div style='font-size:12.5px;line-height:1.5;margin-top:6px'>"
                    "<span style='font-size:10.5px;font-weight:700;color:#fff;background:" + col + ";padding:2px 6px;border-radius:5px'>"
                    + SEV_KO.get(it["status"], "") + "</span> "
                    "<b style='color:#101318'>" + escape(it["area"]) + " · " + escape(str(it["item"])[:40]) + "</b>"
                    "<div style='color:#475467;margin-top:2px'>as-is: " + a_html + "</div>"
                    "<div style='color:#101318'>to-be: " + t_html + "</div></div>")
        blocks += ("<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px;margin-top:10px'>"
                   "<div style='font-size:13px;font-weight:800;color:#101318'>" + escape(sc) + " "
                   "<span style='font-weight:400;color:#667085;font-size:11px'>" + escape((meta.get("region") or "") + " · " + (meta.get("country") or "")) + "</span></div>"
                   "<div style='font-family:monospace;color:#98A2B3;font-size:10.5px;word-break:break-all;margin:2px 0 4px'>" + escape(meta.get("url", "")) + "</div>"
                   + lis + "</div>")
    return blocks, fail


def _section_block_static(static_run):
    """공통페이지 QA 메일 섹션 — static_guide.cell_guide() 의 as-is/to-be 를 그대로 재사용해서
    Data QA/Spec QA 섹션과 같은 톤(사이트 카드 + 색상 배지 + as-is/to-be)으로 렌더한다."""
    import static_guide
    from html import escape
    results = (static_run or {}).get("results", [])
    bad = [r for r in results if r.get("status") != "정상"]
    by_site = {}
    for r in bad:
        by_site.setdefault(r["sitecode"], []).append(r)
    blocks = ""
    for sc, items in by_site.items():
        lis = ""
        for r in items[:20]:
            g = static_guide.cell_guide(r)
            col = "#98A2B3" if r["status"] in ("페이지 없음", "접근 실패") else "#D8362F"
            lis += ("<div style='font-size:12.5px;line-height:1.5;margin-top:6px'>"
                    "<span style='font-size:10.5px;font-weight:700;color:#fff;background:" + col + ";padding:2px 6px;border-radius:5px'>"
                    + escape(r["status"]) + "</span> "
                    "<b style='color:#101318'>" + escape(r.get("page_label") or "") + "</b>"
                    "<div style='color:#475467;margin-top:2px'>지금 상태: " + escape(g["as_is"]) + "</div>"
                    "<div style='color:#101318'>조치: " + escape(g["to_be"]) + "</div></div>")
        country = next((r.get("country") for r in items if r.get("country")), "")
        blocks += ("<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px;margin-top:10px'>"
                   "<div style='font-size:13px;font-weight:800;color:#101318'>" + escape(sc) + " "
                   "<span style='font-weight:400;color:#667085;font-size:11px'>" + escape(country) + "</span></div>"
                   + lis + "</div>")
    return blocks, len(bad)


def build_email_draft(page_results, when="", sections=None, static_run=None):
    """[2026-09 FIX] 예전엔 tab(현재 보고 있는 탭) 하나만 복사됐고 static(공통페이지 QA)은
    아예 처리가 안 돼 있었다 — sections 리스트로 Data QA/Spec QA/공통페이지 QA 중 원하는
    조합을 모두 골라 한 메일에 합칠 수 있게 한다. sections 생략 시 기존 호출부 호환을 위해
    page_results 가 있으면 schema 하나만(예전 tab=None 기본값과 동일한 결과)."""
    from html import escape
    labels = {"schema": "Data QA", "copy": "Spec QA", "static": "공통페이지 QA"}
    sections = list(sections) if sections else (["schema"] if page_results else [])
    section_htmls = []
    section_labels = []
    total_fail = 0
    for tab in sections:
        if tab in ("schema", "copy"):
            blocks, fail = _section_block_schema_copy(page_results, tab)
        elif tab == "static":
            blocks, fail = _section_block_static(static_run)
        else:
            continue
        total_fail += fail
        if not blocks:
            blocks = "<p style='color:#1F9E5C;font-size:12.5px;margin:6px 0 0'>이 영역에서 오류가 발견되지 않았습니다.</p>"
        section_labels.append(labels[tab])
        section_htmls.append(
            "<div style='margin-top:18px'>"
            "<div style='font-size:13px;font-weight:800;color:#101318;border-bottom:2px solid #1B2A4A;padding-bottom:4px'>" + escape(labels[tab]) + "</div>"
            + blocks + "</div>")
    qa_label = " + ".join(section_labels) if section_labels else "QA"
    body = "".join(section_htmls) or "<p>선택한 항목이 없습니다.</p>"
    return ("<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'>"
            "<div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'>"
            "<div style='font-size:12px;color:#667085;font-weight:700'>큐비 🐝 — " + escape(qa_label) + " 리포트</div>"
            "<h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + "</h1>"
            "<div style='font-size:13px;color:#667085'>선택 영역 오류 " + str(total_fail) + "건</div>"
            "<div style='margin-top:14px'>" + body + "</div></div></div>")


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

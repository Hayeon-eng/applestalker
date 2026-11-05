"""
qa_summary_render.py — 큐비 요약판 렌더(엑셀 시트 · 메일 HTML · PPT) [2026-11 신규]
데이터는 qa_exec_summary.build() 하나. 여기서는 모양만 입힌다.
"""
from __future__ import annotations
from html import escape
from typing import Any, Dict, List

TIER_HEX = {"good": "1F9E5C", "mid": "E0A008", "bad": "D8362F", "none": "98A2B3", "": "1D2433"}


# ── 엑셀: 첫 시트 '요약판' ─────────────────────────────────────────────
def write_summary_sheet(wb, S: Dict[str, Any], sheet_title: str = "요약판"):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    ws = wb.create_sheet(sheet_title, 0)
    thin = Side(style="thin", color="E4E7EC"); border = Border(bottom=thin)
    H = Font(bold=True, color="FFFFFF", name="Arial", size=10); HF = PatternFill("solid", fgColor="1B2A4A")
    big = Font(bold=True, size=16, name="Arial", color="101318"); sub = Font(size=10, name="Arial", color="667085")

    ws.append([f"qaBee 🐝 — 요약판  ·  {S.get('product') or ''}  ·  {S.get('run_at') or ''}"]); ws["A1"].font = big
    ws.append([S.get("headline", "")]); ws["A2"].font = Font(bold=True, size=12, name="Arial", color="1B2A4A")
    ws.append([S.get("conclusion", "")]); ws["A3"].font = Font(size=11, name="Arial"); ws["A3"].alignment = Alignment(wrap_text=True)
    ws.merge_cells("A3:H3"); ws.row_dimensions[3].height = 32
    ws.append([])
    # KPI 띠(가로)
    r0 = ws.max_row + 1
    for i, k in enumerate(S.get("kpis", []), 1):
        c = ws.cell(r0, i, k["label"]); c.font = sub
        v = ws.cell(r0 + 1, i, k["value"]); v.font = Font(bold=True, size=18, name="Arial", color=TIER_HEX.get(k.get("tier") or "", "1D2433"))
        s = ws.cell(r0 + 2, i, k.get("sub", "")); s.font = sub
        for rr in (r0, r0 + 1, r0 + 2):
            ws.cell(rr, i).fill = PatternFill("solid", fgColor="F7F8FA"); ws.cell(rr, i).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[r0 + 1].height = 28
    ws.append([])
    # 지금 할 일
    ws.append(["지금 할 일 Top 5"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    for i, a in enumerate(S.get("actions", []), 1):
        ws.append([f"{i}. {a}"]); ws.cell(ws.max_row, 1).alignment = Alignment(wrap_text=True); ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=8)
    ws.append([])
    # 사이트별
    ws.append(["사이트별 상태"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    hdr = ["사이트", "국가", "권역", "페이지", "상태", "오류", "확인", "데이터 유무 %", "AEO 퀄리티 %", "스펙 일치율 %", "URL"]
    ws.append(hdr)
    for c in ws[ws.max_row]:
        c.font, c.fill = H, HF
    for s in S.get("sites", []):
        ws.append([s["site"], s["country"], s["region"], s["page_type"], s["state"], s["fail"], s["warn"], s["data_pct"], s["quality_pct"], s["spec_pct"], s["url"]])
        st = ws.cell(ws.max_row, 5); st.font = Font(bold=True, name="Arial", color="D8362F" if "오류" in s["state"] else "E0A008" if "확인" in s["state"] else "1F9E5C")
        for c in ws[ws.max_row]:
            c.border = border
    ws.append([])
    # 가장 많이 나온 이슈
    ws.append(["가장 많은 사이트에 나타난 이슈"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    ws.append(["항목", "등급", "사이트 수", "예시"])
    for c in ws[ws.max_row]:
        c.font, c.fill = H, HF
    for t in S.get("top_issues", []):
        ws.append([t["item"], t["kind"], t["sites"], t["sample"]])
    if S.get("url_check"):
        ws.append([]); ws.append(["URL 점검 필요 (에러 페이지로 응답 — 레지스트리 URL 갱신)"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial", color="8A6D00")
        ws.append(["사이트", "URL", "사유"])
        for c in ws[ws.max_row]:
            c.font, c.fill = H, HF
        for u in S["url_check"]:
            ws.append([u["site"], u["url"], u["reason"]])
    if S.get("static"):
        st = S["static"]; bs = st.get("by_status") or {}
        ws.append([]); ws.append([f"공통페이지 QA ({st.get('at', '')}) — 사이트 {st.get('sites')} × 페이지 {st.get('pages')}"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
        ws.append(list(bs.keys())); ws.append(list(bs.values()))
    ws.append([]); ws.append([S.get("basis", "")]); ws.cell(ws.max_row, 1).font = Font(size=9, name="Arial", color="98A2B3", italic=True)
    for col, w in zip("ABCDEFGHIJK", (16, 14, 10, 10, 10, 8, 8, 14, 14, 14, 60)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"
    return ws


# ── 메일: 맨 위 블록 ───────────────────────────────────────────────────
def email_block_html(S: Dict[str, Any]) -> str:
    cells = ""
    for k in S.get("kpis", []):
        col = "#" + TIER_HEX.get(k.get("tier") or "", "1D2433")
        cells += ("<td valign='top' style='padding:3px'><div style='border:1px solid #EEF0F3;border-radius:8px;padding:8px 6px;text-align:center;background:#F7F8FA'>"
                  f"<div style='font-size:10px;color:#667085'>{escape(str(k['label']))}</div>"
                  f"<div style='font-size:18px;font-weight:800;color:{col};line-height:1.2'>{escape(str(k['value']))}</div>"
                  f"<div style='font-size:9.5px;color:#98A2B3'>{escape(str(k.get('sub', '')))}</div></div></td>")
    acts = "".join(f"<div style='font-size:12px;color:#101318;margin-top:3px'>{i}. {escape(a)}</div>" for i, a in enumerate(S.get("actions", []), 1))
    rows = ""
    for s in S.get("sites", [])[:12]:
        col = "#D8362F" if "오류" in s["state"] else "#E0A008" if "확인" in s["state"] else "#1F9E5C"
        rows += (f"<tr><td style='padding:3px 6px;font-size:11.5px'><b>{escape(s['site'])}</b> <span style='color:#98A2B3'>{escape(s['country'])}</span></td>"
                 f"<td style='padding:3px 6px;font-size:11.5px;color:{col};font-weight:700'>{escape(s['state'])}</td>"
                 f"<td style='padding:3px 6px;font-size:11.5px;text-align:right'>{s['fail']} / {s['warn']}</td>"
                 f"<td style='padding:3px 6px;font-size:11.5px;text-align:right'>{s['data_pct'] if s['data_pct'] is not None else '-'}% · {s['quality_pct'] if s['quality_pct'] is not None else '-'}% · {s['spec_pct'] if s['spec_pct'] is not None else '-'}%</td></tr>")
    more = f"<div style='font-size:10.5px;color:#98A2B3;margin-top:4px'>외 {len(S.get('sites', [])) - 12}개 사이트 — 아래 상세 참조</div>" if len(S.get("sites", [])) > 12 else ""
    return ("<div style='border:2px solid #1B2A4A;border-radius:12px;padding:14px;margin-bottom:16px;background:#fff'>"
            "<div style='font-size:11px;font-weight:800;color:#1B2A4A;letter-spacing:.04em'>요약판</div>"
            f"<div style='font-size:15px;font-weight:800;color:#101318;margin-top:4px'>{escape(S.get('headline', ''))}</div>"
            f"<div style='font-size:12.5px;color:#475467;margin-top:4px'>{escape(S.get('conclusion', ''))}</div>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:10px'><tr>{cells}</tr></table>"
            "<div style='font-size:12px;font-weight:800;color:#101318;margin-top:12px'>지금 할 일 Top 5</div>" + acts +
            "<div style='font-size:12px;font-weight:800;color:#101318;margin-top:12px'>사이트별 상태 <span style='font-weight:400;color:#98A2B3'>(오류/확인 · 데이터 유무 · 퀄리티 · 스펙)</span></div>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:4px'>{rows}</table>{more}"
            f"<div style='font-size:10px;color:#98A2B3;margin-top:10px'>{escape(S.get('basis', ''))}</div></div>")


# ── PPT ────────────────────────────────────────────────────────────────
def _grade(st):
    return ("오류", "bad") if st == "fail" else ("확인", "mid") if st == "warn" else ("정상", "good")


def structured_actions(S: Dict[str, Any]) -> List[Dict[str, Any]]:
    """할 일을 카드용 {title, detail, tag, tier} 로 — 문장 한 덩어리 대신 제목/한 줄/담당."""
    out: List[Dict[str, Any]] = []
    for t in S.get("top_issues", []):
        if t["kind"] == "오류":
            area = t["item"].split("]")[0].strip("[") if t["item"].startswith("[") else "검수"
            out.append({"title": f"{t['item'].split('] ', 1)[-1]} 수정", "detail": f"{t['sites']}개 사이트 · {t['sample']}" if t["sample"] else f"{t['sites']}개 사이트",
                        "tag": {"스키마": "개발", "SEO": "개발", "카피": "마케팅", "스펙": "상품기획"}.get(area, "검수"), "tier": "bad"})
    if S.get("url_check"):
        u = S["url_check"]
        out.append({"title": f"레지스트리 URL {len(u)}건 갱신", "detail": "에러 페이지로 응답: " + ", ".join(x["site"].split()[0] for x in u[:8]) + ("…" if len(u) > 8 else ""),
                    "tag": "운영", "tier": "mid"})
    for t in S.get("top_issues", []):
        if t["kind"] == "확인":
            area = t["item"].split("]")[0].strip("[") if t["item"].startswith("[") else "검수"
            out.append({"title": f"{t['item'].split('] ', 1)[-1]} 확인", "detail": f"{t['sites']}개 사이트 · {t['sample']}" if t["sample"] else f"{t['sites']}개 사이트",
                        "tag": {"스키마": "개발", "SEO": "개발", "카피": "마케팅", "스펙": "상품기획"}.get(area, "검수"), "tier": "mid"})
    st = S.get("static")
    if st and (st.get("by_status") or {}).get("파싱 실패"):
        out.append({"title": f"공통페이지 JSON-LD 파싱 실패 {st['by_status']['파싱 실패']}건 수정", "detail": "검색엔진이 블록을 읽지 못함 — 상세 시트의 수정 코드 참조", "tag": "개발", "tier": "bad"})
    return out


def build_pptx(S: Dict[str, Any], page_results: List[Dict[str, Any]], static_run=None) -> bytes:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import pptx_common as P
    from pptx.dml.color import RGBColor
    ACC = RGBColor(0x1B, 0x2A, 0x4A)
    prs = P.new_deck()
    P.cover(prs, "qaBee 🐝 검수 리포트", f"{S.get('product') or ''} — Data QA · Spec QA · 공통페이지 QA", S.get("run_at") or "",
            ACC, "요약판 1장 + 상세. 숫자는 화면·엑셀·메일과 같은 데이터(qa_exec_summary)에서 나옵니다.")
    kp = {k["label"]: k for k in S.get("kpis", [])}
    fail_total = sum(s_["fail"] for s_ in S.get("sites", [])); warn_total = sum(s_["warn"] for s_ in S.get("sites", []))
    verdict = ({"label": "수정 필요", "tier": "bad"} if fail_total else {"label": "확인 필요", "tier": "mid"} if warn_total else {"label": "정상", "tier": "good"})
    kpis4 = [kp.get("오류 / 확인"), kp.get("데이터 유무"), kp.get("AEO 퀄리티"), kp.get("스펙 일치율")]
    kpis4 = [k for k in kpis4 if k]
    checked = kp.get("검수 페이지", {})
    subtitle = f"{S.get('product') or ''} · {S.get('run_at') or ''} · 검수 {checked.get('value', '-')}페이지" + (f" ({checked.get('sub')})" if checked.get("sub") and "전부" not in str(checked.get("sub")) else "")
    rank_rows = [{"name": f"{s_['site']} {s_['country']}".strip(), "status": s_["state"].split(" ", 1)[-1], "tier": "bad" if s_["fail"] else ("mid" if s_["warn"] else "good"),
                  "value": f"오류{s_['fail']} 확인{s_['warn']}", "bar": s_["quality_pct"]} for s_ in S.get("sites", [])[:8]]
    P.summary_slide(prs, ACC, "요약판", subtitle, S.get("headline", ""), verdict, kpis4, structured_actions(S),
                    {"title": "어디가 문제인가 (오류 많은 순 · 막대=AEO 퀄리티)", "rows": rank_rows}, basis=S.get("basis", ""), conclusion=S.get("conclusion", ""))
    # 상세 1 — 이슈 Top
    P.issue_slide(prs, ACC, "가장 많은 사이트에 나타난 이슈", "같은 원인(템플릿·룰)일 가능성이 높은 순 — 하나 고치면 여러 사이트가 함께 해결",
                  [{"head": "이슈 Top", "sub": f"{len(S.get('top_issues', []))}건", "rows": [{"item": t["item"], "grade": t["kind"], "tier": "bad" if t["kind"] == "오류" else "mid",
                    "what": f"{t['sites']}개 사이트에서 발견", "how": t["sample"]} for t in S.get("top_issues", [])]}], col_titles=("항목", "범위", "예시"))
    # 상세 2 — Data QA 사이트별
    groups = []
    for p in sorted(page_results, key=lambda x: (x.get("sitecode") or "")):
        if p.get("not_checked"):
            continue
        rows = []
        for f in (p.get("schema") or {}).get("findings", []):
            if f.get("status") in ("fail", "warn"):
                g, t = _grade(f["status"]); rows.append({"item": f"스키마 · {f.get('block', '')}", "grade": g, "tier": t, "what": f.get("as_is", ""), "how": f.get("to_be", "")})
        for it in (p.get("seo") or {}).get("items", []) or []:
            if it.get("status") in ("fail", "warn"):
                g, t = _grade(it["status"]); rows.append({"item": f"SEO · {it.get('element', '')}", "grade": g, "tier": t, "what": f"{it.get('issue', '')} — {it.get('value', '')}", "how": it.get("detail", "")})
        for f in (p.get("copy") or {}).get("findings", []) or []:
            if f.get("status") in ("fail", "warn"):
                g, t = _grade(f["status"]); rows.append({"item": f"카피 · {f.get('token', '') or f.get('kind', '')}", "grade": g, "tier": t, "what": f.get("as_is", ""), "how": f.get("to_be", "")})
        if rows:
            groups.append({"head": f"{p.get('sitecode', '')} · {p.get('country', '')} · {p.get('page_type', '')}", "sub": f"오류 {sum(1 for r in rows if r['grade'] == '오류')} · 확인 {sum(1 for r in rows if r['grade'] == '확인')}", "rows": rows})
    P.issue_slide(prs, ACC, "Data QA — 사이트별 상세", "스키마(JSON-LD) · SEO 요소 · 카피 — 오류/확인만", groups)
    # 상세 3 — Spec QA 사이트별
    groups = []
    for p in sorted(page_results, key=lambda x: (x.get("sitecode") or "")):
        rows = []
        for it in (p.get("spec_v2") or {}).get("items", []) or []:
            if it.get("status") in ("fail", "warn"):
                g, t = _grade(it["status"])
                rows.append({"item": it.get("attribute", ""), "grade": g, "tier": t,
                             "what": f"페이지: {it.get('found') or '(없음)'}  ← 기준 {it.get('expected', '')} {it.get('unit', '')}".strip(), "how": it.get("message", "")})
        if rows:
            groups.append({"head": f"{p.get('sitecode', '')} · {p.get('country', '')}", "sub": f"오류 {sum(1 for r in rows if r['grade'] == '오류')} · 확인 {sum(1 for r in rows if r['grade'] == '확인')}", "rows": rows})
    P.issue_slide(prs, ACC, "Spec QA — 사이트별 상세", "페이지 실제값 ← 기준값 · '확인'은 사유를 보고 수정 여부 결정", groups, col_titles=("항목", "페이지 ← 기준", "판정 사유"))
    # 상세 4 — URL 점검
    if S.get("url_check"):
        P.issue_slide(prs, ACC, "URL 점검 필요", "등록된 URL 이 에러 페이지로 응답 — 검수에서 제외했고 레지스트리 URL 갱신이 필요", [{
            "head": "에러 페이지로 응답한 URL", "sub": f"{len(S['url_check'])}건", "rows": [{"item": u["site"], "grade": "점검", "tier": "mid", "what": u["url"], "how": u["reason"]} for u in S["url_check"]]}],
            col_titles=("사이트", "URL", "사유"))
    # 상세 5 — 공통페이지
    if static_run:
        bs = (static_run.get("summary") or {}).get("by_status") or {}
        by_site: Dict[str, List[Dict[str, Any]]] = {}
        for r in static_run.get("results", []):
            if r.get("status") != "정상":
                tier = "bad" if r.get("status") == "파싱 실패" else "mid" if r.get("status") in ("오적용", "미해결 참조", "기타") else "none"
                by_site.setdefault(r.get("sitecode", ""), []).append({"item": r.get("page", ""), "grade": r.get("status", ""), "tier": tier, "what": " / ".join(r.get("reasons", [])), "how": ""})
        P.issue_slide(prs, ACC, "공통페이지 QA — 정상 외 페이지", " · ".join(f"{k} {v}" for k, v in bs.items()),
                      [{"head": sc, "sub": f"{len(rows)}페이지", "rows": rows} for sc, rows in sorted(by_site.items())], col_titles=("페이지", "사유", ""))
    return P.save(prs)

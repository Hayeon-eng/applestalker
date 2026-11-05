"""
hc_exec_summary.py — honeyComb · 요약판 데이터 + 렌더(엑셀 첫 시트 · 메일 블록 · PPT) [2026-11 신규]

화면 '이번 주 요약'·1위 비율·속성 노출률과 같은 숫자를 하나로 만들어 세 내보내기가 같이 쓴다.
build(run, prev_run, config, attributes, insights) → {week, at, headline, conclusion, kpis, countries, products, actions, apple, basis, changes}
"""
from __future__ import annotations
from html import escape
from typing import Any, Dict, List, Optional

import hc_engine

STATUS_KO = {"top1": "1위", "topn": "상단(1위 아님)", "low": "하위", "absent": "미노출", "unranked": "순위 미기록", "unchecked": "미조회", "error": "조회 실패"}
TIER_HEX = {"good": "1F9E5C", "mid": "E0A008", "bad": "D8362F", "none": "98A2B3", "": "1D2433"}


def _tier(v, good=70, mid=40):
    if v is None:
        return "none"
    return "good" if v >= good else "mid" if v >= mid else "bad"


def _rate(by: Dict[str, int], keys=("top1",)) -> Optional[float]:
    chk = sum(by.get(x, 0) for x in ("top1", "topn", "low", "absent"))
    return round(100 * sum(by.get(k, 0) for k in keys) / chk, 1) if chk else None


def build(run: Dict[str, Any], prev_run: Optional[Dict[str, Any]], config: Dict[str, Any], attributes: List[Dict[str, Any]],
          insights: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    s = hc_engine.summarize(run, keyword_type="brand")
    ps = hc_engine.summarize(prev_run, keyword_type="brand") if prev_run else None
    cname = {c["code"]: c["label"] for c in config.get("countries", [])}
    plabel = {p["slug"]: p["label"] for p in config.get("products", [])}
    apple = (insights or {}).get("apple") if insights else None
    apple_top1 = (apple or {}).get("overall", {}).get("apple_top1") if apple else None

    def delta(cur, prev):
        return None if (cur is None or prev is None) else round(cur - prev, 1)

    countries = []
    for code, by in s.get("per_country", {}).items():
        chk = sum(by.get(x, 0) for x in ("top1", "topn", "low", "absent"))
        r1 = _rate(by)
        countries.append({"code": code, "label": cname.get(code, code), "checked": chk, "top1": by.get("top1", 0), "topn": by.get("topn", 0),
                          "absent": by.get("absent", 0), "top1_rate": r1,
                          "apple_top1": next((x.get("apple_top1") for x in (apple or {}).get("by_country", []) if x.get("country") == code), None) if apple else None,
                          "state": "🔴 미노출 多" if (chk and by.get("absent", 0) >= chk / 2) else ("🟢 양호" if (r1 or 0) >= 70 else ("🟡 보통" if (r1 or 0) >= 40 else "🔴 낮음"))})
    countries.sort(key=lambda c: ((c["top1_rate"] if c["top1_rate"] is not None else -1), -c["absent"]))
    products = []
    for slug, by in s.get("per_product", {}).items():
        chk = sum(by.get(x, 0) for x in ("top1", "topn", "low", "absent"))
        products.append({"slug": slug, "label": plabel.get(slug, slug), "checked": chk, "top1": by.get("top1", 0), "absent": by.get("absent", 0), "top1_rate": _rate(by)})
    changes = hc_engine.diff_runs(prev_run, run) if prev_run else []
    downs = [c for c in changes if c["changes"].get("status") and ["top1", "topn", "low", "absent"].index(c["changes"]["status"][1]) >
             ["top1", "topn", "low", "absent"].index(c["changes"]["status"][0]) if c["changes"]["status"][0] in ("top1", "topn", "low", "absent") and c["changes"]["status"][1] in ("top1", "topn", "low", "absent")]
    ups = [c for c in changes if c["changes"].get("status")] 
    ups = [c for c in ups if c not in downs]

    kpis = [
        {"label": "1위 비율", "value": f"{s['top1_rate'] if s['top1_rate'] is not None else '-'}%",
         "sub": (f"전주 {('+' if (delta(s['top1_rate'], ps['top1_rate']) or 0) >= 0 else '')}{delta(s['top1_rate'], ps['top1_rate'])}p" if ps and delta(s['top1_rate'], ps['top1_rate']) is not None else f"조회 {sum(s['by_status'].get(x, 0) for x in ('top1','topn','low','absent'))}칸"),
         "tier": _tier(s["top1_rate"])},
        {"label": "상단 노출(8위 내)", "value": f"{s['topn_rate'] if s['topn_rate'] is not None else '-'}%", "sub": f"1위 {s['by_status'].get('top1', 0)} · 상단 {s['by_status'].get('topn', 0)}", "tier": _tier(s["topn_rate"])},
        {"label": "미노출 칸", "value": f"{s['by_status'].get('absent', 0)}", "sub": f"미조회 {s['by_status'].get('unchecked', 0)} · 실패 {s['by_status'].get('error', 0)}", "tier": "bad" if s["by_status"].get("absent", 0) else "good"},
        {"label": "속성 노출률", "value": f"{s['attr_entered_rate'] if s['attr_entered_rate'] is not None else '-'}%", "sub": "확인 안 함 제외", "tier": _tier(s["attr_entered_rate"])},
        {"label": "Apple 1위 비율", "value": f"{apple_top1 if apple_top1 is not None else '-'}%",
         "sub": (f"삼성 대비 {('+' if (s['top1_rate'] or 0) - apple_top1 >= 0 else '')}{round((s['top1_rate'] or 0) - apple_top1, 1)}p" if (apple_top1 is not None and s['top1_rate'] is not None) else "비교 수집 없음"),
         "tier": ("good" if (apple_top1 is not None and s["top1_rate"] is not None and s["top1_rate"] >= apple_top1) else ("bad" if apple_top1 is not None else "none"))},
        {"label": "전주 대비 변화", "value": f"▼{len(downs)} ▲{len(ups)}", "sub": "순위 상태 바뀐 칸" if prev_run else "이전 실행 없음", "tier": "bad" if downs else "good" if prev_run else "none"},
    ]
    worst_c = countries[0] if countries else None
    all_absent = [c for c in countries if c["checked"] and c["absent"] == c["checked"]]
    headline = f"1위 비율 {s['top1_rate'] if s['top1_rate'] is not None else '-'}% · 미노출 {s['by_status'].get('absent', 0)}칸" + (f" · Apple {apple_top1}%" if apple_top1 is not None else "")
    if all_absent:
        conclusion = f"{', '.join(c['label'] for c in all_absent[:4])}{'…' if len(all_absent) > 4 else ''}에서 전 제품 미노출 — 피드·GMC 등록 상태부터 확인."
    elif worst_c and worst_c["top1_rate"] is not None and worst_c["top1_rate"] < 40:
        conclusion = f"{worst_c['label']} 1위 비율 {worst_c['top1_rate']}% 가 가장 낮음 — 1위 판매처({', '.join(list(s.get('first_stores', {}).keys())[:3])}) 가격·속성 대비 점검."
    elif downs:
        conclusion = f"전주 대비 {len(downs)}칸 순위 하락 — 하락 칸부터 점검."
    else:
        conclusion = "큰 하락 없음 — 속성 노출률 낮은 영역과 Apple 대비 열세 영역만 확인."
    actions: List[str] = [x.get("line") or x.get("text") for x in ((insights or {}).get("top") or []) if (x.get("line") or x.get("text"))][:5]
    if not actions:
        for c in all_absent[:2]:
            actions.append(f"{c['label']} 전 제품 미노출 — GMC 피드 등록 확인")
        for c in downs[:2]:
            actions.append(f"{cname.get(c['country'], c['country'])} {plabel.get(c['product'], c['product'])} {STATUS_KO.get(c['changes']['status'][0], '')} → {STATUS_KO.get(c['changes']['status'][1], '')} 원인 확인")
        actions = actions[:5] or ["현 상태 유지 — 다음 주 변화만 확인"]
    return {"week": run.get("week", ""), "at": run.get("at", ""), "headline": headline, "conclusion": conclusion, "kpis": kpis,
            "countries": countries, "products": products, "actions": actions, "apple": apple, "changes": changes, "downs": downs,
            "first_stores": s.get("first_stores", {}),
            "basis": (insights or {}).get("basis") or "판단 기준: 1위 비율·속성 노출 70% 미만 = 부족 · Apple 보다 10%p 이상 낮음 = 열세 · 미조회 칸은 분모 제외"}


# ── 엑셀 첫 시트 ──
def write_summary_sheet(wb, S: Dict[str, Any]):
    from openpyxl.styles import Font, PatternFill, Alignment
    ws = wb.create_sheet("요약판", 0)
    H = Font(bold=True, color="FFFFFF", name="Arial"); HF = PatternFill("solid", fgColor="8A5A00"); sub = Font(size=10, name="Arial", color="667085")
    ws.append([f"honeyComb 🐝 — 요약판 · {S['week']} · {S['at']}"]); ws["A1"].font = Font(bold=True, size=16, name="Arial")
    ws.append([S["headline"]]); ws["A2"].font = Font(bold=True, size=12, name="Arial", color="8A5A00")
    ws.append([S["conclusion"]]); ws.merge_cells("A3:H3"); ws["A3"].alignment = Alignment(wrap_text=True); ws.row_dimensions[3].height = 30
    ws.append([])
    r0 = ws.max_row + 1
    for i, k in enumerate(S["kpis"], 1):
        ws.cell(r0, i, k["label"]).font = sub
        ws.cell(r0 + 1, i, k["value"]).font = Font(bold=True, size=18, name="Arial", color=TIER_HEX.get(k.get("tier") or "", "1D2433"))
        ws.cell(r0 + 2, i, k.get("sub", "")).font = sub
        for rr in (r0, r0 + 1, r0 + 2):
            ws.cell(rr, i).fill = PatternFill("solid", fgColor="FFF7E6"); ws.cell(rr, i).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.append([]); ws.append(["이번 주 할 일 Top 5"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    for i, a in enumerate(S["actions"], 1):
        ws.append([f"{i}. {a}"]); ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=8)
    ws.append([]); ws.append(["국가별 (1위 비율 낮은 순)"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    ws.append(["국가", "조회 칸", "1위", "상단", "미노출", "1위 비율 %", "Apple 1위 비율 %", "상태"])
    for c in ws[ws.max_row]:
        c.font, c.fill = H, HF
    for c in S["countries"]:
        ws.append([c["label"], c["checked"], c["top1"], c["topn"], c["absent"], c["top1_rate"], c["apple_top1"], c["state"]])
    ws.append([]); ws.append(["제품별"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    ws.append(["제품", "조회 칸", "1위", "미노출", "1위 비율 %"])
    for c in ws[ws.max_row]:
        c.font, c.fill = H, HF
    for p in S["products"]:
        ws.append([p["label"], p["checked"], p["top1"], p["absent"], p["top1_rate"]])
    if S.get("apple") and S["apple"].get("by_group"):
        ws.append([]); ws.append(["속성 영역별 노출률 — 삼성 vs Apple"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
        ws.append(["영역", "삼성 %", "Apple %", "차이 p"])
        for c in ws[ws.max_row]:
            c.font, c.fill = H, HF
        for g in S["apple"]["by_group"]:
            sv, av = g.get("samsung"), g.get("apple")
            ws.append([g["group"], sv, av, round(sv - av, 1) if (sv is not None and av is not None) else None])
    if S.get("downs"):
        ws.append([]); ws.append(["전주 대비 순위 하락 칸"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial", color="D8362F")
        ws.append(["국가", "제품", "키워드", "이전 → 현재"])
        for c in ws[ws.max_row]:
            c.font, c.fill = H, HF
        for d in S["downs"]:
            st = d["changes"]["status"]
            ws.append([d["country"], d["product"], d["keyword"], f"{STATUS_KO.get(st[0], st[0])} → {STATUS_KO.get(st[1], st[1])}"])
    ws.append([]); ws.append([S["basis"]]); ws.cell(ws.max_row, 1).font = Font(size=9, italic=True, name="Arial", color="98A2B3")
    for col, w in zip("ABCDEFGH", (22, 12, 10, 10, 12, 14, 18, 14)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"


# ── 메일 블록 ──
def email_block_html(S: Dict[str, Any]) -> str:
    cells = "".join(
        "<td valign='top' style='padding:3px'><div style='border:1px solid #FCE3A6;border-radius:8px;padding:8px 6px;text-align:center;background:#FFF7E6'>"
        f"<div style='font-size:10px;color:#667085'>{escape(k['label'])}</div>"
        f"<div style='font-size:18px;font-weight:800;color:#{TIER_HEX.get(k.get('tier') or '', '1D2433')};line-height:1.2'>{escape(str(k['value']))}</div>"
        f"<div style='font-size:9.5px;color:#98A2B3'>{escape(str(k.get('sub', '')))}</div></div></td>" for k in S["kpis"])
    acts = "".join(f"<div style='font-size:12px;margin-top:3px'>{i}. {escape(a)}</div>" for i, a in enumerate(S["actions"], 1))
    rows = "".join(f"<tr><td style='padding:3px 6px;font-size:11.5px'><b>{escape(c['label'])}</b></td><td style='padding:3px 6px;font-size:11.5px'>{escape(c['state'])}</td>"
                   f"<td style='padding:3px 6px;font-size:11.5px;text-align:right'>{c['top1_rate'] if c['top1_rate'] is not None else '-'}%</td>"
                   f"<td style='padding:3px 6px;font-size:11.5px;text-align:right;color:#667085'>{c['apple_top1'] if c['apple_top1'] is not None else '-'}%</td>"
                   f"<td style='padding:3px 6px;font-size:11.5px;text-align:right'>{c['absent']}/{c['checked']}</td></tr>" for c in S["countries"][:12])
    return ("<div style='border:2px solid #8A5A00;border-radius:12px;padding:14px;margin-bottom:16px;background:#fff'>"
            "<div style='font-size:11px;font-weight:800;color:#8A5A00;letter-spacing:.04em'>요약판</div>"
            f"<div style='font-size:15px;font-weight:800;color:#101318;margin-top:4px'>{escape(S['headline'])}</div>"
            f"<div style='font-size:12.5px;color:#475467;margin-top:4px'>{escape(S['conclusion'])}</div>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:10px'><tr>{cells}</tr></table>"
            "<div style='font-size:12px;font-weight:800;margin-top:12px'>이번 주 할 일 Top 5</div>" + acts +
            "<div style='font-size:12px;font-weight:800;margin-top:12px'>국가별 <span style='font-weight:400;color:#98A2B3'>(상태 · 삼성 1위 비율 · Apple 1위 비율 · 미노출/조회)</span></div>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:4px'>{rows}</table>"
            f"<div style='font-size:10px;color:#98A2B3;margin-top:10px'>{escape(S['basis'])}</div></div>")


# ── PPT ──
def _actions_struct(S: Dict[str, Any], insights: Optional[Dict[str, Any]], cname, plabel) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for x in ((insights or {}).get("top") or [])[:5]:
        txt, act = (x.get("text") or ""), (x.get("action") or "")
        out.append({"title": act or txt, "detail": txt if act else "", "tag": "GMC 피드" if ("속성" in (txt + act)) else "채널", "tier": "bad" if x.get("sev") == 1 else "mid"})
    if not out:
        for c in [c for c in S["countries"] if c["checked"] and c["absent"] == c["checked"]][:2]:
            out.append({"title": f"{c['label']} 전 제품 미노출 — GMC 피드 등록 확인", "detail": "", "tag": "GMC 피드", "tier": "bad"})
        for d in S["downs"][:2]:
            st = d["changes"]["status"]
            out.append({"title": f"{cname.get(d['country'], d['country'])} {plabel.get(d['product'], d['product'])} 순위 하락 원인 확인", "detail": f"{STATUS_KO.get(st[0], st[0])} → {STATUS_KO.get(st[1], st[1])}", "tag": "채널", "tier": "mid"})
    return out


def build_pptx(S: Dict[str, Any], run: Dict[str, Any], config: Dict[str, Any], attributes: List[Dict[str, Any]], insights: Optional[Dict[str, Any]] = None) -> bytes:
    import os, sys, importlib.util
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    try:
        import pptx_common as P
    except ImportError:   # 패키징(exe)·작업 디렉터리 차이로 못 찾을 때 파일 경로로 직접 로드
        _spec = importlib.util.spec_from_file_location("pptx_common", os.path.join(_root, "pptx_common.py"))
        P = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(P)
    from pptx.dml.color import RGBColor
    ACC = RGBColor(0x8A, 0x5A, 0x00)
    cname = {c["code"]: c["label"] for c in config.get("countries", [])}; plabel = {p["slug"]: p["label"] for p in config.get("products", [])}
    prs = P.new_deck()
    P.cover(prs, "honeyComb 🐝 Google Shopping 노출 리포트", f"{S['week']} — 삼성닷컴 vs Apple 공식몰", S["at"], ACC,
            "요약판 1장 + 상세. 숫자는 화면·엑셀·메일과 같은 데이터(hc_exec_summary)에서 나옵니다.")
    kp = {k["label"]: k for k in S["kpis"]}
    top1 = kp.get("1위 비율", {})
    t1 = None
    try:
        t1 = float(str(top1.get("value", "")).rstrip("%"))
    except Exception:
        pass
    absent = int(kp.get("미노출 칸", {}).get("value", "0") or 0)
    verdict = ({"label": "주의", "tier": "bad"} if (t1 is not None and t1 < 40) or absent else {"label": "점검", "tier": "mid"} if (t1 is not None and t1 < 70) or S["downs"] else {"label": "양호", "tier": "good"})
    kpis4 = [k for k in (kp.get("1위 비율"), kp.get("미노출 칸"), kp.get("속성 노출률"), kp.get("Apple 1위 비율")) if k]
    rank_rows = [{"name": c["label"], "status": c["state"].split(" ", 1)[-1], "tier": "bad" if c["state"].startswith("🔴") else ("good" if c["state"].startswith("🟢") else "mid"),
                  "value": f"{c['top1_rate'] if c['top1_rate'] is not None else '-'}%" + (f" · Apple {c['apple_top1']}%" if c.get("apple_top1") is not None else ""), "bar": c["top1_rate"]} for c in S["countries"][:8]]
    P.summary_slide(prs, ACC, "요약판", f"{S['week']} · {S['at']} · 제품명 키워드 기준", S["headline"], verdict, kpis4, _actions_struct(S, insights, cname, plabel),
                    {"title": "어디가 문제인가 (1위 비율 낮은 순)", "rows": rank_rows}, basis=S["basis"], conclusion=S["conclusion"])
    countries = [c["code"] for c in config.get("countries", [])]; prods = [p["slug"] for p in config.get("products", [])]
    cell = {(c["country"], c["product"]): c for c in run.get("cells", []) if c.get("keyword_type") == "brand"}
    mrows = [[plabel.get(p, p)] + [STATUS_KO.get((cell.get((ct, p)) or {}).get("status", "unchecked"), "-") for ct in countries] for p in prods]
    P.table_slide(prs, ACC, "국가 × 제품 — 셀 상태", "제품명 키워드 · 1위 / 상단(1위 아님) / 하위 / 미노출 / 미조회", ["제품"] + [cname.get(c, c) for c in countries], mrows,
                  [1.8] + [1.0] * len(countries), status_col=-1)
    if S.get("apple") and S["apple"].get("by_group"):
        rows = []
        for g in S["apple"]["by_group"]:
            sv, av = g.get("samsung"), g.get("apple"); diff = (round(sv - av, 1) if (sv is not None and av is not None) else None)
            rows.append({"item": g["group"], "grade": ("열세" if (diff is not None and diff <= -10) else "우세" if (diff is not None and diff >= 10) else "비슷"),
                         "tier": ("bad" if (diff is not None and diff <= -10) else "good" if (diff is not None and diff >= 10) else "mid"),
                         "what": f"삼성 {sv if sv is not None else '-'}% · Apple {av if av is not None else '-'}%", "how": (f"차이 {diff:+}p" if diff is not None else "비교 불가")})
        P.issue_slide(prs, ACC, "속성 영역별 노출률 — 삼성 vs Apple", "확인 안 함 속성 제외 · 10%p 이상 차이면 우세/열세", [{"head": "GMC 속성 영역", "sub": "", "rows": rows}], col_titles=("영역", "삼성 · Apple", "차이"))
    if S.get("changes"):
        rows = []
        for d in S["changes"]:
            st = d["changes"].get("status")
            down = d in S["downs"]
            rows.append({"item": f"{cname.get(d['country'], d['country'])} · {plabel.get(d['product'], d['product'])}", "grade": "하락" if down else "변화", "tier": "bad" if down else "mid",
                         "what": d["keyword"], "how": (f"{STATUS_KO.get(st[0], st[0])} → {STATUS_KO.get(st[1], st[1])}" if st else "속성 노출 변화")})
        P.issue_slide(prs, ACC, "전주 대비 변화", f"상태 바뀐 칸 {len(S['changes'])} · 하락 {len(S['downs'])}", [{"head": "변화 칸", "sub": "", "rows": rows}], col_titles=("국가 · 제품", "키워드", "변화"))
    if S.get("first_stores"):
        P.table_slide(prs, ACC, "1위 판매처 분포", "삼성이 1위가 아닌 칸의 1위 판매처", ["판매처", "칸 수"], [[k, v] for k, v in list(S["first_stores"].items())[:16]], [3, 1])
    return P.save(prs)

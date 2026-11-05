"""
as_exec_summary.py — appleStalker · 요약판 데이터 + 렌더(엑셀 첫 시트 · 메일 블록) [2026-11 신규]

화면 '전체요약' 상단(High 변경·3축 점수·우세/열세·근거 부족)과 같은 숫자를 백엔드에서 한 번 만들어
엑셀 첫 시트 `요약판` · 메일 맨 위 블록 · PPT 2번 슬라이드 · /api/latest-report(exec_summary) 가 공유한다.

build(dcv, changes, insights, timestamp) → {headline, conclusion, kpis, axes, sites, actions, basis}
"""
from __future__ import annotations
from html import escape
from typing import Any, Dict, List, Optional

from insight_rules_base import score_block, COMP_KO, SCORE_COMPONENTS, WEAK_BELOW, GAP_PP

OURS = "samsung"
AXIS_KO = {"data": "DATA", "copy": "COPY", "visual": "VISUAL"}
SITE_KO = {"samsung": "Samsung", "apple": "Apple", "google_pixel": "Google Pixel", "xiaomi": "Xiaomi", "oppo": "OPPO", "vivo": "vivo",
           "sony_audio": "Sony Audio", "garmin": "Garmin", "dell": "Dell", "meta_ai_glasses": "Meta AI Glasses"}
TIER_HEX = {"good": "1F9E5C", "mid": "E0A008", "bad": "D8362F", "none": "98A2B3", "": "1D2433"}


def _tier(v, good=70, mid=40):
    if v is None:
        return "none"
    return "good" if v >= good else "mid" if v >= mid else "bad"


def _avg(vals):
    v = [x for x in vals if isinstance(x, (int, float))]
    return round(sum(v) / len(v)) if v else None


def build(dcv: Dict[str, Any], changes: List[Dict[str, Any]], insights: Optional[Dict[str, Any]], timestamp: str = "") -> Dict[str, Any]:
    dcv = dcv or {}; changes = changes or []; insights = insights or {}
    sites = sorted({s for m in ("data", "copy", "visual") for s in (dcv.get(m) or {}).keys()}, key=lambda s: (s != OURS, s))
    scores: Dict[str, Dict[str, Optional[int]]] = {s: {} for s in sites}
    for m in ("data", "copy", "visual"):
        for s in sites:
            blk = (dcv.get(m) or {}).get(s)
            sb = blk.get("scores") if isinstance(blk, dict) and blk.get("scores") else (score_block(m, blk) if blk else {"total": None})
            scores[s][m] = sb.get("total")
    axes = []
    for m in ("data", "copy", "visual"):
        ours = scores.get(OURS, {}).get(m)
        comp = _avg([scores[s][m] for s in sites if s != OURS])
        rel = ("우세" if (ours is not None and comp is not None and ours - comp >= GAP_PP) else
               "열세" if (ours is not None and comp is not None and comp - ours >= GAP_PP) else
               "비슷" if (ours is not None and comp is not None) else "-")
        axes.append({"metric": m, "label": AXIS_KO[m], "samsung": ours, "comp_avg": comp, "tier": _tier(ours), "relative": rel,
                     "components": SCORE_COMPONENTS[m]})
    high = [c for c in changes if c.get("level") == "High"]
    med = [c for c in changes if c.get("level") == "Medium"]
    by_metric = insights.get("by_metric") or {}
    sam_lines = [x for m in by_metric for x in by_metric[m] if x.get("site") == "samsung"]
    weak = sum(1 for x in sam_lines if "열세" in (x.get("text") or "") or "부족" in (x.get("text") or ""))
    ahead = sum(1 for a in axes if a["relative"] == "우세")
    behind = sum(1 for a in axes if a["relative"] == "열세")
    no_evidence = [s for s in sites if all(scores[s].get(m) is None for m in ("data", "copy", "visual"))]
    site_rows = []
    for s in sites:
        ch = [c for c in changes if (c.get("site") or "") == s]
        h = sum(1 for c in ch if c.get("level") == "High")
        state = ("근거 부족" if s in no_evidence else ("High 변경" if h else ("변경 있음" if ch else "유지")))
        site_rows.append({"site": s, "label": SITE_KO.get(s, s), "data": scores[s].get("data"), "copy": scores[s].get("copy"), "visual": scores[s].get("visual"),
                          "changes": len(ch), "high": h, "state": state})
    kpis = [
        {"label": "변경 (High / 전체)", "value": f"{len(high)} / {len(changes)}", "sub": f"보통 {len(med)}", "tier": "bad" if high else ("mid" if changes else "good")},
    ] + [
        {"label": f"{a['label']} (Samsung)", "value": f"{a['samsung'] if a['samsung'] is not None else '-'}",
         "sub": (f"경쟁사 평균 {a['comp_avg']} · {a['relative']}" if a["comp_avg"] is not None else "경쟁사 근거 없음"), "tier": a["tier"]} for a in axes
    ] + [
        {"label": "경쟁사 대비 (축)", "value": f"▲{ahead} ▼{behind}", "sub": f"우세 {ahead} · 열세 {behind} · 보완 항목 {weak}건", "tier": "bad" if behind else ("good" if ahead else "none")},
        {"label": "근거 부족 사이트", "value": f"{len(no_evidence)}", "sub": (", ".join(SITE_KO.get(s, s) for s in no_evidence[:3]) + ("…" if len(no_evidence) > 3 else "")) if no_evidence else "전 사이트 근거 확보", "tier": "mid" if no_evidence else "good"},
    ]
    headline = ("분석 데이터 없음" if not sites else
                f"High 변경 {len(high)}건 · 전체 {len(changes)}건" if high else
                f"변경 {len(changes)}건 (High 없음)" if changes else "변경 없음")
    top = insights.get("top") or []
    if top:
        conclusion = top[0].get("line") or top[0].get("text") or ""
    elif high:
        conclusion = f"High 변경 {len(high)}건 — {', '.join(sorted({SITE_KO.get(c.get('site'), c.get('site')) for c in high}))} 먼저 확인."
    else:
        conclusion = "큰 변경 없음 — 열세 축과 경쟁사 벤치마크만 확인."
    actions = [x.get("line") or x.get("text") for x in top if (x.get("line") or x.get("text"))][:5]
    if not actions:
        for a in axes:
            if a["relative"] == "열세":
                actions.append(f"{a['label']} 경쟁사 대비 열세({a['samsung']} vs {a['comp_avg']}) — 점수 지표({' · '.join(COMP_KO.get(k, k) for k in a['components'])}) 중 낮은 항목 보강")
        actions = actions[:5] or ["현 상태 유지 — 경쟁사 변화만 모니터"]
    return {"timestamp": timestamp, "headline": headline, "conclusion": conclusion, "kpis": kpis, "axes": axes, "sites": site_rows,
            "actions": actions, "no_evidence": no_evidence,
            "basis": insights.get("basis") or (f"판단 기준: {WEAK_BELOW}점 미만 = 부족 · 경쟁사 평균보다 {GAP_PP}%p 이상 낮음 = 열세, 높음 = 우세 · 점수 = 축별 점수 지표 단순 평균")}


def write_summary_sheet(wb, S: Dict[str, Any]):
    from openpyxl.styles import Font, PatternFill, Alignment
    ws = wb.create_sheet("요약판", 0)
    H = Font(bold=True, color="FFFFFF", name="Arial"); HF = PatternFill("solid", fgColor="1B2A4A"); sub = Font(size=10, name="Arial", color="667085")
    ws.append([f"appleStalker — 요약판 · {S.get('timestamp', '')}"]); ws["A1"].font = Font(bold=True, size=16, name="Arial")
    ws.append([S["headline"]]); ws["A2"].font = Font(bold=True, size=12, name="Arial", color="1B2A4A")
    ws.append([S["conclusion"]]); ws.merge_cells("A3:H3"); ws["A3"].alignment = Alignment(wrap_text=True); ws.row_dimensions[3].height = 30
    ws.append([])
    r0 = ws.max_row + 1
    for i, k in enumerate(S["kpis"], 1):
        ws.cell(r0, i, k["label"]).font = sub
        ws.cell(r0 + 1, i, k["value"]).font = Font(bold=True, size=18, name="Arial", color=TIER_HEX.get(k.get("tier") or "", "1D2433"))
        ws.cell(r0 + 2, i, k.get("sub", "")).font = sub
        for rr in (r0, r0 + 1, r0 + 2):
            ws.cell(rr, i).fill = PatternFill("solid", fgColor="F7F8FA"); ws.cell(rr, i).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.append([]); ws.append(["지금 할 일 Top 5"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    for i, a in enumerate(S["actions"], 1):
        ws.append([f"{i}. {a}"]); ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=8)
    ws.append([]); ws.append(["사이트별 점수·변경"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    ws.append(["사이트", "DATA", "COPY", "VISUAL", "변경", "High", "상태"])
    for c in ws[ws.max_row]:
        c.font, c.fill = H, HF
    for r in S["sites"]:
        ws.append([("★ " if r["site"] == OURS else "") + r["label"], r["data"], r["copy"], r["visual"], r["changes"], r["high"], r["state"]])
        for ci, m in ((2, "data"), (3, "copy"), (4, "visual")):
            v = r[m]
            if v is not None:
                ws.cell(ws.max_row, ci).font = Font(bold=True, name="Arial", color=TIER_HEX[_tier(v)])
    ws.append([]); ws.append(["축별 — Samsung vs 경쟁사 평균 (점수 지표)"]); ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, name="Arial")
    ws.append(["축", "Samsung", "경쟁사 평균", "판정", "점수 지표"])
    for c in ws[ws.max_row]:
        c.font, c.fill = H, HF
    for a in S["axes"]:
        ws.append([a["label"], a["samsung"], a["comp_avg"], a["relative"], " · ".join(COMP_KO.get(k, k) for k in a["components"])])
    ws.append([]); ws.append([S["basis"]]); ws.cell(ws.max_row, 1).font = Font(size=9, italic=True, name="Arial", color="98A2B3")
    for col, w in zip("ABCDEFGH", (22, 14, 14, 14, 12, 10, 14, 30)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"


def email_block_html(S: Dict[str, Any]) -> str:
    cells = "".join(
        "<td valign='top' style='padding:3px'><div style='border:1px solid #EEF0F3;border-radius:8px;padding:8px 6px;text-align:center;background:#F7F8FA'>"
        f"<div style='font-size:10px;color:#667085'>{escape(k['label'])}</div>"
        f"<div style='font-size:17px;font-weight:800;color:#{TIER_HEX.get(k.get('tier') or '', '1D2433')};line-height:1.2'>{escape(str(k['value']))}</div>"
        f"<div style='font-size:9.5px;color:#98A2B3'>{escape(str(k.get('sub', '')))}</div></div></td>" for k in S["kpis"])
    acts = "".join(f"<div style='font-size:12px;margin-top:3px'>{i}. {escape(a)}</div>" for i, a in enumerate(S["actions"], 1))
    rows = "".join(
        f"<tr><td style='padding:3px 6px;font-size:11.5px'><b>{'★ ' if r['site'] == OURS else ''}{escape(r['label'])}</b></td>"
        + "".join(f"<td style='padding:3px 6px;font-size:11.5px;text-align:right;font-weight:700;color:#{TIER_HEX[_tier(r[m])]}'>{'-' if r[m] is None else r[m]}</td>" for m in ("data", "copy", "visual"))
        + f"<td style='padding:3px 6px;font-size:11.5px;text-align:right'>{r['changes']} ({r['high']})</td><td style='padding:3px 6px;font-size:11.5px;color:#667085'>{escape(r['state'])}</td></tr>"
        for r in S["sites"])
    return ("<div style='border:2px solid #1B2A4A;border-radius:12px;padding:14px;margin-bottom:16px;background:#fff'>"
            "<div style='font-size:11px;font-weight:800;color:#1B2A4A;letter-spacing:.04em'>요약판</div>"
            f"<div style='font-size:15px;font-weight:800;color:#101318;margin-top:4px'>{escape(S['headline'])}</div>"
            f"<div style='font-size:12.5px;color:#475467;margin-top:4px'>{escape(S['conclusion'])}</div>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:10px'><tr>{cells}</tr></table>"
            "<div style='font-size:12px;font-weight:800;margin-top:12px'>지금 할 일 Top 5</div>" + acts +
            "<div style='font-size:12px;font-weight:800;margin-top:12px'>사이트별 <span style='font-weight:400;color:#98A2B3'>(DATA · COPY · VISUAL · 변경(High) · 상태)</span></div>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:4px'>{rows}</table>"
            f"<div style='font-size:10px;color:#98A2B3;margin-top:10px'>{escape(S['basis'])}</div></div>")


# ── PPT 요약판 입력(구조화) ──
def pptx_parts(S: Dict[str, Any], insights: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """summary_slide 에 넣을 verdict / kpis4 / actions / ranking."""
    kp = {k["label"]: k for k in S["kpis"]}
    high = int(str(kp.get("변경 (High / 전체)", {}).get("value", "0 / 0")).split("/")[0].strip() or 0)
    behind = sum(1 for a in S["axes"] if a["relative"] == "열세")
    verdict = ({"label": "오늘 확인", "tier": "bad"} if (high or behind) else {"label": "변화 확인", "tier": "mid"} if S["headline"].startswith("변경") and "없음" not in S["headline"] else {"label": "유지", "tier": "good"})
    kpis4 = [kp.get("변경 (High / 전체)")] + [kp.get(f"{a['label']} (Samsung)") for a in S["axes"]]
    kpis4 = [k for k in kpis4 if k]
    actions = []
    for x in ((insights or {}).get("top") or [])[:5]:
        txt, act = (x.get("text") or ""), (x.get("action") or "")
        m = (x.get("metric") or "").upper()
        actions.append({"title": act or txt, "detail": txt if act else "", "tag": {"DATA": "DATA", "COPY": "COPY", "VISUAL": "VISUAL"}.get(m, "변경"),
                        "tier": "bad" if x.get("sev") == 1 else "mid"})
    if not actions:
        for a in S["axes"]:
            if a["relative"] == "열세":
                actions.append({"title": f"{a['label']} 경쟁사 대비 열세 보강", "detail": f"Samsung {a['samsung']} vs 경쟁사 평균 {a['comp_avg']}", "tag": a["label"], "tier": "mid"})
    rows = []
    for r in sorted(S["sites"], key=lambda r: (-(r["high"]), -(r["changes"]), 0 if r["site"] == OURS else 1)):
        vals = [v for v in (r["data"], r["copy"], r["visual"]) if v is not None]
        avg = round(sum(vals) / len(vals)) if vals else None
        tier = "bad" if r["high"] else ("none" if r["state"] == "근거 부족" else ("mid" if r["changes"] else "good"))
        rows.append({"name": ("★ " if r["site"] == OURS else "") + r["label"], "status": r["state"], "tier": tier,
                     "value": f"D{r['data'] if r['data'] is not None else '-'} C{r['copy'] if r['copy'] is not None else '-'} V{r['visual'] if r['visual'] is not None else '-'}", "bar": avg})
    return {"verdict": verdict, "kpis": kpis4, "actions": actions, "ranking": {"title": "사이트별 (변경 많은 순 · 막대=3축 평균)", "rows": rows[:8]}}

"""
export_service.py — DATA/COPY/VISUAL 구조 그대로 Excel/PPT로 내보내기

[PHASE3 변경]
- 기존엔 changes(변경점) 리스트만 export → 변화가 없으면 "변경 없음" 한 줄 뿐이었음.
- 이제 latest_report() 가 반환하는 dcv={data,copy,visual}(사이트별 facts+narrative)를
  항상 함께 받아서, 변화 유무와 무관하게 "현행 분석" 시트/슬라이드를 만든다.
- 화면(page.tsx)의 DATA/COPY/VISUAL 탭 구조와 1:1 대응되도록 시트/슬라이드를 분리한다.
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import Any, Dict, List

COLS = ["사이트", "카테고리", "중요도", "항목", "이전 원문", "현재 원문", "URL"]
SITE_KO = {"samsung": "Samsung", "apple": "Apple", "google_pixel": "Google Pixel", "xiaomi": "Xiaomi", "oppo": "OPPO", "vivo": "vivo", "sony_audio": "Sony Audio", "garmin": "Garmin", "dell": "Dell", "meta_ai_glasses": "Meta AI Glasses"}
LV_KO = {"High": "높음", "Medium": "보통", "Low": "낮음"}
BUCKET_OF = {"데이터·스키마": "DATA", "카피": "COPY", "가격·프로모션": "COPY", "비주얼": "VISUAL"}


def _row(c: Dict[str, Any]) -> List[str]:
    return [
        SITE_KO.get(c.get("site"), c.get("site") or ""),
        c.get("category") or "", LV_KO.get(c.get("level"), c.get("level") or ""),
        c.get("field") or "", c.get("before") or "", c.get("after") or "", c.get("url") or "",
    ]


def _narrative_lines(dcv: Dict[str, Any], bucket: str) -> List[Dict[str, str]]:
    """dcv['data'|'copy'|'visual'] = {site_name: {facts, narrative or insights}} → (site, line) 평탄화."""
    out = []
    by_site = (dcv or {}).get(bucket, {}) or {}
    for site, block in by_site.items():
        site_ko = SITE_KO.get(site, site)
        lines = block.get("narrative") if isinstance(block, dict) else None
        if not lines:
            # IntelEngine.analyze_site() 결과 형태(insights 리스트)도 호환
            insights = (block or {}).get("insights", [])
            lines = [i.get("point") for i in insights if isinstance(i, dict) and i.get("point")]
        for line in (lines or []):
            out.append({"site": site_ko, "line": line})
    return out


def _group_by_page(changes: List[Dict[str, Any]]):
    """변경점을 URL(페이지) 단위로 그룹핑. 등장 순서를 유지한다."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for c in changes:
        url = c.get("url") or "(URL 없음)"
        if url not in groups:
            groups[url] = []
            order.append(url)
        groups[url].append(c)
    return [(u, groups[u]) for u in order]


def build_xlsx(changes: List[Dict[str, Any]], title: str = "", timestamp: str = "",
                dcv: Dict[str, Any] | None = None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook()

    # ── 시트1: 변경점 (기존 그대로) ──
    ws = wb.active; ws.title = "변경점"
    ws.append([f"Apple Stalker — 변경점  ({timestamp})"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLS))
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    head = PatternFill("solid", fgColor="111318"); hf = Font(color="FFFFFF", bold=True, size=10)
    ws.append(COLS)
    for c in range(1, len(COLS) + 1):
        cell = ws.cell(3, c); cell.fill = head; cell.font = hf
    for ch in changes:
        ws.append(_row(ch))
    widths = [16, 14, 8, 16, 48, 48, 40]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for r in ws.iter_rows(min_row=4):
        for cell in r:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A4"
    if not changes:
        ws.append(["변경 없음 — 아래 DATA/COPY/VISUAL 시트에서 현행 분석을 확인하세요"])

    # ── [신규] 시트: 페이지별 변경점 — 같은 URL의 변경들을 한 데 묶어서, 페이지 단위로
    #    "무엇이 이전→이후로 바뀌었는지" 한눈에 보이게 함 (기존 '변경점' 시트는 flat이라
    #    여러 페이지가 뒤섞여 보기 어려웠음) ──
    ws3 = wb.create_sheet("페이지별 변경점")
    ws3.append([f"페이지별 변경점 ({timestamp})"])
    ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
    ws3["A1"].font = Font(bold=True, size=13)
    ws3.append([])
    page_groups = _group_by_page(changes)
    if not page_groups:
        ws3.append(["이 수집에서는 페이지별 변경점이 없습니다."])
    else:
        sub_head = PatternFill("solid", fgColor="EEF1F5")
        page_head = PatternFill("solid", fgColor="111318")
        for url, items in page_groups:
            site_ko = SITE_KO.get(items[0].get("site"), items[0].get("site") or "")
            ws3.append([f"{site_ko} · {url}  —  {len(items)}건 변경"])
            r = ws3.max_row
            ws3.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
            ws3.cell(r, 1).font = Font(bold=True, size=11, color="FFFFFF")
            ws3.cell(r, 1).fill = page_head
            ws3.append(["카테고리", "중요도", "항목", "이전 원문", "현재 원문"])
            r2 = ws3.max_row
            for c in range(1, 6):
                cell = ws3.cell(r2, c); cell.font = Font(bold=True, size=9); cell.fill = sub_head
            for it in items:
                ws3.append([
                    it.get("category") or "", LV_KO.get(it.get("level"), it.get("level") or ""),
                    it.get("field") or "", it.get("before") or "", it.get("after") or "",
                ])
            ws3.append([])  # 페이지 구분 빈 줄
        ws3.column_dimensions["A"].width = 16
        ws3.column_dimensions["B"].width = 10
        ws3.column_dimensions["C"].width = 18
        ws3.column_dimensions["D"].width = 50
        ws3.column_dimensions["E"].width = 50
        for r in ws3.iter_rows(min_row=4):
            for cell in r:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws3.freeze_panes = "A4"

    # ── 시트2~4: [PHASE3 신규] DATA / COPY / VISUAL 현행 분석 (변화 유무 무관, 항상 생성) ──
    for bucket, sheet_name in [("data", "DATA"), ("copy", "COPY"), ("visual", "VISUAL")]:
        ws2 = wb.create_sheet(sheet_name)
        ws2.append([f"{sheet_name} 영역 — 현행 분석 근거 ({timestamp})"])
        ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
        ws2["A1"].font = Font(bold=True, size=13)
        ws2.append([])
        ws2.append(["사이트", "근거/서술"])
        for c in range(1, 3):
            cell = ws2.cell(3, c); cell.fill = head; cell.font = hf
        rows = _narrative_lines(dcv or {}, bucket)
        if not rows:
            ws2.append(["—", "이 영역에 대한 분석 데이터가 없습니다 (크롤이 1회 이상 완료되어야 표시됩니다)"])
        for r in rows:
            ws2.append([r["site"], r["line"]])
        ws2.column_dimensions["A"].width = 18
        ws2.column_dimensions["B"].width = 90
        for r in ws2.iter_rows(min_row=4):
            for cell in r:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws2.freeze_panes = "A4"

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
# PPTX — 점수 스코어보드 + 축별 스코어카드 + 변경점 (표·색 박스 재설계)
# 점수는 프론트 metricScoreBreakdown 과 동일 산식(하위지표 전체 평균)을 Python으로 재현.
# ══════════════════════════════════════════════════════════════════
OURS_KEY = "samsung"


def _avg(vals):
    v = [x for x in vals if isinstance(x, (int, float))]
    return round(sum(v) / len(v)) if v else None


def _score_breakdown(bucket: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """(components[상위3], all[전체], total) — 프론트와 동일 로직."""
    f = facts or {}
    comp = []
    if bucket == "data":
        sch = f.get("schema", {}) or {}
        schema = round(sch["coverage_pct"]) if isinstance(sch.get("coverage_pct"), (int, float)) else None
        h1v = (((f.get("html_structure") or {}).get("h_tag_coverage") or {}).get("h1_coverage_pct"))
        h1 = round(h1v) if isinstance(h1v, (int, float)) else None
        tcnt = len(sch.get("schema_type_counts") or {})
        structured = min(100, tcnt * 30) if tcnt > 0 else schema
        tp = sch.get("total_pages") or 0
        gaps = len(sch.get("role_alignment_gaps") or [])
        rolefit = round((tp - min(gaps, tp)) / tp * 100) if tp else None
        pf = ((sch.get("completeness") or {}).get("Product") or {}).get("filled_ratio")
        prod = round(pf * 100) if isinstance(pf, (int, float)) else None
        idl = sch.get("id_linkage") or {}
        idt = idl.get("total_id_nodes") or 0
        idlink = round((idl.get("linked_ids") or 0) / idt * 100) if idt else None
        comp = [("Schema", schema), ("H-tag", h1), ("타입다양성", structured),
                ("역할적합성", rolefit), ("Product완성도", prod), ("@id연결성", idlink)]
    elif bucket == "copy":
        cr = f.get("copy_richness", {}) or {}
        pages = cr.get("all_pages") or []
        richness = _avg([p.get("score") for p in pages])
        tp = len(pages) or ((f.get("page_inventory") or {}).get("total_pages") or 0)
        buy = (f.get("commerce_cta") or {}).get("pages_with_buy_cta")
        cta = round(buy / tp * 100) if isinstance(buy, (int, float)) and tp else None
        wok = len([p for p in pages if (p.get("word_count") or 0) >= 80])
        wcov = round(wok / len(pages) * 100) if pages else None
        det = (f.get("faq") or {}).get("detail") or []
        faq = _avg([d.get("avg_score") for d in det]) if det else None
        ig = len(cr.get("intent_gap_pages") or [])
        intent = round((len(pages) - min(ig, len(pages))) / len(pages) * 100) if pages else None
        dup = len((f.get("duplication") or {}).get("duplicate_copy_pages") or []) + \
              len((f.get("duplication") or {}).get("duplicate_cta_pages") or [])
        dupav = 100 - round(min(dup, tp) / tp * 100) if tp else None
        comp = [("구체성", richness), ("CTA", cta), ("분량", wcov),
                ("FAQ품질", faq), ("intent", intent), ("중복회피", dupav)]
    else:
        aq = (f.get("alt_text_quality") or {}).get("descriptive_ratio_pct")
        alt = round(aq) if isinstance(aq, (int, float)) else None
        idv = f.get("image_diversity") or {}
        dvr = idv.get("lifestyle_ratio_pct")
        diversity = round(dvr) if isinstance(dvr, (int, float)) else None
        ti = idv.get("total_images") or 0
        tp = (f.get("page_inventory") or {}).get("total_pages") or ti
        cov = min(100, round(ti / tp * 100)) if ti and tp else None
        comp = [("ALT", alt), ("다양성", diversity), ("커버리지", cov)]
    total = _avg([v for _, v in comp])
    return {"components": comp[:3], "all": comp, "total": total}


def _tier(score):
    if score is None:
        return "none"
    return "good" if score >= 70 else "mid" if score >= 40 else "bad"


def build_pptx(changes: List[Dict[str, Any]], title: str = "", timestamp: str = "",
               summary: str = "", dcv: Dict[str, Any] | None = None) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    dcv = dcv or {}
    # ── 팔레트 (Charcoal·Navy executive) ──
    NAVY = RGBColor(0x1B, 0x2A, 0x4A); INK = RGBColor(0x1A, 0x1D, 0x24); GRAY = RGBColor(0x6B, 0x72, 0x80)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF); PANEL = RGBColor(0xF2, 0xF4, 0xF7); LINE = RGBColor(0xE2, 0xE6, 0xEC)
    GOOD = RGBColor(0x1F, 0x9E, 0x5C); MID = RGBColor(0xE0, 0xA0, 0x08); BAD = RGBColor(0xD8, 0x36, 0x2F); NONE = RGBColor(0x9A, 0xA0, 0xA8)
    AXIS = {"data": RGBColor(0x0A, 0x66, 0xE0), "copy": RGBColor(0x7A, 0x3E, 0xA1), "visual": RGBColor(0x1A, 0x7F, 0x37)}
    TIERC = {"good": GOOD, "mid": MID, "bad": BAD, "none": NONE}
    TIERL = {"good": "Strong", "mid": "Moderate", "bad": "Needs Attention", "none": "근거 없음"}
    AXIS_LABEL = {"data": "DATA · 스키마", "copy": "COPY · 카피", "visual": "VISUAL · 이미지"}
    SW, SH = Inches(13.333), Inches(7.5)

    prs = Presentation(); prs.slide_width = SW; prs.slide_height = SH
    BLANK = prs.slide_layouts[6]

    def slide():
        return prs.slides.add_slide(BLANK)

    def rect(sl, l, t, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE):
        sp = sl.shapes.add_shape(shape, l, t, w, h)
        if fill is None:
            sp.fill.background()
        else:
            sp.fill.solid(); sp.fill.fore_color.rgb = fill
        if line is None:
            sp.line.fill.background()
        else:
            sp.line.color.rgb = line; sp.line.width = Pt(0.75)
        sp.shadow.inherit = False
        return sp

    def text(sl, l, t, w, h, s, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
        tb = sl.shapes.add_textbox(l, t, w, h); tf = tb.text_frame
        tf.word_wrap = True; tf.vertical_anchor = anchor
        tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
        lines = s if isinstance(s, list) else [s]
        for i, ln in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = ln; p.alignment = align
            p.font.size = Pt(size); p.font.bold = bold; p.font.color.rgb = color
        return tb

    # 사이트별 축 점수 계산
    def sites_in(bucket):
        return list((dcv.get(bucket) or {}).keys())
    all_sites = []
    for b in ("data", "copy", "visual"):
        for s in sites_in(b):
            if s not in all_sites:
                all_sites.append(s)
    # 우리 먼저, 나머지 순서 유지
    all_sites = ([OURS_KEY] if OURS_KEY in all_sites else []) + [s for s in all_sites if s != OURS_KEY]

    breaks = {b: {} for b in ("data", "copy", "visual")}
    for b in ("data", "copy", "visual"):
        for s, blk in (dcv.get(b) or {}).items():
            breaks[b][s] = _score_breakdown(b, (blk or {}).get("facts") or {})

    def comp_delta(bucket, label, val):
        """우리 값 vs 경쟁사(비-samsung) 평균 대비 ±."""
        peers = [breaks[bucket][s] for s in breaks[bucket] if s != OURS_KEY]
        pv = _avg([dict(bk["all"]).get(label) for bk in peers]) if peers else None
        if val is None or pv is None:
            return None
        return val - pv

    # ── 1) 표지 ──
    s = slide()
    rect(s, 0, 0, SW, SH, fill=NAVY)
    text(s, Inches(0.9), Inches(2.5), Inches(11.5), Inches(1.4),
         "경쟁사 웹 분석 리포트", size=40, bold=True, color=WHITE)
    text(s, Inches(0.9), Inches(3.7), Inches(11.5), Inches(0.6),
         "Samsung vs 경쟁사 — DATA / COPY / VISUAL", size=18, color=RGBColor(0xCA, 0xDC, 0xFC))
    if timestamp:
        text(s, Inches(0.9), Inches(4.4), Inches(11.5), Inches(0.5), timestamp, size=13, color=RGBColor(0xAE, 0xB8, 0xCC))
    if summary:
        text(s, Inches(0.9), Inches(5.1), Inches(11.5), Inches(1.6), summary[:220], size=13, color=RGBColor(0xCA, 0xDC, 0xFC))

    # ── 2) Executive Summary — 스코어보드 표 + 우리 우선 액션 ──
    s = slide()
    text(s, Inches(0.7), Inches(0.45), Inches(12), Inches(0.7), "Executive Summary — 종합 점수", size=26, bold=True, color=INK)
    text(s, Inches(0.7), Inches(1.12), Inches(12), Inches(0.4),
         "점수 = 각 축 하위지표 전체 평균(0~100). 색은 신호등(70↑ Strong / 40~69 Moderate / 40↓ Needs Attention).", size=11, color=GRAY)

    rows = 1 + len(all_sites)
    tbl_shape = s.shapes.add_table(rows, 4, Inches(0.7), Inches(1.7), Inches(12), Inches(0.5 * rows))
    tbl = tbl_shape.table
    tbl.columns[0].width = Inches(4.5)
    for ci in (1, 2, 3):
        tbl.columns[ci].width = Inches(2.5)
    hdr = ["사이트", "DATA", "COPY", "VISUAL"]
    for ci, htxt in enumerate(hdr):
        c = tbl.cell(0, ci); c.fill.solid(); c.fill.fore_color.rgb = NAVY
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c.text_frame.paragraphs[0]; p.text = htxt; p.alignment = PP_ALIGN.CENTER if ci else PP_ALIGN.LEFT
        p.font.size = Pt(13); p.font.bold = True; p.font.color.rgb = WHITE
    for ri, site in enumerate(all_sites, start=1):
        ours = site == OURS_KEY
        c0 = tbl.cell(ri, 0); c0.fill.solid(); c0.fill.fore_color.rgb = (RGBColor(0xE9, 0xEF, 0xFB) if ours else WHITE)
        c0.vertical_anchor = MSO_ANCHOR.MIDDLE
        p0 = c0.text_frame.paragraphs[0]; p0.text = ("★ " if ours else "") + SITE_KO.get(site, site)
        p0.font.size = Pt(12); p0.font.bold = ours; p0.font.color.rgb = INK
        for ci, b in enumerate(("data", "copy", "visual"), start=1):
            total = (breaks[b].get(site) or {}).get("total")
            tier = _tier(total)
            c = tbl.cell(ri, ci); c.fill.solid(); c.fill.fore_color.rgb = TIERC[tier]
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]; p.text = "-" if total is None else str(total)
            p.alignment = PP_ALIGN.CENTER
            p.font.size = Pt(13); p.font.bold = True
            p.font.color.rgb = WHITE if tier != "none" else RGBColor(0x44, 0x44, 0x44)

    # 우리 우선 액션 3줄
    ay = Inches(1.7) + Inches(0.5 * rows) + Inches(0.35)
    text(s, Inches(0.7), ay, Inches(12), Inches(0.4), "우리(Samsung) 우선 액션", size=15, bold=True, color=INK)
    ay2 = ay + Inches(0.5)
    for b in ("data", "copy", "visual"):
        blk = (dcv.get(b) or {}).get(OURS_KEY) or {}
        facts = blk.get("facts") or {}
        bd = breaks[b].get(OURS_KEY) or {}
        act = _priority_action(b, facts, bd)
        rect(s, Inches(0.7), ay2, Inches(0.16), Inches(0.16), fill=AXIS[b])
        text(s, Inches(1.0), ay2 - Inches(0.03), Inches(11.4), Inches(0.5),
             f"{AXIS_LABEL[b].split(' ')[0]}  {act}", size=12, color=INK)
        ay2 += Inches(0.55)

    # ── 3) 축별 상세 ──
    for b in ("data", "copy", "visual"):
        s = slide()
        # 모티프: 색 원 + 축 이니셜
        circ = rect(s, Inches(0.7), Inches(0.5), Inches(0.62), Inches(0.62), fill=AXIS[b], shape=MSO_SHAPE.OVAL)
        cp = circ.text_frame.paragraphs[0]; cp.text = b[0].upper(); cp.alignment = PP_ALIGN.CENTER
        cp.font.size = Pt(22); cp.font.bold = True; cp.font.color.rgb = WHITE
        circ.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        text(s, Inches(1.5), Inches(0.55), Inches(11), Inches(0.7), f"{AXIS_LABEL[b]} — 현행 분석", size=24, bold=True, color=INK)

        bd = breaks[b].get(OURS_KEY) or {"components": [], "all": [], "total": None}
        total = bd.get("total"); tier = _tier(total)
        # 좌: 큰 점수
        rect(s, Inches(0.7), Inches(1.7), Inches(3.3), Inches(2.3), fill=PANEL)
        text(s, Inches(0.7), Inches(1.95), Inches(3.3), Inches(1.2),
             "-" if total is None else str(total), size=66, bold=True, color=TIERC[tier], align=PP_ALIGN.CENTER)
        text(s, Inches(0.7), Inches(3.25), Inches(3.3), Inches(0.4),
             f"Samsung 종합 · {TIERL[tier]}", size=13, bold=True, color=INK, align=PP_ALIGN.CENTER)
        text(s, Inches(0.7), Inches(3.62), Inches(3.3), Inches(0.3),
             "하위지표 전체 평균", size=10, color=GRAY, align=PP_ALIGN.CENTER)

        # 우: 주요 3개 하위지표 + 경쟁사 평균 대비
        rx = Inches(4.3); ry = Inches(1.7)
        text(s, rx, ry, Inches(8.3), Inches(0.35), "주요 지표 (경쟁사 평균 대비)", size=13, bold=True, color=INK)
        ry += Inches(0.5)
        for label, val in bd.get("components", []):
            d = comp_delta(b, label, val)
            dtxt = "" if d is None else (f"  ▲ +{d}p" if d > 0 else (f"  ▼ {d}p" if d < 0 else "  = 0p"))
            dcolor = GRAY if not d else (GOOD if d > 0 else BAD)
            text(s, rx, ry, Inches(3.2), Inches(0.4), label, size=13, color=INK)
            text(s, rx + Inches(3.2), ry, Inches(1.6), Inches(0.4),
                 "-" if val is None else f"{val}", size=13, bold=True, color=INK)
            text(s, rx + Inches(4.7), ry, Inches(3.4), Inches(0.4), dtxt, size=12, bold=True, color=dcolor)
            ry += Inches(0.52)

        # 핵심 근거 (narrative insights 2~3줄)
        ny = Inches(4.25)
        text(s, Inches(0.7), ny, Inches(12), Inches(0.35), "핵심 근거", size=13, bold=True, color=INK)
        blk = (dcv.get(b) or {}).get(OURS_KEY) or {}
        ev_lines = []
        for i in (blk.get("insights") or []):
            pt = i.get("point") if isinstance(i, dict) else None
            if pt:
                ev_lines.append(pt)
        if not ev_lines:
            ev_lines = ["이번 수집에서 표시할 근거가 부족합니다 (재수집 후 갱신)."]
        text(s, Inches(0.7), ny + Inches(0.4), Inches(12), Inches(1.3),
             ["· " + ln[:110] for ln in ev_lines[:3]], size=12, color=GRAY)

        # 우선 액션 박스 (은은한 tint)
        rect(s, Inches(0.7), Inches(6.05), Inches(12), Inches(1.05), fill=PANEL)
        text(s, Inches(0.95), Inches(6.2), Inches(11.5), Inches(0.35), "우선 액션", size=12, bold=True, color=AXIS[b])
        text(s, Inches(0.95), Inches(6.55), Inches(11.5), Inches(0.5),
             _priority_action(b, blk.get("facts") or {}, bd), size=13, color=INK)

    # ── 4) 변경점 (있을 때만) ──
    if changes:
        by_cat = {}
        for c in changes:
            by_cat[c.get("category") or "기타"] = by_cat.get(c.get("category") or "기타", 0) + 1
        s = slide()
        text(s, Inches(0.7), Inches(0.45), Inches(12), Inches(0.7), f"변경점 요약 — 총 {len(changes)}건", size=26, bold=True, color=INK)
        cy = Inches(1.5)
        for cat, cnt in by_cat.items():
            rect(s, Inches(0.7), cy, Inches(0.16), Inches(0.16), fill=NAVY)
            text(s, Inches(1.0), cy - Inches(0.03), Inches(11), Inches(0.4), f"{cat} — {cnt}건", size=14, color=INK)
            cy += Inches(0.5)

        page_groups = _group_by_page(changes)
        for url, items in page_groups[:8]:
            s = slide()
            site_ko = SITE_KO.get(items[0].get("site"), items[0].get("site") or "")
            text(s, Inches(0.7), Inches(0.45), Inches(12), Inches(0.5), f"{site_ko} — {len(items)}건 변경", size=20, bold=True, color=INK)
            text(s, Inches(0.7), Inches(1.0), Inches(12), Inches(0.4), url[:120], size=11, color=GRAY)
            gy = Inches(1.6)
            for ch in items[:6]:
                lv = ch.get("level"); lvc = {"High": BAD, "Medium": MID, "Low": GOOD}.get(lv, GRAY)
                rect(s, Inches(0.7), gy + Inches(0.05), Inches(0.16), Inches(0.16), fill=lvc)
                text(s, Inches(1.0), gy, Inches(11.4), Inches(0.35),
                     f"[{LV_KO.get(lv,'')}] {ch.get('category','')} · {ch.get('field','')}", size=12, bold=True, color=INK)
                text(s, Inches(1.0), gy + Inches(0.34), Inches(11.4), Inches(0.32),
                     f"이전: {(ch.get('before') or '(없음)')[:90]}  →  현재: {(ch.get('after') or '(삭제)')[:90]}", size=10.5, color=GRAY)
                gy += Inches(0.85)

    # ── 5) 기준 / 부록 ──
    s = slide()
    rect(s, 0, 0, SW, SH, fill=NAVY)
    text(s, Inches(0.9), Inches(0.9), Inches(11.5), Inches(0.7), "점수·액션 기준 (참고)", size=26, bold=True, color=WHITE)
    notes = [
        "· 점수는 각 축의 하위지표(DATA·COPY 6개, VISUAL 3개) 전체 평균이며, 화면 카드에는 주요 3개만 노출됩니다.",
        "· 스키마 역할 기대값은 '우리 사이트 Schema Link Map' 기준(참고)입니다. 절대 기준이 아니며, @id로 연결돼 있을 수 있어 누락=오류로 보지 않습니다.",
        "· 고급 스키마(FAQPage·Quotation·3DModel·VideoObject 등)는 없어도 되며, 있으면 검색·AI 노출에 유리한 '기회'로만 표기합니다.",
        "· VISUAL(이미지) 판단은 HTML 신호(ALT·파일명 등) 기반이며 실제 이미지 픽셀은 검증하지 않았습니다.",
        "· '규칙기반' 서술은 facts를 규칙으로 집계한 것이고, 'AI 분석'은 근거 위에 서술을 다듬은 것으로 점수 자체는 항상 규칙 기반입니다.",
    ]
    text(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(4.5), notes, size=14, color=RGBColor(0xCA, 0xDC, 0xFC))

    buf = io.BytesIO(); prs.save(buf); return buf.getvalue()


def _priority_action(bucket: str, facts: Dict[str, Any], bd: Dict[str, Any]) -> str:
    """축별 우선 액션 한 줄 ([상태] — [할 일+이유]). detailedAction 핵심 분기의 경량 Python판."""
    f = facts or {}
    allc = dict(bd.get("all") or [])
    if bucket == "data":
        sch = f.get("schema", {}) or {}
        types = list((sch.get("schema_type_counts") or {}).keys())
        roles = sch.get("page_role_distribution") or {}
        has_pdp = (roles.get("pdp") or 0) > 0
        has_buying = (roles.get("buying") or 0) > 0
        has_pf = (roles.get("pf") or 0) > 0
        low = lambda k: k.lower()
        def has(rx):
            return any(rx in low(t) for t in types)
        if allc.get("Schema") is None and allc.get("H-tag") is None:
            return "수집 근거 없음 — 관리 URL·수집 결과부터 확보."
        if has_pdp and not has("product"):
            return "PDP에 Product 스키마·@id 참조 없음 — Product 추가 또는 @id 연결로 제품 신호 노출."
        if has_buying and not has("productgroup"):
            return "Buying에 ProductGroup 없음 — ProductGroup 추가로 구매 옵션 묶음 신호 노출."
        if has_pf and not has("itemlist") and not has("collectionpage"):
            return "PF에 ItemList/CollectionPage 없음 — 목록 스키마로 카테고리 성격 노출."
        if types and not has("breadcrumb"):
            return "BreadcrumbList 없음 — Breadcrumb로 탐색 경로 신호 보강."
        if (allc.get("Schema") or 0) < 40:
            return "Schema 적용 페이지 비율 낮음 — 적용 페이지 확대로 구조화 신호 강화."
        return "핵심 스키마 신호 양호 — 현 구조 유지, 다음 수집에서 변화만 확인."
    if bucket == "copy":
        if (allc.get("분량") or 100) < 40:
            return "본문 분량(80단어↑) 충족 페이지 적음 — 스펙·소재·기능 설명 추가로 이해도↑."
        if (allc.get("구체성") or 100) < 40:
            return "카피 구체성 점수 낮음 — 수치·소재·기능 언급 추가로 구체성↑."
        if (allc.get("FAQ품질") is not None) and (allc.get("분량") or 100) < 70:
            return "FAQ는 있으나 본문 분량 충족 페이지 적음 — 제품 설명 분량 보강."
        if (allc.get("CTA") or 100) < 30:
            return "구매 CTA 커버리지 낮음 — PDP·Buying에 Buy/Where to buy 버튼 보강."
        return "핵심 카피 신호 양호 — 현 상태 유지, 경쟁사 문구 변화만 모니터."
    ti = (f.get("image_diversity") or {}).get("total_images") or 0
    cav = " (HTML 신호 기준, 실제 이미지 미검증)"
    if ti == 0:
        return "수집된 이미지 없음 — 렌더 여부 확인, 핵심 비교 제외." + cav
    if (allc.get("ALT") or 100) < 30:
        return "설명형 ALT 비율 낮음 — ALT에 제품명·핵심 기능 반영." + cav
    if (allc.get("다양성") or 100) < 20:
        return "제품 단독컷 위주 — 사용 장면 이미지 추가." + cav
    if (allc.get("ALT") or 100) < 70:
        return "설명형 ALT 비율 중간 — ALT 품질을 페이지 전반으로 확대." + cav
    return "이미지 신호 양호 — 현 구성 유지." + cav


def filename(prefix: str, ext: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

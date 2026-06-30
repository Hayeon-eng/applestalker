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
SITE_KO = {"apple": "경쟁사 · Apple", "samsung": "당사 · Samsung"}
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


def build_pptx(changes: List[Dict[str, Any]], title: str = "", timestamp: str = "",
               summary: str = "", dcv: Dict[str, Any] | None = None) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
    INK = RGBColor(0x11, 0x13, 0x18); GRAY = RGBColor(0x6B, 0x72, 0x80)
    LVC = {"High": RGBColor(0xFF, 0x3B, 0x30), "Medium": RGBColor(0xFF, 0x9F, 0x0A), "Low": RGBColor(0x34, 0xC7, 0x59)}
    BUCKET_COLOR = {"DATA": RGBColor(0x0A, 0x66, 0xE0), "COPY": RGBColor(0x8E, 0x44, 0xAD), "VISUAL": RGBColor(0x1A, 0x7F, 0x37)}

    # 표지
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.7), Inches(2.6), Inches(12), Inches(2)); tf = tb.text_frame
    tf.text = "Apple Stalker — 변경점 + 현행 분석"; tf.paragraphs[0].font.size = Pt(36); tf.paragraphs[0].font.bold = True; tf.paragraphs[0].font.color.rgb = INK
    p = tf.add_paragraph(); p.text = timestamp; p.font.size = Pt(16); p.font.color.rgb = GRAY
    if summary:
        p2 = tf.add_paragraph(); p2.text = summary; p2.font.size = Pt(13); p2.font.color.rgb = GRAY

    # 변경점: 슬라이드당 최대 4개
    per = 4
    if not changes:
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        b = sl.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11.7), Inches(1))
        b.text_frame.text = "변경 없음 — 다음 슬라이드부터 DATA/COPY/VISUAL 현행 분석"; b.text_frame.paragraphs[0].font.size = Pt(20)
    for i in range(0, len(changes), per):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        body = sl.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(12.1), Inches(6.6)); bf = body.text_frame; bf.word_wrap = True
        for j, ch in enumerate(changes[i:i + per]):
            head = bf.paragraphs[0] if j == 0 else bf.add_paragraph()
            head.text = f"[{LV_KO.get(ch.get('level'),'')}] {SITE_KO.get(ch.get('site'),'')} · {ch.get('category','')} · {ch.get('field','')}"
            head.font.size = Pt(13); head.font.bold = True
            head.font.color.rgb = LVC.get(ch.get("level"), INK)
            b1 = bf.add_paragraph(); b1.text = f"   이전: {(ch.get('before') or '(예시용 가상/없음)')[:140]}"; b1.font.size = Pt(11); b1.font.color.rgb = GRAY
            b2 = bf.add_paragraph(); b2.text = f"   현재: {(ch.get('after') or '(삭제됨)')[:140]}"; b2.font.size = Pt(11); b2.font.color.rgb = INK
            b3 = bf.add_paragraph(); b3.text = f"   {ch.get('url','')}"; b3.font.size = Pt(9); b3.font.color.rgb = GRAY
            bf.add_paragraph()

    # ── [PHASE3 신규] DATA/COPY/VISUAL 현행 분석 슬라이드 (변화 유무 무관, 항상 생성) ──
    for bucket, label in [("data", "DATA"), ("copy", "COPY"), ("visual", "VISUAL")]:
        rows = _narrative_lines(dcv or {}, bucket)
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        head = sl.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12.1), Inches(0.8))
        head.text_frame.text = f"{label} 영역 — 현행 분석"
        head.text_frame.paragraphs[0].font.size = Pt(24); head.text_frame.paragraphs[0].font.bold = True
        head.text_frame.paragraphs[0].font.color.rgb = BUCKET_COLOR[label]

        body = sl.shapes.add_textbox(Inches(0.6), Inches(1.3), Inches(12.1), Inches(5.8)); bf = body.text_frame; bf.word_wrap = True
        if not rows:
            bf.text = "이 영역에 대한 분석 데이터가 없습니다 (크롤이 1회 이상 완료되어야 표시됩니다)"
            bf.paragraphs[0].font.size = Pt(13); bf.paragraphs[0].font.color.rgb = GRAY
        else:
            cur_site = None
            for k, r in enumerate(rows):
                if r["site"] != cur_site:
                    cur_site = r["site"]
                    sp = bf.paragraphs[0] if k == 0 else bf.add_paragraph()
                    sp.text = cur_site; sp.font.size = Pt(14); sp.font.bold = True; sp.font.color.rgb = INK
                lp = bf.add_paragraph(); lp.text = f"   · {r['line']}"; lp.font.size = Pt(11.5); lp.font.color.rgb = GRAY

    buf = io.BytesIO(); prs.save(buf); return buf.getvalue()


def filename(prefix: str, ext: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

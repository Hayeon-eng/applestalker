"""
export_service.py — 화면(변경점)을 '꾸밈 없이 그대로' Excel/PPT로.
리포트 디자인 없이, 화면에 보이는 변경점 표(이전·현재 원문 포함)를 그대로 박제.
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import Any, Dict, List

COLS = ["사이트", "카테고리", "중요도", "항목", "이전 원문", "현재 원문", "URL"]
SITE_KO = {"apple": "경쟁사 · Apple", "samsung": "당사 · Samsung"}
LV_KO = {"High": "높음", "Medium": "보통", "Low": "낮음"}


def _row(c: Dict[str, Any]) -> List[str]:
    return [
        SITE_KO.get(c.get("site"), c.get("site") or ""),
        c.get("category") or "", LV_KO.get(c.get("level"), c.get("level") or ""),
        c.get("field") or "", c.get("before") or "", c.get("after") or "", c.get("url") or "",
    ]


def build_xlsx(changes: List[Dict[str, Any]], title: str = "", timestamp: str = "") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "변경점"
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
        ws.append(["변경 없음 — 현행 유지"])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def build_pptx(changes: List[Dict[str, Any]], title: str = "", timestamp: str = "",
               summary: str = "") -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
    INK = RGBColor(0x11, 0x13, 0x18); GRAY = RGBColor(0x6B, 0x72, 0x80)
    LVC = {"High": RGBColor(0xFF, 0x3B, 0x30), "Medium": RGBColor(0xFF, 0x9F, 0x0A), "Low": RGBColor(0x34, 0xC7, 0x59)}

    # 표지
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.7), Inches(2.6), Inches(12), Inches(2)); tf = tb.text_frame
    tf.text = "Apple Stalker — 변경점"; tf.paragraphs[0].font.size = Pt(40); tf.paragraphs[0].font.bold = True; tf.paragraphs[0].font.color.rgb = INK
    p = tf.add_paragraph(); p.text = timestamp; p.font.size = Pt(16); p.font.color.rgb = GRAY
    if summary:
        p2 = tf.add_paragraph(); p2.text = summary; p2.font.size = Pt(13); p2.font.color.rgb = GRAY

    # 변경점: 슬라이드당 최대 5개, 사이트·중요도·항목 + 이전/현재 원문
    per = 4
    if not changes:
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        b = sl.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11.7), Inches(1))
        b.text_frame.text = "변경 없음 — 현행 유지"; b.text_frame.paragraphs[0].font.size = Pt(20)
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
    buf = io.BytesIO(); prs.save(buf); return buf.getvalue()


def filename(prefix: str, ext: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

"""
Export Service — Excel(.xlsx) / PPTX 다운로드 (사용자 요청)
================================================================
용도:
  - DB 데이터(크롤 이력/변화/스냅샷)를 사용자가 직접 내려받아 관리/아카이브
  - 변화 리포트를 PPTX 로 보고용 생성
  - 스크린샷은 영구저장 안 하지만, 크롤 직후 메모리에 있는 bytes 를
    "일회성" PNG 다운로드로 제공 (export_screenshot_png)

의존성: openpyxl, python-pptx, Pillow (requirements 에 추가)
반환: 생성된 파일의 bytes + 파일명 (FastAPI 에서 StreamingResponse 로 전송)
"""

from __future__ import annotations
import io
from datetime import datetime
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────
# Excel
# ──────────────────────────────────────────────────────────────

def build_xlsx(
    crawl_runs: List[Dict[str, Any]],
    changes: List[Dict[str, Any]],
    pages: List[Dict[str, Any]],
) -> bytes:
    """크롤 이력 + 변화 + 페이지 스냅샷을 3개 시트로. DB 백업/분석용."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="111318")
    head_font = Font(color="FFFFFF", bold=True, size=10)

    def _sheet(ws, headers, rows):
        for c, h in enumerate(headers, 1):
            cell = ws.cell(1, c, h)
            cell.fill = head_fill
            cell.font = head_font
            cell.alignment = Alignment(vertical="center")
        for r, row in enumerate(rows, 2):
            for c, val in enumerate(row, 1):
                ws.cell(r, c, val)
        for c in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(c)].width = 22
        ws.freeze_panes = "A2"

    ws1 = wb.active
    ws1.title = "Crawl Runs"
    _sheet(ws1,
           ["run_id", "site", "started_at", "status", "urls_crawled", "changes"],
           [[r.get("crawl_run_id"), r.get("site_name"), r.get("started_at"),
             r.get("status"), r.get("total_urls_crawled"),
             r.get("total_changes_detected")] for r in crawl_runs])

    ws2 = wb.create_sheet("Changes")
    _sheet(ws2,
           ["url", "level", "type", "field", "summary", "before", "after", "detected_at"],
           [[c.get("url"), c.get("severity_level") or c.get("severity"),
             c.get("change_type"), c.get("field_name"), c.get("summary") or "",
             (c.get("before_value") or "")[:300], (c.get("after_value") or "")[:300],
             c.get("detected_at")] for c in changes])

    ws3 = wb.create_sheet("Page Snapshots")
    _sheet(ws3,
           ["url", "title", "h1", "word_count", "faq_count", "schema_types", "crawled_at"],
           [[p.get("url"), p.get("title"), p.get("h1"), p.get("word_count"),
             len(p.get("faqs") or []),
             ", ".join(p.get("schema_types") or []), p.get("crawled_at")]
            for p in pages])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────
# PPTX
# ──────────────────────────────────────────────────────────────

def build_pptx(report: Dict[str, Any]) -> bytes:
    """변화 리포트 → 보고용 슬라이드. report 는 main.py 의 latest-report 형식."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    INK = RGBColor(0x11, 0x13, 0x18)
    GRAY = RGBColor(0x6B, 0x72, 0x80)

    def _title_slide():
        s = prs.slides.add_slide(prs.slide_layouts[6])
        tb = s.shapes.add_textbox(Inches(0.7), Inches(2.4), Inches(12), Inches(2))
        tf = tb.text_frame
        tf.text = "Apple Stalker Report"
        tf.paragraphs[0].font.size = Pt(40)
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].font.color.rgb = INK
        p = tf.add_paragraph()
        p.text = f"{report.get('site_name','')} · {report.get('timestamp','')}"
        p.font.size = Pt(16)
        p.font.color.rgb = GRAY
        return s

    def _bullets_slide(title: str, bullets: List[str]):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        t = s.shapes.add_textbox(Inches(0.7), Inches(0.5), Inches(12), Inches(0.9))
        t.text_frame.text = title
        t.text_frame.paragraphs[0].font.size = Pt(26)
        t.text_frame.paragraphs[0].font.bold = True
        t.text_frame.paragraphs[0].font.color.rgb = INK
        body = s.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(11.7), Inches(5.4))
        bf = body.text_frame
        bf.word_wrap = True
        for i, b in enumerate(bullets or ["데이터 없음"]):
            p = bf.paragraphs[0] if i == 0 else bf.add_paragraph()
            p.text = f"• {b}"
            p.font.size = Pt(14)
            p.font.color.rgb = INK
            p.space_after = Pt(8)
        return s

    analysis = report.get("analysis") or {}
    _title_slide()
    _bullets_slide("핵심 요약", [
        analysis.get("change_summary", ""),
        analysis.get("samsung_comparison", ""),
    ])
    _bullets_slide("인사이트 (근거기반)",
                   [i if isinstance(i, str) else i.get("point", "")
                    for i in (analysis.get("insights") or [])][:7])
    _bullets_slide("권장 액션 (당사)",
                   [a if isinstance(a, str) else a.get("action", "")
                    for a in (analysis.get("action_items") or [])][:6])

    changes = report.get("data_changes") or []
    if changes:
        _bullets_slide("감지된 변화 Top",
                       [f"[{c.get('severity') or c.get('severity_level')}] {c.get('url')}"
                        for c in changes[:10]])

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────
# 일회성 스크린샷 PNG (DB 저장 X — 크롤 직후 메모리 bytes 만 전달)
# ──────────────────────────────────────────────────────────────

def export_screenshot_png(png_bytes: Optional[bytes]) -> Optional[bytes]:
    """크롤 시점에 잡아둔 PNG bytes 를 그대로 반환 (검증만)."""
    if not png_bytes:
        return None
    try:
        from PIL import Image
        Image.open(io.BytesIO(png_bytes)).verify()
        return png_bytes
    except Exception:
        return None


def filename(prefix: str, ext: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

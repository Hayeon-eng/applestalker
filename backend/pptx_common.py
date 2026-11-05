"""
pptx_common.py — 세 도구(appleStalker·큐비·honeyComb) 공통 PPT 블록 [2026-11 신규, v2 정리]

v2 원칙(읽는 순서가 보이게):
  요약판 = ① 판정 배지 + 한 줄 헤드라인 → ② 숫자 4개(큰 숫자 + 신호등 점) → ③ 지금 할 일 3장(카드: 제목/한 줄/담당 태그)
          → ④ 어디가 문제인가(순위 막대 5~8줄) → ⑤ 판단 기준(작게)
  상세   = 사이트(국가)별 묶음 띠 + 등급 배지 + "무엇이 / 어떻게" 두 칸. 빽빽한 표는 매트릭스(국가×제품)에만.
도구별 색(accent)만 다르고 자리는 같다.
"""
from __future__ import annotations
import io
from typing import Any, Dict, List, Optional, Sequence

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

INK = RGBColor(0x10, 0x13, 0x18); GRAY = RGBColor(0x66, 0x70, 0x85); LIGHT = RGBColor(0x98, 0xA2, 0xB3)
PANEL = RGBColor(0xF4, 0xF6, 0xF9); LINE = RGBColor(0xE4, 0xE9, 0xF2); WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x1F, 0x9E, 0x5C); MID = RGBColor(0xE0, 0xA0, 0x08); BAD = RGBColor(0xD8, 0x36, 0x2F)
GOOD_BG = RGBColor(0xE7, 0xF6, 0xEC); MID_BG = RGBColor(0xFF, 0xF6, 0xDA); BAD_BG = RGBColor(0xFB, 0xE7, 0xE6); NONE_BG = RGBColor(0xEE, 0xF1, 0xF6)
TIER_COLOR = {"good": GOOD, "mid": MID, "bad": BAD, "none": LIGHT, "": INK}
TIER_BG = {"good": GOOD_BG, "mid": MID_BG, "bad": BAD_BG, "none": NONE_BG, "": PANEL}
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FONT = "Malgun Gothic"


def tier_of(v: Optional[float], good: float = 70, mid: float = 40) -> str:
    if v is None:
        return "none"
    return "good" if v >= good else "mid" if v >= mid else "bad"


def new_deck() -> Presentation:
    prs = Presentation(); prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    return prs


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill=PANEL, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(0.75)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, s: str, size=12, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT):
    tb = slide.shapes.add_textbox(x, y, w, h); tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.02); tf.vertical_anchor = anchor
    for i, ln in enumerate((s or "").split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name = font
    return tb


def pill(slide, x, y, label: str, tier: str = "", w=None, size=10):
    w = w or Inches(0.22 + 0.11 * max(2, len(label)))
    rect(slide, x, y, w, Inches(0.3), fill=TIER_BG.get(tier, PANEL), radius=0.5)
    text(slide, x, y, w, Inches(0.3), label, size=size, bold=True, color=TIER_COLOR.get(tier, INK), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w


def _fit(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def header(slide, title: str, subtitle: str = "", accent: RGBColor = INK, tag: str = ""):
    rect(slide, 0, 0, SLIDE_W, Inches(0.1), fill=accent, shape=MSO_SHAPE.RECTANGLE)
    x = Inches(0.6)
    if tag:
        rect(slide, x, Inches(0.42), Inches(1.3), Inches(0.34), fill=accent, radius=0.3)
        text(slide, x, Inches(0.42), Inches(1.3), Inches(0.34), tag, size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        x += Inches(1.45)
    text(slide, x, Inches(0.32), Inches(10), Inches(0.5), title, size=22, bold=True)
    if subtitle:
        text(slide, x, Inches(0.8), Inches(11), Inches(0.35), subtitle, size=11, color=GRAY)


def cover(prs, title: str, subtitle: str, date: str, accent: RGBColor, footnote: str = ""):
    s = _blank(prs)
    rect(s, 0, 0, SLIDE_W, SLIDE_H, fill=WHITE, shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, 0, Inches(0.35), SLIDE_H, fill=accent, shape=MSO_SHAPE.RECTANGLE)
    text(s, Inches(1.0), Inches(2.3), Inches(11), Inches(1.0), title, size=36, bold=True)
    text(s, Inches(1.0), Inches(3.3), Inches(11), Inches(0.6), subtitle, size=16, color=GRAY)
    text(s, Inches(1.0), Inches(4.0), Inches(11), Inches(0.4), date, size=13, color=LIGHT)
    if footnote:
        text(s, Inches(1.0), Inches(6.6), Inches(11.5), Inches(0.5), footnote, size=10, color=LIGHT)
    return s


# ── 요약판 v2 ─────────────────────────────────────────────────────────
def summary_slide(prs, accent: RGBColor, title: str, subtitle: str, headline: str, verdict: Dict[str, Any],
                  kpis: Sequence[Dict[str, Any]], actions: Sequence[Dict[str, Any]], ranking: Dict[str, Any],
                  basis: str = "", conclusion: str = ""):
    """
    verdict : {"label": "수정 필요", "tier": "bad"}
    kpis    : [{label, value, sub, tier}] 최대 4
    actions : [{title, detail, tag, tier}] 최대 3 (+ 나머지 수는 '외 N건')
    ranking : {"title": "어디가 문제인가", "rows": [{name, status, tier, value, bar}], "note": ""}  bar=0~100
    """
    s = _blank(prs)
    header(s, title, subtitle, accent, tag="요약판")
    # ① 판정 + 헤드라인
    vt = verdict.get("tier", "")
    rect(s, Inches(0.6), Inches(1.3), Inches(12.1), Inches(0.75), fill=TIER_BG.get(vt, PANEL))
    rect(s, Inches(0.6), Inches(1.3), Inches(0.12), Inches(0.75), fill=TIER_COLOR.get(vt, INK), shape=MSO_SHAPE.RECTANGLE)
    text(s, Inches(0.9), Inches(1.33), Inches(2.1), Inches(0.7), verdict.get("label", ""), size=20, bold=True, color=TIER_COLOR.get(vt, INK), anchor=MSO_ANCHOR.MIDDLE)
    body = _fit(headline, 60) + (("\n" + _fit(conclusion, 95)) if conclusion else "")
    text(s, Inches(3.0), Inches(1.33), Inches(9.6), Inches(0.7), body, size=13 if conclusion else 16, bold=not conclusion, anchor=MSO_ANCHOR.MIDDLE)
    # ② 숫자 4개
    text(s, Inches(0.6), Inches(2.25), Inches(4), Inches(0.3), "숫자로 보는 현황", size=11, bold=True, color=GRAY)
    kx, ky, kw, kh, gap = Inches(0.6), Inches(2.55), Inches(1.95), Inches(1.15), Inches(0.12)
    for i, k in enumerate(list(kpis)[:4]):
        cx = kx + i * (kw + gap)
        rect(s, cx, ky, kw, kh, fill=WHITE, line=LINE)
        col = TIER_COLOR.get(k.get("tier") or "", INK)
        rect(s, cx + Inches(0.12), ky + Inches(0.14), Inches(0.14), Inches(0.14), fill=col, shape=MSO_SHAPE.OVAL)
        text(s, cx + Inches(0.3), ky + Inches(0.07), kw - Inches(0.35), Inches(0.28), _fit(k.get("label", ""), 18), size=9.5, color=GRAY)
        text(s, cx + Inches(0.1), ky + Inches(0.33), kw - Inches(0.2), Inches(0.52), str(k.get("value", "-")), size=24, bold=True, color=col)
        text(s, cx + Inches(0.1), ky + Inches(0.84), kw - Inches(0.2), Inches(0.28), _fit(k.get("sub", ""), 26), size=8.5, color=LIGHT)
    # ③ 할 일 3장
    ax, ay, aw = Inches(0.6), Inches(3.9), Inches(8.15)
    rest = max(0, len(actions) - 3)
    text(s, ax, ay, aw, Inches(0.3), "지금 할 일" + (f"  (외 {rest}건은 상세 참조)" if rest else ""), size=11, bold=True, color=GRAY)
    cy = ay + Inches(0.32); ch = Inches(0.82)
    for i, a in enumerate(list(actions)[:3]):
        rect(s, ax, cy, aw, ch, fill=WHITE, line=LINE)
        rect(s, ax, cy, Inches(0.5), ch, fill=accent, shape=MSO_SHAPE.RECTANGLE)
        text(s, ax, cy, Inches(0.5), ch, str(i + 1), size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, ax + Inches(0.62), cy + Inches(0.06), aw - Inches(2.2), Inches(0.36), _fit(a.get("title", ""), 52), size=12.5, bold=True)
        text(s, ax + Inches(0.62), cy + Inches(0.42), aw - Inches(0.8), Inches(0.36), _fit(a.get("detail", ""), 95), size=10, color=GRAY)
        if a.get("tag"):
            pill(s, ax + aw - Inches(1.45), cy + Inches(0.1), _fit(a["tag"], 8), a.get("tier", ""), w=Inches(1.3), size=9)
        cy += ch + Inches(0.1)
    if not actions:
        text(s, ax, cy, aw, Inches(0.5), "— 지금 할 일 없음 (현 상태 유지)", size=12, color=GRAY)
    # ④ 어디가 문제인가 (순위 막대)
    rx, ry, rw = Inches(9.0), Inches(2.25), Inches(3.7)
    text(s, rx, ry, rw, Inches(0.3), ranking.get("title", "어디가 문제인가"), size=11, bold=True, color=GRAY)
    rows = list(ranking.get("rows", []))[:8]
    rect(s, rx, ry + Inches(0.32), rw, Inches(4.0), fill=WHITE, line=LINE)
    yy = ry + Inches(0.42)
    for r in rows:
        t = r.get("tier", "")
        rect(s, rx + Inches(0.12), yy + Inches(0.07), Inches(0.12), Inches(0.12), fill=TIER_COLOR.get(t, LIGHT), shape=MSO_SHAPE.OVAL)
        text(s, rx + Inches(0.3), yy, Inches(1.3), Inches(0.26), _fit(r.get("name", ""), 13), size=10.5, bold=True)
        text(s, rx + Inches(1.6), yy, Inches(0.85), Inches(0.26), _fit(r.get("status", ""), 7), size=9, color=TIER_COLOR.get(t, GRAY), bold=True)
        text(s, rx + Inches(2.4), yy, Inches(1.2), Inches(0.26), _fit(str(r.get("value", "")), 16), size=9, color=INK, align=PP_ALIGN.RIGHT)
        bar = r.get("bar")
        if bar is not None:
            rect(s, rx + Inches(0.3), yy + Inches(0.3), Inches(3.3), Inches(0.07), fill=PANEL, shape=MSO_SHAPE.RECTANGLE)
            rect(s, rx + Inches(0.3), yy + Inches(0.3), int(Inches(3.3) * max(0, min(100, bar)) / 100) or Inches(0.02), Inches(0.07), fill=TIER_COLOR.get(t, LIGHT), shape=MSO_SHAPE.RECTANGLE)
        yy += Inches(0.47)
    if not rows:
        text(s, rx + Inches(0.2), yy, rw - Inches(0.4), Inches(0.5), "— 해당 없음", size=11, color=GRAY)
    if ranking.get("note"):
        text(s, rx, Inches(6.6), rw, Inches(0.3), _fit(ranking["note"], 60), size=8.5, color=LIGHT)
    # ⑤ 판단 기준
    if basis:
        text(s, Inches(0.6), Inches(6.95), Inches(12.1), Inches(0.4), _fit(basis, 170), size=8.5, color=LIGHT)
    return s


# ── 상세: 묶음 띠 + 등급 배지 ─────────────────────────────────────────
def issue_slide(prs, accent: RGBColor, title: str, lead: str, groups: Sequence[Dict[str, Any]], tag: str = "상세",
                col_titles=("항목", "무엇이", "어떻게"), per_slide: int = 9, note: str = ""):
    """
    groups: [{"head": "fr · France", "sub": "오류 2 · 확인 1", "rows": [{"item", "tier", "grade", "what", "how"}]}]
    """
    flat: List[Any] = []
    for g in groups:
        if not g.get("rows"):
            continue
        flat.append(("head", g))
        for r in g["rows"]:
            flat.append(("row", r))
    if not flat:
        s = _blank(prs); header(s, title, lead, accent, tag=tag)
        text(s, Inches(0.6), Inches(1.6), Inches(12), Inches(0.5), "— 해당 없음", size=12, color=GRAY)
        return
    pages: List[List[Any]] = []; cur: List[Any] = []; n = 0.0; last_head: Dict[str, Any] = {}
    for kind, obj in flat:
        cost = 0.6 if kind == "head" else 1
        if n + cost > per_slide and cur:
            pages.append(cur); cur = []; n = 0.0
            if kind == "row":
                cur.append(("head", {"head": str(last_head.get("head", "")) + " (계속)", "sub": last_head.get("sub", "")})); n += 0.6
        if kind == "head":
            last_head = obj
        cur.append((kind, obj)); n += cost
    if cur:
        pages.append(cur)
    for pi, page in enumerate(pages, 1):
        s = _blank(prs)
        header(s, title + (f"  ({pi}/{len(pages)})" if len(pages) > 1 else ""), lead, accent, tag=tag)
        x0, y = Inches(0.6), Inches(1.35)
        text(s, x0 + Inches(0.1), y, Inches(2.3), Inches(0.28), col_titles[0], size=9, bold=True, color=LIGHT)
        text(s, x0 + Inches(3.35), y, Inches(4.6), Inches(0.28), col_titles[1], size=9, bold=True, color=LIGHT)
        text(s, x0 + Inches(8.05), y, Inches(4.0), Inches(0.28), col_titles[2], size=9, bold=True, color=LIGHT)
        y += Inches(0.3)
        for kind, obj in page:
            if kind == "head":
                rect(s, x0, y, Inches(12.1), Inches(0.34), fill=PANEL, shape=MSO_SHAPE.RECTANGLE)
                rect(s, x0, y, Inches(0.08), Inches(0.34), fill=accent, shape=MSO_SHAPE.RECTANGLE)
                text(s, x0 + Inches(0.18), y, Inches(6), Inches(0.34), str(obj.get("head", "")), size=11, bold=True, anchor=MSO_ANCHOR.MIDDLE)
                if obj.get("sub"):
                    text(s, x0 + Inches(6.2), y, Inches(5.8), Inches(0.34), str(obj["sub"]), size=9.5, color=GRAY, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
                y += Inches(0.36)
            else:
                r = obj; t = r.get("tier", "")
                rect(s, x0, y + Inches(0.5), Inches(12.1), Pt(0.75), fill=LINE, shape=MSO_SHAPE.RECTANGLE)
                text(s, x0 + Inches(0.1), y + Inches(0.02), Inches(2.3), Inches(0.5), _fit(r.get("item", ""), 34), size=10.5, bold=True, anchor=MSO_ANCHOR.MIDDLE)
                pill(s, x0 + Inches(2.45), y + Inches(0.12), str(r.get("grade", "")), t, w=Inches(0.8), size=9)
                text(s, x0 + Inches(3.35), y + Inches(0.02), Inches(4.6), Inches(0.5), _fit(r.get("what", ""), 110), size=9.5, color=INK, anchor=MSO_ANCHOR.MIDDLE)
                text(s, x0 + Inches(8.05), y + Inches(0.02), Inches(4.0), Inches(0.5), _fit(r.get("how", ""), 95), size=9.5, color=GRAY, anchor=MSO_ANCHOR.MIDDLE)
                y += Inches(0.54)
        if note:
            text(s, Inches(0.6), Inches(6.95), Inches(12.1), Inches(0.4), _fit(note, 170), size=8.5, color=LIGHT)


def table_slide(prs, accent: RGBColor, title: str, subtitle: str, headers: Sequence[str], rows: Sequence[Sequence[Any]],
                col_w: Optional[Sequence[float]] = None, note: str = "", status_col: Optional[int] = None, per_slide: int = 14, tag: str = "상세"):
    """매트릭스(국가×제품 등) 전용 표. status_col=-1 이면 모든 칸을 상태어로 색칠."""
    rows = list(rows)
    pages = [rows[i:i + per_slide] for i in range(0, len(rows), per_slide)] or [[]]
    for pi, chunk in enumerate(pages, 1):
        s = _blank(prs)
        header(s, title + (f"  ({pi}/{len(pages)})" if len(pages) > 1 else ""), subtitle, accent, tag=tag)
        if not chunk:
            text(s, Inches(0.6), Inches(1.6), Inches(12), Inches(0.5), "— 해당 없음", size=12, color=GRAY); continue
        shp = s.shapes.add_table(len(chunk) + 1, len(headers), Inches(0.6), Inches(1.4), Inches(12.1), Inches(0.34) * (len(chunk) + 1))
        tbl = shp.table
        if col_w:
            tot = sum(col_w)
            for i, cw in enumerate(col_w):
                tbl.columns[i].width = int(Inches(12.1) * cw / tot)
        for j, hname in enumerate(headers):
            c = tbl.cell(0, j); c.text = str(hname); c.fill.solid(); c.fill.fore_color.rgb = accent
            p = c.text_frame.paragraphs[0]; p.runs[0].font.size = Pt(10); p.runs[0].font.bold = True; p.runs[0].font.color.rgb = WHITE; p.runs[0].font.name = FONT
        for i, r in enumerate(chunk, 1):
            for j, v in enumerate(r):
                c = tbl.cell(i, j); c.text = "" if v is None else str(v)
                c.fill.solid(); c.fill.fore_color.rgb = WHITE if i % 2 else PANEL
                p = c.text_frame.paragraphs[0]
                if p.runs:
                    p.runs[0].font.size = Pt(10); p.runs[0].font.name = FONT; p.runs[0].font.color.rgb = INK
                    tv = str(v)
                    if status_col is not None and (j == status_col or status_col == -1) and j > 0:
                        if any(k in tv for k in ("미노출", "오류", "낮음", "하위")):
                            c.fill.fore_color.rgb = BAD_BG; p.runs[0].font.color.rgb = BAD; p.runs[0].font.bold = True
                        elif any(k in tv for k in ("상단", "확인", "보통")):
                            c.fill.fore_color.rgb = MID_BG; p.runs[0].font.color.rgb = MID; p.runs[0].font.bold = True
                        elif any(k in tv for k in ("1위", "정상", "양호")):
                            c.fill.fore_color.rgb = GOOD_BG; p.runs[0].font.color.rgb = GOOD; p.runs[0].font.bold = True
        if note:
            text(s, Inches(0.6), Inches(6.95), Inches(12.1), Inches(0.4), _fit(note, 170), size=8.5, color=LIGHT)


def save(prs) -> bytes:
    buf = io.BytesIO(); prs.save(buf); return buf.getvalue()

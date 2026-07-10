"""
spec_extractor.py — 큐비 — Spec QA [V2] Step 2~4
DOM Extraction → Section Detection → Attribute-Value 후보 추출

파이프라인 위치 (설계 철학 문서의 순서 고정):
  Browser Rendering → [DOM Extraction → Section Detection → Attribute Detection] → …

원칙
  · 모든 텍스트를 쓰지 않는다 — Section을 먼저 판정하고, Spec 성격의 label:value 페어만 추출
  · 추출은 3중: <dl>/<table> 구조 페어 → label/value 형제 페어 → 텍스트 윈도우(폴백)
  · 각 페어에 section 태그를 붙여 이후 Validation이 Context를 알 수 있게 한다
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

# Section 판정 키워드 (id/class/heading 텍스트, 대소문자 무시)
_SECTION_KEYWORDS = [
    ("disclaimer", re.compile(r"disclaimer|footnote|fine-?print|legal|terms|sub-disc|cp-disc", re.I)),
    ("buybox",     re.compile(r"buy-?box|purchase|add-to-cart|price-info|bc-price", re.I)),
    ("compare",    re.compile(r"compare|comparison", re.I)),
    ("box",        re.compile(r"in-?the-?box|whats-?in|package-?content", re.I)),
    ("promotion",  re.compile(r"promo|offer|benefit|banner|event", re.I)),
    ("spec",       re.compile(r"spec|specification|tech-?spec|detail-?spec", re.I)),
]
_HEADING_KEYWORDS = [
    ("box",        re.compile(r"what'?s in the box|구성품", re.I)),
    ("spec",       re.compile(r"^specs?$|specifications?|사양|스펙", re.I)),
    ("disclaimer", re.compile(r"disclaimer|legal|각주|고지", re.I)),
]

# MasterSpec의 Page 컬럼 값 → 이 엔진의 section 태그 매핑
PAGE_TO_SECTIONS = {
    "pdp": ("spec", "body", "buybox", "box"),
    "buy box": ("buybox", "spec", "body"),
    "compare": ("compare", "spec", "body"),
    "disclaimer": ("disclaimer",),
    "what's in the box": ("box", "spec", "body"),
}


def _classify(el) -> str:
    """엘리먼트(및 조상)의 id/class/heading으로 section 태그 판정."""
    node = el
    hops = 0
    while node is not None and hops < 8:
        idc = " ".join(filter(None, [node.get("id", "")] + (node.get("class") or []))) if hasattr(node, "get") else ""
        for tag, rx in _SECTION_KEYWORDS:
            if idc and rx.search(idc):
                return tag
        node = getattr(node, "parent", None)
        hops += 1
    return "body"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def extract(html: str) -> Dict[str, Any]:
    """HTML → {"pairs": [...], "sections": {tag: 전체텍스트}}
    pairs: [{"label","value","section","source"}]  source: dl|table|sibling|window
    sections: 폴백 텍스트 윈도우 검색용 섹션별 원문."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.extract()

    pairs: List[Dict[str, str]] = []

    # ① <dl><dt><dd> 구조
    for dl in soup.find_all("dl"):
        sec = _classify(dl)
        dts, dds = dl.find_all("dt"), dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            label, value = _clean(dt.get_text(" ")), _clean(dd.get_text(" "))
            if label and value:
                pairs.append({"label": label, "value": value, "section": sec, "source": "dl"})

    # ② <table> th/td (또는 td 2개) 행
    for table in soup.find_all("table"):
        sec = _classify(table)
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                label, value = _clean(cells[0].get_text(" ")), _clean(cells[1].get_text(" "))
                if label and value and len(label) < 80:
                    pairs.append({"label": label, "value": value, "section": sec, "source": "table"})

    # ③ label/value 형제 페어 — class에 label/name/title vs value/data가 붙는 흔한 패턴
    lab_rx = re.compile(r"label|name|title|key", re.I)
    val_rx = re.compile(r"value|data|desc", re.I)
    for el in soup.find_all(True, class_=lab_rx):
        sib = el.find_next_sibling(True, class_=val_rx)
        if sib is not None:
            label, value = _clean(el.get_text(" ")), _clean(sib.get_text(" "))
            if label and value and len(label) < 80 and len(value) < 200:
                pairs.append({"label": label, "value": value,
                              "section": _classify(el), "source": "sibling"})

    # ④ 섹션별 전체 텍스트(폴백 윈도우 검색용) — heading 기반 재분류 보강
    sections: Dict[str, List[str]] = {}
    for el in soup.find_all(True):
        if el.name in ("html", "head", "body"):
            continue
        # heading 텍스트로 컨테이너 섹션 보정
        if el.name in ("h1", "h2", "h3", "h4"):
            htext = _clean(el.get_text(" "))
            for tag, rx in _HEADING_KEYWORDS:
                if rx.search(htext) and el.parent is not None:
                    el.parent["data-qb-section"] = tag
    for el in soup.find_all(True):
        forced = el.get("data-qb-section") if hasattr(el, "get") else None
        if forced:
            sections.setdefault(forced, []).append(_clean(el.get_text(" ")))
    # 최상위 분류 텍스트
    for tag, rx in _SECTION_KEYWORDS:
        for el in soup.find_all(True, id=rx) + soup.find_all(True, class_=rx):
            sections.setdefault(tag, []).append(_clean(el.get_text(" ")))
    body_text = _clean(soup.get_text(" "))
    sec_text = {k: " … ".join(dict.fromkeys(v)) for k, v in sections.items()}
    sec_text["body"] = body_text
    return {"pairs": pairs, "sections": sec_text}


def window_search(section_text: str, aliases: List[str], span: int = 60) -> List[Tuple[str, str]]:
    """구조 페어가 없을 때의 폴백: 섹션 텍스트에서 alias 뒤 span자 윈도우를 값 후보로.
    ASCII alias는 문자 경계를 적용해 다른 단어 내부 매칭('Weight'⊂'Lightweight')을 막고,
    CJK 등 비ASCII는 붙여쓰기('무게188g')가 정상이므로 평문 검색한다.
    반환: [(matched_alias, window_text)]"""
    out = []
    for alias in aliases:
        if not alias:
            continue
        if alias.isascii():
            pat = re.compile(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", re.I)
        else:
            pat = re.compile(re.escape(alias), re.I)
        for m in pat.finditer(section_text):
            start = m.end()
            out.append((alias, section_text[start:start + span].strip(" :·-—")))
    return out

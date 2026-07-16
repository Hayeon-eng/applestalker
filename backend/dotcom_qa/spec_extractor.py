"""
spec_extractor.py — 큐비 — Spec QA [V2] Step 2~4

DOM Extraction → Section Detection → Attribute-Value 후보 추출

파이프라인 위치 (설계 철학 문서의 순서 고정):
  Browser Rendering → [DOM Extraction → Section Detection → Attribute Detection] → …

원칙
  · 모든 텍스트를 쓰지 않는다 — Section을 먼저 판정하고, Spec 성격의 label:value 페어만 추출
  · 추출은 3중: <dl>/<table> 구조 페어 → label/value 형제 페어 → 텍스트 윈도우(폴백)
  · 각 페어에 section 태그를 붙여 이후 Validation이 Context를 알 수 있게 한다

[2026-07 리팩토링 — Critical Error 오탐/오검출 근본 원인 수정]
  기존 구조의 문제:
    1) Section 판정에 Header/Footer/Nav/Menu/Button/Popup 카테고리가 없어 이런 UI
       텍스트가 전부 "body"(catch-all)로 분류됨.
    2) 폴백 텍스트 윈도우 검색이 페이지 전체를 `soup.get_text(" ")`로 한 줄 문자열로
       평탄화한 뒤 그 위에서 검색 — 서로 다른 컴포넌트(마케팅 카피, 캐러셀 캡션 등)의
       문장이 공백 하나로 이어붙어, alias 뒤 N자를 그냥 잘라내면 완전히 무관한 문장이
       "찾은 값"으로 뒤섞여 들어옴.
       예) Samsung.com 같은 마케팅형 PDP는 <dl>/<table> 스펙 표가 아니라 스펙 수치가
       마케팅 문장 속에 섞여 있는 경우가 많아, 위 문제가 그대로 Critical Error 오탐으로
       이어진다 (JP Galaxy Z Fold7 "解像度" 사례).
    3) 이 "body" catch-all이 Dictionary 후보 생성에도 그대로 재사용되어, nav/footer/
       button/popup 라벨까지 전부 "신규 표현"으로 잡히는 원인이 되었다(별도 요구사항).

  수정:
    · Section 키워드에 header/footer/nav/menu/button/popup 추가, spec류보다 먼저 검사
      (모호한 경우 UI-chrome 우선 배제).
    · 섹션 텍스트를 문자열 하나로 합치지 않고 "블록 리스트"(section_blocks)로 보존한다.
      블록 = 하위에 다른 block-level 태그가 없는 최소 텍스트 단위(p/li/dt/dd/td/th/
      h1-6/span/div/button/a/label 등). 컴포넌트 경계를 유지하므로 alias가 어떤
      블록에서 매칭되면 그 블록 "안"에서만 값을 찾는다 — 다른 컴포넌트 문장이 섞이지
      않는다.
    · window_search: 블록 내부 검색 + 문장 종결부호에서 자르기 + (옵션) 숫자/단위가
      실제로 그 윈도우 안에 있는 경우만 채택. alias 뒤뿐 아니라 앞쪽도 좁게 함께 봐서
      "2184 x 1968 の解像度" 처럼 라벨이 값 뒤에 오는 마케팅 문장형 표기도 포착한다.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

# ── Section 판정 키워드 (id/class/heading 텍스트, 대소문자 무시) ──────────
# UI-chrome(제외 대상)을 스펙류보다 먼저 검사한다 — "spec-menu-btn" 같은 모호한
# class명이 있어도 chrome으로 분류되어 검수/사전 후보 양쪽에서 제외되게 한다.
_SECTION_KEYWORDS = [
    ("header",     re.compile(r"\bheader\b|gnb|global-?nav|site-?header|masthead|top-?bar", re.I)),
    ("footer",     re.compile(r"\bfooter\b|site-?footer|bottom-?bar", re.I)),
    ("nav",        re.compile(r"\bnav\b|navigation|breadcrumb|\block?[-_]?nav\b|side-?menu|tab-?menu|gnb|lnb", re.I)),
    ("menu",       re.compile(r"\bmenu\b|dropdown|option-?menu|context-?menu|select-?box", re.I)),
    ("button",     re.compile(r"\bbtn\b|\bbutton\b|\bcta\b|\blink-?btn\b", re.I)),
    ("popup",      re.compile(r"popup|modal|dialog|tooltip|overlay|layer-?pop", re.I)),
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

# 태그 자체로 UI-chrome이 명확한 경우(클래스명이 없어도 배제)
_TAG_SECTION = {
    "nav": "nav", "header": "header", "footer": "footer",
    "button": "button", "dialog": "popup",
}

# MasterSpec의 Page 컬럼 값 → 이 엔진의 section 태그 매핑 (Validation용 — body 포함)
PAGE_TO_SECTIONS = {
    "pdp": ("spec", "body", "buybox", "box"),
    "buy box": ("buybox", "spec", "body"),
    "compare": ("compare", "spec", "body"),
    "disclaimer": ("disclaimer",),
    "what's in the box": ("box", "spec", "body"),
}

# Dictionary(신규 표현) 후보를 생성해도 되는 section — Attribute/Value 스펙 영역만.
# body(마케팅 카피 등 catch-all)·disclaimer·promotion과 모든 UI-chrome은 제외.
SPEC_LIKE_SECTIONS = {"spec", "compare", "buybox", "box"}

# UI-chrome으로 분류된 section — 후보 생성뿐 아니라 항상 검수 대상에서도 제외
CHROME_SECTIONS = {"header", "footer", "nav", "menu", "button", "popup"}

# 블록 경계로 취급하는(하위에 있으면 leaf가 아님) block-level 태그
_BLOCK_TAGS = ("p", "li", "div", "dt", "dd", "td", "th",
               "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "section", "article")
_LEAF_CANDIDATE_TAGS = ("p", "li", "dt", "dd", "td", "th",
                        "h1", "h2", "h3", "h4", "h5", "h6",
                        "span", "div", "a", "button", "label")

_SENTENCE_END = re.compile(r"(?<!\d)[。.!?！？](?!\d)")


def _classify(el) -> str:
    """엘리먼트(및 조상)의 태그명/id/class/heading으로 section 태그 판정."""
    node = el
    hops = 0
    while node is not None and hops < 8:
        name = getattr(node, "name", None)
        if name in _TAG_SECTION:
            return _TAG_SECTION[name]
        idc = " ".join(filter(None, [node.get("id", "")] + (node.get("class") or []))) if hasattr(node, "get") else ""
        for tag, rx in _SECTION_KEYWORDS:
            if idc and rx.search(idc):
                return tag
        node = getattr(node, "parent", None)
        hops += 1
    return "body"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _is_leaf_block(tag) -> bool:
    """하위에 다른 block-level 태그가 없으면 leaf 텍스트 블록으로 취급."""
    return tag.find(_BLOCK_TAGS) is None


def extract(html: str) -> Dict[str, Any]:
    """HTML → {"pairs": [...], "sections": {tag: 전체텍스트}, "section_blocks": {tag: [블록,...]}}
    pairs: [{"label","value","section","source"}]  source: dl|table|sibling
    section_blocks: 컴포넌트 경계를 보존한 블록 리스트(window_search가 여기서만 검색)
    sections: section_blocks를 이어붙인 텍스트(exists/option_match 등 '포함 여부' 검사용)"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.extract()

    pairs: List[Dict[str, str]] = []

    # ⓪ [2026-07 신규] data-속성 기반 값 — 화면엔 아이콘만 있고 실제 스펙 숫자는
    #    data-spec-value 같은 속성 안에만 있는 구조(예: Samsung Compare 위젯의
    #    <p data-spec-type="keyweightsize-2" data-spec-value="218">).
    #    렌더링/스크롤/동의모달을 아무리 고쳐도 텍스트 기반 추출(①~③)로는 절대 못 잡는
    #    영역이라 별도 tier로 추가한다. data-spec-type 끝의 "-N"은 비교 대상 제품의
    #    열 순서(product_hint)로 쓴다(Compare 표의 컬럼별 값 구분과 동일한 목적).
    _DATA_IDX_RX = re.compile(r"^(.*?)-(\d+)$")
    for el in soup.find_all(attrs={"data-spec-value": True}):
        raw_val = _clean(el.get("data-spec-value", ""))
        raw_type = _clean(el.get("data-spec-type", "") or el.get("data-spec-key", ""))
        if not raw_val or not raw_type:
            continue
        m = _DATA_IDX_RX.match(raw_type)
        spec_key, col_idx = (m.group(1), m.group(2)) if m else (raw_type, None)
        # 사람이 읽는 라벨 후보 — aria-label/자체 라벨 속성 → 형제 아이콘의 alt → 안되면 slug 그대로
        label = _clean(el.get("aria-label") or el.get("data-spec-label") or "")
        if not label:
            img = el.find("img")
            if img is None:
                img = el.find_previous("img")
            if img is not None:
                label = _clean(img.get("alt", ""))
        if not label:
            label = spec_key
        pair = {"label": label, "value": raw_val, "section": _classify(el), "source": "data-attr"}
        if col_idx:
            pair["product_hint"] = col_idx
        pairs.append(pair)

    # ① <dl><dt><dd> 구조
    for dl in soup.find_all("dl"):
        sec = _classify(dl)
        dts, dds = dl.find_all("dt"), dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            label, value = _clean(dt.get_text(" ")), _clean(dd.get_text(" "))
            if label and value:
                pairs.append({"label": label, "value": value, "section": sec, "source": "dl"})

    # ② <table> th/td (또는 td 2개) 행
    #    [V3] Compare형 표(값 컬럼 2개 이상 + 헤더 행) 지원 — 각 값 셀에 소속 컬럼의
    #    헤더 텍스트를 product_hint로 붙여, 엔진이 "이 값이 어느 제품 것인지"를 알 수
    #    있게 한다(이웃 제품 컬럼 값을 검수 대상 제품 값으로 오인하는 문제 방지).
    for table in soup.find_all("table"):
        sec = _classify(table)
        rows_ = table.find_all("tr")
        header_cells: List[str] = []
        if rows_:
            first = rows_[0].find_all(["th", "td"])
            if len(first) >= 3 or (first and first[0].name == "th" and len(first) >= 2):
                header_cells = [_clean(c.get_text(" ")) for c in first]
        for ri, tr in enumerate(rows_):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = _clean(cells[0].get_text(" "))
            if not label or len(label) >= 80:
                continue
            if header_cells and ri == 0:
                continue  # 헤더 행 자체는 페어가 아니다
            if header_cells and len(cells) >= 3:
                # 다중 값 컬럼(Compare) — 컬럼별 페어 + product_hint
                for ci in range(1, len(cells)):
                    value = _clean(cells[ci].get_text(" "))
                    hint = header_cells[ci] if ci < len(header_cells) else ""
                    if value:
                        pairs.append({"label": label, "value": value, "section": sec,
                                      "source": "table", "product_hint": hint})
            else:
                value = _clean(cells[1].get_text(" "))
                if value:
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

    # ④ heading 텍스트로 컨테이너 섹션 보정(스펙/구성품/각주 등)
    for el in soup.find_all(("h1", "h2", "h3", "h4")):
        htext = _clean(el.get_text(" "))
        for tag, rx in _HEADING_KEYWORDS:
            if rx.search(htext) and el.parent is not None:
                el.parent["data-qb-section"] = tag

    # ⑤ 섹션별 "블록 리스트" — 컴포넌트 경계를 보존한 폴백 검색용 원문
    #    (기존처럼 페이지 전체를 한 문자열로 평탄화하지 않는다 — 이게 오탐의 근본 원인이었다)
    section_blocks: Dict[str, List[str]] = {}
    last_seen: Dict[str, str] = {}
    for el in soup.find_all(_LEAF_CANDIDATE_TAGS):
        if not _is_leaf_block(el):
            continue
        text = _clean(el.get_text(" "))
        if not text:
            continue
        forced = None
        node = el
        hops = 0
        while node is not None and hops < 4:
            f = node.get("data-qb-section") if hasattr(node, "get") else None
            if f:
                forced = f
                break
            node = getattr(node, "parent", None)
            hops += 1
        sec = forced or _classify(el)
        # 크롤러가 같은 노드를 중첩 순회해 만드는 연속 중복만 제거(전역 dedup은 하지 않음
        # — 같은 문구가 서로 다른 스펙 항목에 정당하게 반복될 수 있으므로)
        if last_seen.get(sec) == text:
            continue
        last_seen[sec] = text
        section_blocks.setdefault(sec, []).append(text)

    sections = {tag: " … ".join(blocks) for tag, blocks in section_blocks.items()}
    return {"pairs": pairs, "sections": sections, "section_blocks": section_blocks}


def window_search(blocks: List[str], aliases: List[str], span: int = 70,
                  require_digit: bool = False) -> List[Tuple[str, str]]:
    """구조 페어가 없을 때의 폴백: '같은 블록 안'에서만 alias 주변 윈도우를 값 후보로 삼는다.
    (문자열 하나로 평탄화된 페이지 전체가 아니라 블록 리스트를 받는다 — 서로 다른
    컴포넌트의 문장이 섞여 엉뚱한 값이 매칭되는 문제를 원천 차단)

    · ASCII alias는 문자 경계를 적용해 다른 단어 내부 매칭('Weight'⊂'Lightweight')을 막고,
      CJK 등 비ASCII는 붙여쓰기('무게188g')가 정상이므로 평문 검색한다.
    · alias 뒤쪽뿐 아니라 앞쪽 좁은 구간도 함께 후보로 본다 — "2184 x 1968 の解像度"처럼
      마케팅 문장에서 라벨이 값 뒤에 오는 경우도 포착.
    · 문장 종결부호(。.!?！？)에서 잘라 다음 문장으로 안 넘어가게 한다.
    · require_digit=True면 윈도우 안에 숫자가 실제로 있는 경우만 채택
      (숫자형 스펙에 마케팅 카피 문장이 값으로 오인되는 것을 방지).
    반환: [(matched_alias, window_text)] — 같은 블록·같은 alias 기준 앞쪽보다 뒤쪽을 우선."""
    out: List[Tuple[str, str]] = []
    for block in blocks:
        if not block:
            continue
        for alias in aliases:
            if not alias:
                continue
            if alias.isascii():
                pat = re.compile(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", re.I)
            else:
                pat = re.compile(re.escape(alias), re.I)
            for m in pat.finditer(block):
                # 뒤쪽 우선
                tail = block[m.end():m.end() + span]
                cut = _SENTENCE_END.search(tail)
                if cut:
                    tail = tail[:cut.end()]
                tail = tail.strip(" :·-—")
                if tail and (not require_digit or re.search(r"\d", tail)):
                    out.append((alias, tail))
                    continue
                # 뒤쪽에서 못 찾으면 앞쪽 좁은 구간도 시도
                head_start = max(0, m.start() - span // 2)
                head = block[head_start:m.start()]
                cut2 = list(_SENTENCE_END.finditer(head))
                if cut2:
                    head = head[cut2[-1].end():]
                head = head.strip(" :·-—")
                if head and (not require_digit or re.search(r"\d", head)):
                    out.append((alias, head))
    return out

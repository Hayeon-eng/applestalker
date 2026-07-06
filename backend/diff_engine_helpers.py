"""
Diff Engine helpers — shared types/normalizers/structure/image utilities
================================================================
요구사항 3,4,5,8 을 한 곳에서 구현.

이벤트 단위 출력: detect() 는 ChangeEvent 리스트를 반환한다.
각 이벤트는 "무엇이 / 어디서 / 어느 수준(L0~L5)으로 / 왜" 바뀌었는지 담는다.

3단계 diff:
  - character-level  : difflib ratio + 실제 추가/삭제 문자수
  - token/sentence   : 단어·문장 단위 added/removed (의미 단위)
  - DOM/structure    : 태그 구조 지문(fingerprint) 비교 (레이아웃 변화)

이미지: Playwright 스크린샷의 perceptual hash(aHash) 만 비교.
        (이미지 파일은 저장 안 함 — 500MB DB 제약. hash 만 DB 보관)

severity L0~L5:
  L0 pixel/char     : 1~2글자, 공백, 해시 미세차
  L1 word           : 단어 1~몇 개 교체
  L2 sentence       : 문장/문구 단위
  L3 section        : 섹션(H2/H3 블록, FAQ, 다수 문단)
  L4 structural     : DOM 구조/내비/스키마 타입 변화
  L5 business-critical: 가격/CTA/품절/사전예약 등 커머스 키워드 관련
"""

from __future__ import annotations
import difflib
import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlsplit, urlunsplit
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────
# Severity
# ──────────────────────────────────────────────────────────────

SEVERITY_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5"]
SEVERITY_LABEL = {
    "L0": "미세(pixel/char)", "L1": "단어", "L2": "문장/문구",
    "L3": "섹션", "L4": "구조", "L5": "비즈니스 임팩트",
}
# 기존 critical/high/medium/low 와의 호환 매핑 (DB·이메일·UI 하위호환)
SEVERITY_TO_LEGACY = {
    "L0": "low", "L1": "low", "L2": "medium",
    "L3": "high", "L4": "high", "L5": "critical",
}


@dataclass
class ChangeEvent:
    url: str
    site_key: str
    tier_level: int
    field_name: str                 # h1 / title / body / cta / schema_type / dom / image ...
    change_type: str                # content / navigation / commerce / technical / visual
    severity_level: str             # L0~L5
    severity_legacy: str            # low/medium/high/critical (호환)
    summary: str                    # 사람이 읽는 한 줄 (사실 기반, AI 아님)
    before_value: Optional[str] = None
    after_value: Optional[str] = None
    # 정량 지표 (UI/필터/AI 근거용)
    char_added: int = 0
    char_removed: int = 0
    diff_ratio: float = 0.0         # 0(동일)~1(완전 상이)
    evidence: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["detected_at"] = self.detected_at.isoformat()
        return d


def _s(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _sentences(text: str) -> List[str]:
    text = _s(text)
    parts = re.split(r"(?<=[.!?。！？\n])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _tokens(text: str) -> List[str]:
    return re.findall(r"\w+", _s(text).lower())


# ──────────────────────────────────────────────────────────────
# Character / Token / Sentence diff
# ──────────────────────────────────────────────────────────────

def char_diff(before: str, after: str) -> Dict[str, Any]:
    before, after = _s(before), _s(after)
    sm = difflib.SequenceMatcher(None, before, after)
    ratio = 1.0 - sm.ratio()
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            added += (j2 - j1)
        if tag in ("replace", "delete"):
            removed += (i2 - i1)
    return {"diff_ratio": round(ratio, 4), "char_added": added, "char_removed": removed}


def token_sentence_diff(before: str, after: str) -> Dict[str, Any]:
    b_sent, a_sent = set(_sentences(before)), set(_sentences(after))
    b_tok, a_tok = set(_tokens(before)), set(_tokens(after))
    return {
        "sentences_added": sorted(a_sent - b_sent)[:20],
        "sentences_removed": sorted(b_sent - a_sent)[:20],
        "words_added": sorted(a_tok - b_tok)[:50],
        "words_removed": sorted(b_tok - a_tok)[:50],
    }



# ──────────────────────────────────────────────────────────────
# 안정화 유틸: 크롤 때마다 바뀌는 타임스탬프/쿼리/추적 요소 노이즈 축소
# ──────────────────────────────────────────────────────────────

_VOLATILE_TEXT_PATTERNS = [
    re.compile(r"\b\d{4}[-./]\d{1,2}[-./]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?\b"),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s?(?:AM|PM|KST|UTC)?\b", re.IGNORECASE),
    re.compile(r"\b(?:last updated|updated at|as of|generated at)\b[^.。\n]{0,80}", re.IGNORECASE),
]


def stable_text(text: str) -> str:
    """비교용 텍스트 정규화. 가격/스펙 숫자는 보존하고 명백한 수집시각류만 제거한다."""
    out = _s(text).replace("\u200b", " ").replace("\xa0", " ")
    for pat in _VOLATILE_TEXT_PATTERNS:
        out = pat.sub(" ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _short_list_delta(before: List[str], after: List[str], limit: int = 5) -> Dict[str, List[str]]:
    b, a = list(before or []), list(after or [])
    bset, aset = set(b), set(a)
    return {
        "added": sorted(aset - bset)[:limit],
        "removed": sorted(bset - aset)[:limit],
    }


def _tag_count_delta(prev_counts: Dict[str, int], cur_counts: Dict[str, int], limit: int = 12) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    keys = sorted(set(prev_counts or {}) | set(cur_counts or {}))
    for k in keys:
        b, a = int((prev_counts or {}).get(k, 0)), int((cur_counts or {}).get(k, 0))
        if b != a:
            out[k] = {"before": b, "after": a, "diff": a - b}
    return dict(list(out.items())[:limit])


def _meaningful_tag_deltas(tag_deltas: Dict[str, Dict[str, int]], limit: int = 8) -> Dict[str, Dict[str, int]]:
    """
    DOM hash는 태그 순서/중첩이 조금만 달라도 바뀐다.
    li/a/button처럼 반복되는 메뉴·푸터·캐러셀 태그 1~2개 차이는
    실제 캠페인/페이지 구조 변경이라기보다 동적 렌더링 노이즈인 경우가 많아 제외한다.
    """
    if not tag_deltas:
        return {}

    core_tags = {
        "main", "section", "article", "aside", "header", "footer", "nav",
        "h1", "h2", "h3", "h4", "h5", "h6", "form", "table", "video",
    }
    visual_tags = {"figure", "picture", "img"}
    repeat_tags = {"li", "a", "button", "ul", "ol"}

    out: Dict[str, Dict[str, int]] = {}
    for tag, delta in tag_deltas.items():
        diff = abs(int((delta or {}).get("diff", 0)))
        if diff <= 0:
            continue
        if tag in core_tags:
            out[tag] = delta
        elif tag in visual_tags and diff >= 3:
            out[tag] = delta
        elif tag in repeat_tags and diff >= 5:
            out[tag] = delta
        elif diff >= 8:
            out[tag] = delta
    return dict(list(out.items())[:limit])


def _dom_severity_level(
    count_deltas: Dict[str, Dict[str, Any]],
    tag_deltas: Dict[str, Dict[str, int]],
    heading_delta: Dict[str, List[str]],
    cta_delta: Dict[str, List[str]],
) -> str:
    if cta_delta.get("added") or cta_delta.get("removed") or "cta_count" in count_deltas:
        return "L3"
    if heading_delta.get("added") or heading_delta.get("removed") or "h2_count" in count_deltas or "h3_count" in count_deltas:
        return "L3"
    if "faq_count" in count_deltas or "img_count" in count_deltas:
        return "L2"
    if any(tag in tag_deltas for tag in ("main", "section", "article", "header", "footer", "nav", "form", "table", "video")):
        return "L2"
    return "L1"



# ──────────────────────────────────────────────────────────────
# 반복 크롤 안정화: 메뉴/푸터/쿠키/추천 영역처럼 매번 달라지는 텍스트 제외
# ──────────────────────────────────────────────────────────────
_COPY_NOISE_RE = re.compile(
    r"(cookie|cookies|privacy|terms|legal|copyright|all rights reserved|"
    r"sign in|login|logout|account|cart|bag|search|menu|breadcrumb|"
    r"recommended|related|recently viewed|compare|support|contact us|"
    r"쿠키|개인정보|약관|저작권|로그인|로그아웃|계정|장바구니|검색|메뉴|"
    r"추천|관련|최근 본|비교하기|고객지원|문의)",
    re.IGNORECASE,
)


def _stable_copy_units(text: str, limit: int = 220) -> List[str]:
    """본문 비교용 단위.

    전체 body 텍스트를 그대로 비교하면 헤더/푸터/추천 링크/쿠키 문구 때문에
    같은 페이지를 연속 크롤해도 변경점이 흔들린다. 캠페인·프로모션·제품 설명처럼
    의미 있는 문장/문구만 안정적으로 남긴다.
    """
    raw = stable_text(text)
    if not raw:
        return []

    # 문장부호가 적은 랜딩 페이지까지 고려해 구분자 단위와 길이 단위 둘 다 사용한다.
    rough = re.split(r"(?<=[.!?。！？])\s+|\s{2,}|\s[•·|]\s", raw)
    units: List[str] = []
    for chunk in rough:
        chunk = re.sub(r"\s+", " ", chunk).strip(" -–—|·•\t\n\r")
        if not chunk:
            continue
        if _COPY_NOISE_RE.search(chunk):
            continue
        words = _tokens(chunk)
        if len(chunk) < 24 and not _is_campaign_copy(chunk):
            continue
        if len(words) <= 3 and not _is_campaign_copy(chunk):
            continue
        if len(chunk) > 360:
            # 긴 덩어리는 같은 문구가 약간만 밀려도 전체가 변경처럼 보이므로 고정 길이로 분할한다.
            for i in range(0, len(chunk), 220):
                sub = chunk[i:i + 260].strip()
                if len(sub) >= 24:
                    units.append(sub)
        else:
            units.append(chunk)

    # 중복 제거하되 순서는 유지한다.
    seen = set()
    out: List[str] = []
    for u in units:
        key = u.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
        if len(out) >= limit:
            break
    return out


def _comparison_text(field_name: str, value: str) -> str:
    if field_name == "body_content":
        return "\n".join(_stable_copy_units(value))
    return stable_text(value)


def _copy_change_is_meaningful(field_name: str, before_cmp: str, after_cmp: str, cd: Dict[str, Any], ts: Dict[str, Any]) -> bool:
    """저장할 만한 카피 변화인지 판단.

    메뉴 탭/짧은 라벨/렌더링 노이즈는 변경점 수를 흔드는 주범이라 제외하고,
    캠페인·프로모션·제품 메시지 변화 또는 충분한 문장 단위 변화만 남긴다.
    """
    if field_name != "body_content":
        return True
    blob = f"{before_cmp} {after_cmp}"
    if _is_campaign_copy(blob):
        return True
    sent_changed = len(ts.get("sentences_added", [])) + len(ts.get("sentences_removed", []))
    word_changed = len(ts.get("words_added", [])) + len(ts.get("words_removed", []))
    total_chars = int(cd.get("char_added", 0)) + int(cd.get("char_removed", 0))
    # 캠페인성이 없는 소폭 본문 흔들림은 반복 크롤 노이즈로 본다.
    if sent_changed <= 2 and word_changed <= 18 and total_chars <= 420:
        return False
    # 비교용 본문 자체가 거의 없으면 안정적으로 판단하기 어렵다.
    if len(after_cmp) < 80 and len(before_cmp) < 80:
        return False
    return True

# ──────────────────────────────────────────────────────────────
# DOM / structure fingerprint
# ──────────────────────────────────────────────────────────────

def dom_fingerprint(html: str) -> str:
    """
    의미 있는 구조 태그만 남긴 DOM 지문.
    광고/스크립트/SVG/path/스타일/트래킹처럼 크롤 때마다 흔들리는 요소는 제외한다.
    """
    html = _s(html)
    structural_tags = {
        "html", "body", "main", "section", "article", "aside", "header", "footer", "nav",
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "a", "button",
        "form", "input", "select", "textarea", "table", "thead", "tbody", "tr", "th", "td",
        "figure", "picture", "img", "video", "source", "details", "summary",
    }
    volatile = {"script", "style", "noscript", "path", "svg", "meta", "link", "template"}
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for node in soup.find_all(list(volatile)):
            node.decompose()
        tokens: List[str] = []
        for el in soup.find_all(True):
            name = (el.name or "").lower()
            if name not in structural_tags:
                continue
            if el.get("aria-hidden") == "true" or "display:none" in _s(el.get("style")).replace(" ", "").lower():
                continue
            depth = len(list(el.parents))
            tokens.append(f"{min(depth, 8)}:{name}")
    except Exception:
        tags = re.findall(r"<\s*([a-zA-Z][a-zA-Z0-9]*)", html)
        tokens = [t.lower() for t in tags if t.lower() in structural_tags and t.lower() not in volatile]
    skeleton = ">".join(tokens)
    return hashlib.sha1(skeleton.encode("utf-8", "ignore")).hexdigest()


def _html_tag_counts(html: str) -> Dict[str, int]:
    tags = re.findall(r"<\s*([a-zA-Z][a-zA-Z0-9]*)", _s(html))
    keep = {"main", "section", "article", "aside", "header", "footer", "nav", "h1", "h2", "h3", "h4", "h5", "h6",
            "ul", "ol", "li", "a", "button", "form", "table", "figure", "picture", "img", "video"}
    return dict(Counter(t.lower() for t in tags if t.lower() in keep))


def _normalize_list_text(items: Any, limit: int = 30) -> List[str]:
    out: List[str] = []
    for x in (items or []):
        if isinstance(x, dict):
            val = x.get("text") or x.get("question") or x.get("name") or x.get("alt") or x.get("src") or ""
        else:
            val = x
        val = re.sub(r"\s+", " ", _s(val)).strip()
        if val:
            out.append(val[:160])
    return out[:limit]


def structural_signature(page: Dict[str, Any]) -> Dict[str, Any]:
    """페이지의 구조적 지표 모음 (변화 감지/저장용)."""
    def _schema_nodes(sd) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        def add(node):
            if not isinstance(node, dict):
                return
            nodes.append(node)
            for g in (node.get("@graph") or []):
                add(g)
        for item in (sd or []):
            add(item)
        return nodes

    def _node_types(node: Dict[str, Any]) -> List[str]:
        t = node.get("@type")
        if isinstance(t, list):
            return [str(x) for x in t]
        return [str(t)] if t else []

    def _schema_types(sd) -> List[str]:
        out = []
        for node in _schema_nodes(sd):
            out.extend(_node_types(node))
        return sorted(set(map(str, out)))

    def _schema_props_by_type(sd) -> Dict[str, List[str]]:
        tracked = {"Product", "FAQPage", "Organization", "BreadcrumbList", "WebPage", "ItemPage", "CollectionPage", "ItemList"}
        props: Dict[str, set] = {}
        for node in _schema_nodes(sd):
            keys = {str(k) for k in node.keys() if not str(k).startswith("@")}
            for typ in _node_types(node):
                if typ in tracked:
                    props.setdefault(typ, set()).update(keys)
        return {typ: sorted(vals) for typ, vals in sorted(props.items())}

    nav = page.get("navigation") or {}
    ctas = _normalize_list_text(page.get("ctas"), 20)
    h2 = _normalize_list_text(page.get("h2"), 30)
    h3 = _normalize_list_text(page.get("h3"), 30)
    imgs = page.get("images") or []
    return {
        "h2_count": len(page.get("h2") or []),
        "h3_count": len(page.get("h3") or []),
        "cta_count": len(page.get("ctas") or []),
        "faq_count": len(page.get("faqs") or []),
        "img_count": len(imgs),
        "nav_items": sorted({_s(i.get("text") if isinstance(i, dict) else i)
                             for i in (nav.get("main") or [])} - {""}),
        "schema_types": _schema_types(page.get("structured_data")),
        "schema_props_by_type": _schema_props_by_type(page.get("structured_data")),
        "dom_hash": dom_fingerprint(page.get("html_content") or ""),
        "tag_counts": _html_tag_counts(page.get("html_content") or ""),
        "h2_texts": h2,
        "h3_texts": h3,
        "cta_texts": ctas,
        "image_keys": sorted({_normalize_image_src(_s(im.get("src"))) for im in imgs if isinstance(im, dict) and im.get("src")})[:50],
    }


# ──────────────────────────────────────────────────────────────
# Image perceptual hash (aHash) — Pillow 만 사용 (numpy 불필요)
# ──────────────────────────────────────────────────────────────

def average_hash(image_bytes: bytes, size: int = 16) -> Optional[str]:
    """
    스크린샷 bytes → 64bit aHash (16x16 grayscale 평균 기준).
    반환: 16진수 문자열. 실패 시 None.
    이미지 파일은 저장하지 않고 이 해시만 DB 에 보관한다.
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((size, size))
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p >= avg else "0" for p in pixels)
        return f"{int(bits, 2):0{size * size // 4}x}"
    except Exception:
        return None


def hamming_distance(h1: Optional[str], h2: Optional[str]) -> Optional[int]:
    if not h1 or not h2 or len(h1) != len(h2):
        return None
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except Exception:
        return None


def _normalize_image_src(src: str) -> str:
    """CDN querystring/width/format 파라미터처럼 매번 달라지는 값 제거."""
    src = _s(src).strip()
    if not src or src.startswith("data:"):
        return ""

    # srcset 문자열이 섞여 들어온 경우 첫 URL만 비교 대상으로 사용한다.
    # (예: "image.jpg 720w, image-large.jpg 1440w")
    if "," in src and re.search(r"\s(?:\d+(?:w|x))", src, flags=re.IGNORECASE):
        first = src.split(",", 1)[0].strip().split()[0]
        if first:
            src = first

    try:
        sp = urlsplit(src)
        path = re.sub(r"/(?:w|h|q|f)_\d+(?=/)", "", sp.path)
        path = re.sub(r"([_-])\d{2,5}x\d{2,5}(?=\.)", "", path, flags=re.IGNORECASE)
        path = re.sub(r"([_-])(?:mo|pc|desktop|mobile|tablet)(?=\.)", "", path, flags=re.IGNORECASE)
        path = re.sub(r"([_-])(?:small|medium|large|xlarge|retina|1x|2x|3x)(?=\.)", "", path, flags=re.IGNORECASE)
        path = re.sub(r"([_-])(?:width|height|resize|crop)-?\d{2,5}(?=\.)", "", path, flags=re.IGNORECASE)
        return urlunsplit((sp.scheme, sp.netloc, path, "", "")) or path
    except Exception:
        return re.sub(r"[?#].*$", "", src)


def _stable_list_text(items: Any, key: str = "text", limit: int = 80) -> List[str]:
    """COUNT 비교용 리스트 정규화. 순서 흔들림과 짧은 UI 라벨을 줄인다."""
    out: List[str] = []
    for item in (items or []):
        if isinstance(item, dict):
            value = item.get(key) or item.get("question") or item.get("name") or item.get("alt") or item.get("src") or ""
        else:
            value = item
        value = stable_text(_s(value))
        if not value or _is_minor_ui_text(value):
            continue
        out.append(value[:220])
    return sorted(set(out))[:limit]


def stable_snapshot_fingerprint(page: Dict[str, Any]) -> str:
    """반복 크롤 COUNT 안정화를 위한 URL 스냅샷 지문.

    raw HTML/이미지 순서/메뉴 위치처럼 매번 흔들리는 값 대신,
    실제 변경점으로 집계할 후보만 정규화해 해시화한다.
    동일 지문이면 바로 재크롤 시 변경점 COUNT가 0이 된다.
    """
    if not page:
        return ""

    sig = page.get("_sig") if isinstance(page.get("_sig"), dict) else None
    if sig is None:
        sig = structural_signature(page) if (page.get("html_content") or page.get("structured_data")) else {}

    images = []
    for im in (page.get("images") or []):
        if not isinstance(im, dict):
            continue
        src = _normalize_image_src(_s(im.get("src")))
        if not src or re.search(r"(?:pixel|tracking|spacer|blank|1x1|transparent|placeholder)", src, re.IGNORECASE):
            continue
        images.append(src)

    payload = {
        "title": stable_text(_s(page.get("title"))),
        "h1": stable_text(_s(page.get("h1"))),
        "meta_description": stable_text(_s(page.get("meta_description"))),
        "canonical_url": stable_text(_s(page.get("canonical_url"))),
        "body_units": sorted(set(_stable_copy_units(page.get("body_content") or "")))[:220],
        "schema_types": sorted(set(sig.get("schema_types") or [])),
        "h2_texts": _stable_list_text(sig.get("h2_texts") or page.get("h2") or [], limit=40),
        "cta_texts": [t for t in _stable_list_text(sig.get("cta_texts") or page.get("ctas") or [], limit=40) if _is_campaign_copy(t)],
        "faq_questions": _stable_list_text(page.get("faqs") or [], key="question", limit=80),
        "image_keys": sorted(set(images))[:80],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()


# ──────────────────────────────────────────────────────────────
# Severity 분류
# ──────────────────────────────────────────────────────────────

def _is_critical(field_name: str, before: str, after: str, critical_keywords: List[str]) -> bool:
    blob = f"{field_name} {before} {after}".lower()
    return any(k.lower() in blob for k in critical_keywords)


# 카피 변경 중요도 보정: 캠페인/전환 문구는 우선 감지하고,
# 짧은 메뉴·탭·네비게이션 라벨은 낮은 등급으로 제한한다.
_CAMPAIGN_COPY_RE = re.compile(
    r"("
    r"campaign|promo(?:tion)?|offer|deal|sale|save|discount|coupon|voucher|bundle|bonus|cashback|"
    r"launch|new|introduc|announce|available|limited|exclusive|event|unpacked|"
    r"pre[- ]?order|reserve|trade[- ]?in|switch|compare|upgrade|buy|shop|cart|checkout|"
    r"galaxy ai|apple intelligence|one ui|bespoke|fold|flip|ultra|qled|oled|"
    r"캠페인|프로모션|혜택|할인|쿠폰|세일|무료|증정|사은품|이벤트|한정|단독|"
    r"출시|런칭|신규|신제품|공개|사전예약|예약|구매|장바구니|보상판매|업그레이드|비교|"
    r"갤럭시 ai|애플 인텔리전스"
    r")",
    re.IGNORECASE,
)

_MINOR_UI_RE = re.compile(
    r"^("
    r"overview|features?|specs?|specifications?|design|gallery|reviews?|support|learn more|view more|see more|"
    r"home|shop|mobile|tv|audio|accessories|for business|search|menu|close|open|next|previous|"
    r"전체|개요|특징|기능|스펙|사양|디자인|갤러리|리뷰|지원|더 알아보기|자세히 보기|"
    r"홈|모바일|티비|오디오|액세서리|검색|메뉴|닫기|열기|다음|이전|탭"
    r")$",
    re.IGNORECASE,
)

def _is_campaign_copy(text: str) -> bool:
    return bool(_CAMPAIGN_COPY_RE.search(stable_text(text)))


# CTA 중요도 전용: '개 특이한' 프로모/오퍼성 CTA만 잡는다.
# 흔한 구매 동사(buy/shop/cart/order/pre-order/reserve/compare/upgrade)는 제외 → 낮음 처리.
_PROMO_CTA_RE = re.compile(
    r"("
    r"save|discount|\boff\b|deal|offer|promo(?:tion)?|coupon|voucher|cashback|bonus|gift|\bfree\b|"
    r"trade[- ]?in|bundle|limited|exclusive|unpacked|\bsale\b|giveaway|"
    r"[£$€₩]\s?\d|\d+\s?%|"
    r"할인|혜택|무료|증정|사은품|한정|단독|이벤트|보상판매|세일|프로모션|쿠폰|경품"
    r")",
    re.IGNORECASE,
)


def _is_promo_cta(text: str) -> bool:
    return bool(_PROMO_CTA_RE.search(stable_text(text)))


def _is_minor_ui_text(text: str) -> bool:
    txt = stable_text(text).strip(" -–—|·•:[]()")
    if not txt:
        return True
    words = _tokens(txt)
    if len(txt) <= 32 and len(words) <= 5:
        return True
    return bool(_MINOR_UI_RE.match(txt))


def _copy_importance_note(field_name: str, before: str, after: str) -> str:
    blob = f"{before} {after}"
    if _is_campaign_copy(blob):
        return "campaign_or_conversion_copy"
    if field_name in ("navigation", "ctas") or _is_minor_ui_text(before) or _is_minor_ui_text(after):
        return "minor_ui_or_menu_copy"
    return "general_copy"


def classify_text_severity(field_name: str, before: str, after: str,
                           cd: Dict[str, Any], ts: Dict[str, Any],
                           critical_keywords: List[str]) -> str:
    """텍스트 변화의 L0~L5.

    COPY 영역은 캠페인/전환 문구 중심으로 등급을 올리고,
    메뉴·탭·짧은 UI 라벨성 문구는 기본적으로 Low 수준으로 제한한다.
    """
    if _is_critical(field_name, before, after, critical_keywords):
        return "L5"

    sent_changed = len(ts["sentences_added"]) + len(ts["sentences_removed"])
    word_changed = len(ts["words_added"]) + len(ts["words_removed"])
    total_chars = cd["char_added"] + cd["char_removed"]
    is_copy_field = field_name in ("h1", "body_content", "meta_description")
    campaign_copy = _is_campaign_copy(f"{before} {after}")
    minor_ui_copy = _is_minor_ui_text(before) or _is_minor_ui_text(after)

    if is_copy_field:
        # 캠페인/프로모션/전환에 직접 닿는 문구는 일반 문장 변경보다 우선 감지
        if campaign_copy:
            if sent_changed >= 3 or total_chars > 300:
                return "L3"
            return "L2"
        # 메뉴 탭·짧은 안내 라벨·소폭 문구 변경은 Low로 제한
        if minor_ui_copy or (sent_changed <= 1 and total_chars <= 180):
            return "L1" if (word_changed >= 1 or total_chars > 2 or sent_changed) else "L0"
        # 캠페인성이 없는 본문 대량 변경도 곧바로 High로 보지 않고 Medium 수준에서 관찰
        if sent_changed >= 4 or total_chars > 500:
            return "L2"

    if sent_changed >= 4 or total_chars > 400:
        return "L3"                       # 섹션급
    if sent_changed >= 1:
        return "L2"                       # 문장/문구
    if word_changed >= 1 or total_chars > 2:
        return "L1"                       # 단어
    return "L0"                           # 미세


# ──────────────────────────────────────────────────────────────
# 메인 엔진
# ──────────────────────────────────────────────────────────────

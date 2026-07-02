"""
Diff Engine — 3단계 diff + L0~L5 severity + 이미지 perceptual-hash
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
    def _schema_types(sd) -> List[str]:
        out = []
        for s in (sd or []):
            if isinstance(s, dict):
                t = s.get("@type")
                if isinstance(t, str):
                    out.append(t)
                elif isinstance(t, list):
                    out.extend(str(x) for x in t)
                for g in (s.get("@graph") or []):
                    if isinstance(g, dict) and g.get("@type"):
                        gt = g["@type"]
                        out.extend(gt if isinstance(gt, list) else [gt])
        return sorted(set(map(str, out)))

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

class DiffEngine:
    """
    이전 스냅샷(previous) ↔ 현재(current) 단일 URL 비교 → ChangeEvent[].
    crawl_service 는 URL별로 이 엔진을 호출한다.
    """

    # 텍스트 비교 대상 필드 → (change_type)
    TEXT_FIELDS = {
        "title": "technical",
        "meta_description": "technical",
        "canonical_url": "technical",
        "h1": "content",
        "body_content": "content",
    }

    def __init__(self, critical_keywords: Optional[List[str]] = None,
                 min_diff_ratio: float = 0.002):
        self.critical_keywords = critical_keywords or [
            "price", "$", "₩", "월", "할부", "trade-in", "보상",
            "sold out", "품절", "out of stock", "pre-order", "사전예약",
            "buy now", "add to cart", "purchase", "order now", "checkout", "구매하기", "장바구니",
        ]
        self.min_diff_ratio = min_diff_ratio

    def detect(self, url: str, site_key: str, tier_level: int,
               current: Dict[str, Any], previous: Dict[str, Any]) -> List[ChangeEvent]:
        events: List[ChangeEvent] = []
        previous = previous or {}

        # [FIX] 렌더링 방식(httpx/playwright)이 직전 스냅샷과 다르면, body_content/DOM
        # 비교 자체가 "같은 페이지의 두 시점"이 아니라 "다른 추출 방식의 두 결과"를
        # 비교하는 셈이 되어 실제 사이트 변경 없이도 대량의 가짜 변경점이 생길 수 있다.
        # 지금 당장 억제하지는 않고(오탐 여부 판단을 위해 몇 회차 더 관찰), 각 이벤트의
        # evidence에 남겨 UI/export에서 바로 확인 가능하게만 한다.
        prev_rb, cur_rb = previous.get("rendered_by"), current.get("rendered_by")
        render_mismatch = bool(prev_rb) and bool(cur_rb) and prev_rb != cur_rb
        render_note = {"render_mismatch": True, "rendered_by_before": prev_rb,
                        "rendered_by_after": cur_rb} if render_mismatch else {}

        # 1) 텍스트 필드 (char + token/sentence)
        for fld, ctype in self.TEXT_FIELDS.items():
            b, a = _s(previous.get(fld)), _s(current.get(fld))
            b_cmp, a_cmp = _comparison_text(fld, b), _comparison_text(fld, a)
            if b_cmp == a_cmp:
                continue
            cd = char_diff(b_cmp, a_cmp)
            if cd["diff_ratio"] < self.min_diff_ratio and not _is_critical(fld, b_cmp, a_cmp, self.critical_keywords):
                continue                  # noise 게이트
            ts = token_sentence_diff(b_cmp, a_cmp)
            if not _copy_change_is_meaningful(fld, b_cmp, a_cmp, cd, ts):
                continue
            sev = classify_text_severity(fld, b_cmp, a_cmp, cd, ts, self.critical_keywords)
            ctype2 = "commerce" if sev == "L5" else ctype
            events.append(ChangeEvent(
                url=url, site_key=site_key, tier_level=tier_level,
                field_name=fld, change_type=ctype2,
                severity_level=sev, severity_legacy=SEVERITY_TO_LEGACY[sev],
                summary=self._text_summary(fld, b_cmp, a_cmp, ts),
                before_value=(b_cmp if fld == "body_content" else b)[:1000] or None,
                after_value=(a_cmp if fld == "body_content" else a)[:1000] or None,
                char_added=cd["char_added"], char_removed=cd["char_removed"],
                diff_ratio=cd["diff_ratio"],
                evidence={"sentences_added": ts["sentences_added"][:5],
                          "sentences_removed": ts["sentences_removed"][:5],
                          "copy_importance": _copy_importance_note(fld, b_cmp, a_cmp),
                          "comparison_note": "본문은 헤더/푸터/메뉴/쿠키/추천 영역을 제외한 안정화 카피 기준으로 비교" if fld == "body_content" else ""},
            ))

        # 2) 구조 (DOM / nav / schema) — L4
        cs = structural_signature(current)
        ps = previous.get("_sig") or (structural_signature(previous) if previous.get("html_content") else {})
        events.extend(self._structural_events(url, site_key, tier_level, cs, ps))

        # 3) CTA / FAQ — commerce / content
        events.extend(self._list_field_events(
            url, site_key, tier_level, "ctas", "text", "commerce",
            current, previous, added_sev="L2", removed_sev="L2"))
        events.extend(self._list_field_events(
            url, site_key, tier_level, "faqs", "question", "content",
            current, previous, added_sev="L3", removed_sev="L3"))

        # 4) 이미지 perceptual hash — visual / L0~L3 (스크린샷이 있을 때만 동작)
        ev = self._image_event(url, site_key, tier_level, current, previous)
        if ev:
            events.append(ev)

        # 4b) 이미지 src/alt 기반 시각 변화 — 스크린샷 없이도 감지 가능한 우회 경로.
        #     이미지 추가/제거(src 기준)와 동일 이미지의 alt 텍스트 변경을 잡는다.
        events.extend(self._image_list_events(url, site_key, tier_level, current, previous))

        if render_mismatch:
            for ev in events:
                ev.evidence.update(render_note)

        return events

    # ── helpers ────────────────────────────────────────────

    def _text_summary(self, fld: str, b: str, a: str, ts: Dict) -> str:
        if not b:
            return f"{fld} 신규 추가"
        if not a:
            return f"{fld} 제거됨"
        sa, sr = len(ts["sentences_added"]), len(ts["sentences_removed"])
        if sa or sr:
            return f"{fld} 변경 (문장 +{sa}/-{sr})"
        return f"{fld} 변경 (단어 단위)"

    def _structural_events(self, url, site_key, tier, cs, ps) -> List[ChangeEvent]:
        out = []
        if not ps:
            return out
        # 스키마 타입 변화
        c_sch, p_sch = set(cs.get("schema_types", [])), set(ps.get("schema_types", []))
        for t in sorted(c_sch - p_sch):
            out.append(self._mk(url, site_key, tier, "schema_type", "technical", "L4",
                                 f"스키마 신규: {t}", after=t,
                                 evidence={"kind": "schema_added", "type": t}))
        for t in sorted(p_sch - c_sch):
            out.append(self._mk(url, site_key, tier, "schema_type", "technical", "L4",
                                 f"스키마 제거: {t}", before=t,
                                 evidence={"kind": "schema_removed", "type": t}))
        # 내비게이션 항목 변화
        # 메뉴/푸터/국가 선택 등은 매번 흔들리기 쉬워 변경점 수를 과도하게 만든다.
        # 캠페인·구매전환성 내비 문구만 저장한다.
        c_nav, p_nav = set(cs.get("nav_items", [])), set(ps.get("nav_items", []))
        for t in sorted(c_nav - p_nav):
            if not _is_campaign_copy(t):
                continue
            out.append(self._mk(url, site_key, tier, "navigation", "navigation", "L2",
                                 f"주요 내비 캠페인 문구 추가: {t}", after=t,
                                 evidence={"copy_importance": _copy_importance_note("navigation", "", t),
                                           "counting_note": "일반 메뉴/푸터 라벨은 반복 크롤 노이즈로 제외"}))
        for t in sorted(p_nav - c_nav):
            if not _is_campaign_copy(t):
                continue
            out.append(self._mk(url, site_key, tier, "navigation", "navigation", "L2",
                                 f"주요 내비 캠페인 문구 제거: {t}", before=t,
                                 evidence={"copy_importance": _copy_importance_note("navigation", t, ""),
                                           "counting_note": "일반 메뉴/푸터 라벨은 반복 크롤 노이즈로 제외"}))
        # DOM 골격 해시 변화. 단순 해시값 차이만으로는 알림을 만들지 않고,
        # 저장된 구조 지표에서 실제로 설명 가능한 변화가 있을 때만 이벤트화한다.
        if cs.get("dom_hash") and ps.get("dom_hash") and cs["dom_hash"] != ps["dom_hash"]:
            count_fields = [
                ("h2_count", "H2 제목"), ("h3_count", "H3 제목"),
                ("cta_count", "CTA 버튼"), ("faq_count", "FAQ 문항"), ("img_count", "이미지"),
            ]
            deltas, parts = {}, []
            for key, label in count_fields:
                b, a = ps.get(key), cs.get(key)
                if isinstance(b, int) and isinstance(a, int) and b != a:
                    diff = a - b
                    # 이미지/CTA/H3 같은 반복 요소의 1~2개 차이는 동적 렌더링 노이즈일 가능성이 높다.
                    if key == "img_count" and abs(diff) < 5:
                        continue
                    if key in ("cta_count", "h3_count") and abs(diff) < 3:
                        continue
                    if key == "faq_count" and abs(diff) < 2:
                        continue
                    deltas[key] = {"label": label, "before": b, "after": a, "diff": diff}
                    parts.append(f"{label} {'+' if diff > 0 else ''}{diff}")

            raw_tag_deltas = _tag_count_delta(ps.get("tag_counts") or {}, cs.get("tag_counts") or {}) if ps.get("tag_counts") and cs.get("tag_counts") else {}
            tag_deltas = _meaningful_tag_deltas(raw_tag_deltas)
            if tag_deltas:
                parts.append("핵심 태그 구성 변경")

            heading_delta = _short_list_delta(ps.get("h2_texts") or [], cs.get("h2_texts") or []) if ps.get("h2_texts") is not None and cs.get("h2_texts") is not None else {"added": [], "removed": []}
            cta_delta = _short_list_delta(ps.get("cta_texts") or [], cs.get("cta_texts") or []) if ps.get("cta_texts") is not None and cs.get("cta_texts") is not None else {"added": [], "removed": []}
            heading_delta = {
                "added": [t for t in heading_delta["added"] if _is_campaign_copy(t) or not _is_minor_ui_text(t)],
                "removed": [t for t in heading_delta["removed"] if _is_campaign_copy(t) or not _is_minor_ui_text(t)],
            }
            cta_delta = {
                "added": [t for t in cta_delta["added"] if _is_campaign_copy(t) or _is_critical("ctas", "", t, self.critical_keywords)],
                "removed": [t for t in cta_delta["removed"] if _is_campaign_copy(t) or _is_critical("ctas", t, "", self.critical_keywords)],
            }
            if heading_delta["added"] or heading_delta["removed"]:
                parts.append("핵심 H2 문구 변경")
            if cta_delta["added"] or cta_delta["removed"]:
                parts.append("구매/캠페인 CTA 문구 변경")

            # 해시만 바뀌었거나 li/a/button 같은 반복 태그 1~2개 차이만 있으면
            # 메뉴·푸터·캐러셀·동적 렌더링 노이즈로 간주해 변경점에서 제외한다.
            if not (deltas or tag_deltas or heading_delta["added"] or heading_delta["removed"] or cta_delta["added"] or cta_delta["removed"]):
                return out

            dom_sev = _dom_severity_level(deltas, tag_deltas, heading_delta, cta_delta)
            summary = "DOM 구조 참고 변화" + (f" — {', '.join(parts[:4])}" if parts else "")
            evidence = {
                "dom_hash_before": ps["dom_hash"][:12], "dom_hash_after": cs["dom_hash"][:12],
                "structure_note": "H2/CTA/FAQ/이미지 개수, 핵심 구조 태그처럼 설명 가능한 변화만 표시. li/a/button 등 반복 태그의 소폭 차이는 제외",
            }
            if deltas:
                evidence["count_deltas"] = deltas
            if tag_deltas:
                evidence["tag_deltas"] = tag_deltas
            if heading_delta["added"] or heading_delta["removed"]:
                evidence["heading_deltas"] = heading_delta
            if cta_delta["added"] or cta_delta["removed"]:
                evidence["cta_deltas"] = cta_delta
            out.append(self._mk(url, site_key, tier, "dom", "technical", dom_sev, summary, evidence=evidence))
        return out

    def _list_field_events(self, url, site_key, tier, fld, key, ctype,
                           cur, prev, added_sev, removed_sev) -> List[ChangeEvent]:
        def texts(p):
            return {_s(x.get(key) if isinstance(x, dict) else x) for x in (p.get(fld) or [])} - {""}

        def sev_for(text: str, default: str) -> str:
            if _is_critical(fld, "", text, self.critical_keywords):
                return "L5"
            if fld == "ctas":
                if _is_campaign_copy(text):
                    return "L2"
                return "L1"
            if fld == "faqs":
                if _is_campaign_copy(text):
                    return "L2"
                return "L1" if _is_minor_ui_text(text) else default
            return default

        c, p = texts(cur), texts(prev)
        out = []

        def keep_list_change(text: str) -> bool:
            if _is_critical(fld, "", text, self.critical_keywords):
                return True
            if fld == "ctas":
                # Learn more / Explore 같은 일반 버튼은 크롤마다 출현 위치가 흔들리므로 제외.
                return _is_campaign_copy(text)
            if fld == "faqs":
                # FAQ는 실제 문항 변화만 남기고 짧은 탭/라벨성 노이즈는 제외.
                return not _is_minor_ui_text(text)
            return True

        for t in sorted(c - p):
            if not keep_list_change(t):
                continue
            sev = sev_for(t, added_sev)
            out.append(self._mk(url, site_key, tier, fld, ctype, sev,
                                 f"{fld} 추가: {t[:60]}", after=t,
                                 evidence={"copy_importance": _copy_importance_note(fld, "", t),
                                           "counting_note": "일반 메뉴/탭/짧은 CTA 라벨은 변경점 집계에서 제외" if fld == "ctas" else ""}))
        for t in sorted(p - c):
            if not keep_list_change(t):
                continue
            sev = sev_for(t, removed_sev)
            out.append(self._mk(url, site_key, tier, fld, ctype, sev,
                                 f"{fld} 제거: {t[:60]}", before=t,
                                 evidence={"copy_importance": _copy_importance_note(fld, t, ""),
                                           "counting_note": "일반 메뉴/탭/짧은 CTA 라벨은 변경점 집계에서 제외" if fld == "ctas" else ""}))
        return out

    def _image_list_events(self, url, site_key, tier, cur, prev) -> List[ChangeEvent]:
        """스크린샷(perceptual hash) 없이도 이미지 변화를 감지하는 우회 경로.

        변경점 건수가 비정상적으로 커지지 않도록 이미지 1장마다 이벤트를 만들지 않고,
        URL 1개당 이미지 구성 변경을 최대 1건으로 집계한다.
        """
        def _norm(imgs) -> Dict[str, str]:
            out: Dict[str, str] = {}
            for im in (imgs or []):
                if not isinstance(im, dict):
                    continue
                src = _normalize_image_src(_s(im.get("src")))
                if not src or re.search(r"(?:pixel|tracking|spacer|blank|1x1|transparent|placeholder)", src, re.IGNORECASE):
                    continue
                out[src] = stable_text(_s(im.get("alt")))
            return out

        c_imgs, p_imgs = _norm(cur.get("images")), _norm(prev.get("images"))
        if not c_imgs and not p_imgs:
            return []

        # 이전 스냅샷에 이미지 목록이 없는데 현재만 대량 존재하는 경우는
        # 실제 사이트 변경이 아니라 수집 로직 보강/일시 누락의 첫 기준선으로 간주한다.
        if (not p_imgs and len(c_imgs) >= 3) or (not c_imgs and len(p_imgs) >= 3):
            return []

        added = sorted(set(c_imgs) - set(p_imgs))
        removed = sorted(set(p_imgs) - set(c_imgs))
        alt_changed = [
            (src, p_imgs[src], c_imgs[src])
            for src in sorted(set(c_imgs) & set(p_imgs))
            if p_imgs[src] != c_imgs[src]
        ]

        if not added and not removed and not alt_changed:
            return []

        total_delta = len(added) + len(removed) + len(alt_changed)
        total_known = max(len(c_imgs), len(p_imgs), 1)
        overlap = len(set(c_imgs) & set(p_imgs))
        overlap_ratio = overlap / total_known

        # 동일 페이지 연속 크롤에서 lazy-load/srcset/추천 이미지가 1~3장 흔들리는 경우는 제외한다.
        # 대량 변화 또는 겹침이 낮은 경우만 실제 비주얼 구성 변화로 본다.
        if total_delta <= 2 and not alt_changed:
            return []
        if total_delta <= 3 and overlap_ratio >= 0.85:
            return []
        if total_delta <= 5 and overlap_ratio >= 0.92 and not alt_changed:
            return []

        sev = "L2" if total_delta >= 8 or overlap_ratio < 0.70 else "L1"
        parts = []
        if added:
            parts.append(f"추가 {len(added)}개")
        if removed:
            parts.append(f"제거 {len(removed)}개")
        if alt_changed:
            parts.append(f"alt 변경 {len(alt_changed)}개")

        evidence = {
            "kind": "image_inventory_changed",
            "added_count": len(added),
            "removed_count": len(removed),
            "alt_changed_count": len(alt_changed),
            "added_samples": added[:5],
            "removed_samples": removed[:5],
            "alt_changed_samples": [
                {"src": src, "before": b, "after": a}
                for src, b, a in alt_changed[:5]
            ],
            "counting_note": "이미지 단위가 아닌 URL 단위 1건으로 집계. 1~3장 수준의 lazy-load/srcset 흔들림은 제외",
            "overlap_ratio": round(overlap_ratio, 4),
        }
        return [self._mk(
            url, site_key, tier, "image", "visual", sev,
            "이미지 구성 변경 — " + ", ".join(parts),
            evidence=evidence,
        )]

    def _image_event(self, url, site_key, tier, cur, prev) -> Optional[ChangeEvent]:
        c_hash, p_hash = cur.get("screenshot_phash"), prev.get("screenshot_phash")
        dist = hamming_distance(c_hash, p_hash)
        if dist is None or dist == 0:
            return None
        # 64bit aHash 기준: 2이하=노이즈, 3~8=부분변경, 9+=대폭 변경
        if dist <= 2:
            return None
        sev = "L1" if dist <= 8 else ("L2" if dist <= 16 else "L3")
        return self._mk(url, site_key, tier, "screenshot", "visual", sev,
                        f"비주얼 변화 감지 (perceptual 거리 {dist})",
                        evidence={"phash_before": p_hash, "phash_after": c_hash,
                                  "hamming": dist})

    def _mk(self, url, site_key, tier, fld, ctype, sev, summary,
            before=None, after=None, evidence=None) -> ChangeEvent:
        return ChangeEvent(
            url=url, site_key=site_key, tier_level=tier,
            field_name=fld, change_type=ctype,
            severity_level=sev, severity_legacy=SEVERITY_TO_LEGACY[sev],
            summary=summary, before_value=_s(before)[:1000] or None,
            after_value=_s(after)[:1000] or None,
            evidence=evidence or {},
        )


def summarize_events(events: List[ChangeEvent]) -> Dict[str, Any]:
    by_level = {lv: 0 for lv in SEVERITY_ORDER}
    by_type: Dict[str, int] = {}
    for e in events:
        by_level[e.severity_level] = by_level.get(e.severity_level, 0) + 1
        by_type[e.change_type] = by_type.get(e.change_type, 0) + 1
    max_level = "L0"
    for lv in reversed(SEVERITY_ORDER):
        if by_level.get(lv):
            max_level = lv
            break
    return {"total": len(events), "by_level": by_level,
            "by_type": by_type, "max_level": max_level}


# ──────────────────────────────────────────────────────────────
# 이미지 비교샷용: 초소형 썸네일 (DB 보관용, 원본 저장 안 함)
# ──────────────────────────────────────────────────────────────

def thumbnail_b64(image_bytes: bytes, width: int = 360, quality: int = 35) -> Optional[str]:
    """
    스크린샷 bytes → 가로 width 로 축소한 JPEG base64 문자열.
    before/after 비교샷 표시용. 한 장 ~8~15KB (45 URL×2 ≈ 1MB → 무료 DB OK).
    """
    try:
        from PIL import Image
        import io, base64
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if img.width > width:
            img = img.resize((width, int(img.height * width / img.width)))
        # 너무 긴 페이지는 상단 1200px 만 (히어로 영역 위주)
        if img.height > 1200:
            img = img.crop((0, 0, img.width, 1200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def diff_regions(before_b64: Optional[str], after_b64: Optional[str],
                 grid: int = 16, thresh: int = 28) -> List[Dict[str, float]]:
    """
    두 썸네일(base64)을 격자로 나눠 변화가 큰 셀의 상대 좌표를 반환.
    UI 에서 빨간 박스로 '바뀐 영역'을 표시하는 데 사용. 좌표는 0~1 비율.
    """
    try:
        from PIL import Image
        import io, base64
        def _load(b):
            raw = base64.b64decode(b.split(",", 1)[1])
            return Image.open(io.BytesIO(raw)).convert("L")
        a, b = _load(before_b64), _load(after_b64)
        b = b.resize(a.size)
        W, H = a.size
        cw, ch = max(1, W // grid), max(1, H // grid)
        ap, bp = a.load(), b.load()
        out = []
        for gy in range(grid):
            for gx in range(grid):
                acc = n = 0
                for yy in range(gy * ch, min((gy + 1) * ch, H), 3):
                    for xx in range(gx * cw, min((gx + 1) * cw, W), 3):
                        acc += abs(ap[xx, yy] - bp[xx, yy]); n += 1
                if n and acc / n > thresh:
                    out.append({"x": gx / grid, "y": gy / grid,
                                "w": 1 / grid, "h": 1 / grid})
        return out
    except Exception:
        return []

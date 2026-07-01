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
# DOM / structure fingerprint
# ──────────────────────────────────────────────────────────────

def dom_fingerprint(html: str) -> str:
    """
    태그 시퀀스 기반 구조 지문. 본문 텍스트가 아니라 '레이아웃 골격'만 본다.
    BeautifulSoup 없이도 동작하도록 정규식 태그 시퀀스를 해시.
    """
    html = _s(html)
    tags = re.findall(r"<\s*([a-zA-Z][a-zA-Z0-9]*)", html)
    skeleton = ">".join(t.lower() for t in tags
                         if t.lower() not in ("script", "style", "noscript", "path", "svg"))
    return hashlib.sha1(skeleton.encode("utf-8", "ignore")).hexdigest()


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
    return {
        "h2_count": len(page.get("h2") or []),
        "h3_count": len(page.get("h3") or []),
        "cta_count": len(page.get("ctas") or []),
        "faq_count": len(page.get("faqs") or []),
        "img_count": len(page.get("images") or []),
        "nav_items": sorted({_s(i.get("text") if isinstance(i, dict) else i)
                             for i in (nav.get("main") or [])} - {""}),
        "schema_types": _schema_types(page.get("structured_data")),
        "dom_hash": dom_fingerprint(page.get("html_content") or ""),
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


# ──────────────────────────────────────────────────────────────
# Severity 분류
# ──────────────────────────────────────────────────────────────

def _is_critical(field_name: str, before: str, after: str, critical_keywords: List[str]) -> bool:
    blob = f"{field_name} {before} {after}".lower()
    return any(k.lower() in blob for k in critical_keywords)


def classify_text_severity(field_name: str, before: str, after: str,
                           cd: Dict[str, Any], ts: Dict[str, Any],
                           critical_keywords: List[str]) -> str:
    """텍스트 변화의 L0~L5."""
    if _is_critical(field_name, before, after, critical_keywords):
        return "L5"
    sent_changed = len(ts["sentences_added"]) + len(ts["sentences_removed"])
    word_changed = len(ts["words_added"]) + len(ts["words_removed"])
    total_chars = cd["char_added"] + cd["char_removed"]

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
        ]
        self.min_diff_ratio = min_diff_ratio

    def detect(self, url: str, site_key: str, tier_level: int,
               current: Dict[str, Any], previous: Dict[str, Any]) -> List[ChangeEvent]:
        events: List[ChangeEvent] = []
        previous = previous or {}

        # 1) 텍스트 필드 (char + token/sentence)
        for fld, ctype in self.TEXT_FIELDS.items():
            b, a = _s(previous.get(fld)), _s(current.get(fld))
            if b == a:
                continue
            cd = char_diff(b, a)
            if cd["diff_ratio"] < self.min_diff_ratio and not _is_critical(fld, b, a, self.critical_keywords):
                continue                  # noise 게이트
            ts = token_sentence_diff(b, a)
            sev = classify_text_severity(fld, b, a, cd, ts, self.critical_keywords)
            ctype2 = "commerce" if sev == "L5" else ctype
            events.append(ChangeEvent(
                url=url, site_key=site_key, tier_level=tier_level,
                field_name=fld, change_type=ctype2,
                severity_level=sev, severity_legacy=SEVERITY_TO_LEGACY[sev],
                summary=self._text_summary(fld, b, a, ts),
                before_value=b[:1000] or None, after_value=a[:1000] or None,
                char_added=cd["char_added"], char_removed=cd["char_removed"],
                diff_ratio=cd["diff_ratio"],
                evidence={"sentences_added": ts["sentences_added"][:5],
                          "sentences_removed": ts["sentences_removed"][:5]},
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

        # 4) 이미지 perceptual hash — visual / L0~L3
        ev = self._image_event(url, site_key, tier_level, current, previous)
        if ev:
            events.append(ev)

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
        c_nav, p_nav = set(cs.get("nav_items", [])), set(ps.get("nav_items", []))
        for t in sorted(c_nav - p_nav):
            out.append(self._mk(url, site_key, tier, "navigation", "navigation", "L4",
                                 f"내비 항목 추가: {t}", after=t))
        for t in sorted(p_nav - c_nav):
            out.append(self._mk(url, site_key, tier, "navigation", "navigation", "L4",
                                 f"내비 항목 제거: {t}", before=t))
        # DOM 골격 해시 변화 (텍스트 변화 없이 레이아웃만 바뀐 경우 포착)
        # ── 보강: dom_hash 자체는 뭉뚱그린 지문이라 "무엇이" 바뀌었는지 알려주지 않지만,
        #    같은 structural_signature 안에 이미 h2/h3/cta/faq/이미지 개수가 있으므로
        #    새 크롤링 없이 그 필드들을 비교해 구체적인 변화 내역을 evidence에 담는다.
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
                    deltas[key] = {"label": label, "before": b, "after": a, "diff": diff}
                    parts.append(f"{label} {'+' if diff > 0 else ''}{diff}")
            summary = "DOM 구조(레이아웃 골격) 변화" + (f" — {', '.join(parts)}" if parts else
                       " (h2/h3/CTA/FAQ/이미지 개수는 동일 — 순서·배치만 바뀐 것으로 추정)")
            evidence = {"dom_hash_before": ps["dom_hash"][:12], "dom_hash_after": cs["dom_hash"][:12]}
            if deltas:
                evidence["count_deltas"] = deltas
            out.append(self._mk(url, site_key, tier, "dom", "technical", "L4", summary, evidence=evidence))
        return out

    def _list_field_events(self, url, site_key, tier, fld, key, ctype,
                           cur, prev, added_sev, removed_sev) -> List[ChangeEvent]:
        def texts(p):
            return {_s(x.get(key) if isinstance(x, dict) else x) for x in (p.get(fld) or [])} - {""}
        c, p = texts(cur), texts(prev)
        out = []
        for t in sorted(c - p):
            sev = "L5" if _is_critical(fld, "", t, self.critical_keywords) else added_sev
            out.append(self._mk(url, site_key, tier, fld, ctype, sev,
                                 f"{fld} 추가: {t[:60]}", after=t))
        for t in sorted(p - c):
            sev = "L5" if _is_critical(fld, t, "", self.critical_keywords) else removed_sev
            out.append(self._mk(url, site_key, tier, fld, ctype, sev,
                                 f"{fld} 제거: {t[:60]}", before=t))
        return out

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

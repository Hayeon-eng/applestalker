"""
insight_rules_base.py — [2026-11] insight_rules.py 용량(47KB) 제한으로 분리한 앞부분.
공통(판단 기준·정렬·표기 유틸) + appleStalker 룰 + 메일 HTML 박스.
직접 import 하지 말고 insight_rules 를 통해 쓴다(insight_rules 가 전부 다시 내보냄).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse


# ── 판단 기준 ─────────────────────────────────────────────────────
WEAK_BELOW = 70          # 70점(%) 미만 = 부족
GAP_PP = 10              # 10%p 이상 차이 = 열세/우세
MAX_LINES = 3            # 한 박스 최대 줄 수

BASIS_SCORE = f"판단 기준: {WEAK_BELOW}점 미만 = 부족 · 비교 대상보다 {GAP_PP}%p 이상 낮음 = 열세, 높음 = 우세"


def _ins(rule: str, sev: int, text: str, action: str = "", metric: str = "", site: str = "",
         **extra: Any) -> Dict[str, Any]:
    text = text.strip()
    action = (action or "").strip()
    d = {"rule": rule, "sev": sev, "metric": metric, "site": site, "text": text, "action": action,
         "line": f"{text} → {action}" if action else text}
    d.update(extra)
    return d


def _top(items: Iterable[Dict[str, Any]], n: int = MAX_LINES) -> List[Dict[str, Any]]:
    """심각도(sev 작을수록 심각) → 등록 순서로 정렬해 상위 n개. 같은 문장 중복 제거."""
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x.get("sev", 9)):
        if it["line"] in seen:
            continue
        seen.add(it["line"])
        out.append(it)
        if len(out) >= n:
            break
    return out


def _join(xs: Iterable[str], n: int = 3) -> str:
    xs = [x for x in xs if x]
    if len(xs) <= n:
        return "·".join(xs)
    return "·".join(xs[:n]) + f" 외 {len(xs) - n}개"


def _pct(v: Optional[float]) -> str:
    return "-" if v is None else f"{round(v)}%"


# ════════════════════════════════════════════════════════════════
# 공통 표기
# ════════════════════════════════════════════════════════════════
SITE_SHORT = {
    "samsung": "삼성", "apple": "Apple", "google_pixel": "Pixel", "xiaomi": "Xiaomi", "oppo": "OPPO",
    "vivo": "vivo", "sony_audio": "Sony", "garmin": "Garmin", "dell": "Dell", "meta_ai_glasses": "Meta",
}


def site_short(key: str) -> str:
    return SITE_SHORT.get(key or "", key or "미분류")


_CASE = {"iphone": "iPhone", "ipad": "iPad", "macbook": "MacBook", "airpods": "AirPods", "imac": "iMac",
         "galaxy": "Galaxy", "pixel": "Pixel", "ai": "AI", "xps": "XPS", "pro": "Pro", "max": "Max",
         "ultra": "Ultra", "duo": "Duo", "air": "Air", "mini": "mini", "se": "SE"}


def page_name(url: str) -> str:
    """URL → 사람이 읽는 짧은 페이지 이름. 예: https://www.apple.com/iphone-duo/ → iPhone Duo"""
    try:
        path = urlparse(url or "").path.strip("/")
    except Exception:
        path = ""
    segs = [s for s in path.split("/") if s and not re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", s)]
    if not segs:
        return "홈"
    seg = segs[-1]
    if seg in ("buy", "shop", "specs", "compare") and len(segs) >= 2:
        seg = f"{segs[-2]} {seg}"
    words = re.split(r"[-_ ]+", seg)
    return " ".join(_CASE.get(w.lower(), w[:1].upper() + w[1:]) for w in words if w)[:40]


ROLE_KO = {"pf": "PF", "pdp": "PDP", "buying": "Buying", "specs": "스펙 페이지",
           "campaign_or_compare": "비교/캠페인 페이지", "home": "홈", "content": "콘텐츠 페이지", "unknown": "페이지"}
CAT_KO = {"phone": "폰", "tablet": "태블릿", "audio": "오디오", "watch": "워치", "laptop": "노트북", "ai_glass": "AI Glass"}


def _role(url: str) -> str:
    try:
        from config import page_role_for_url
        return page_role_for_url(url)
    except Exception:
        return "unknown"


def _cat(url: str) -> str:
    try:
        from config import product_category_for_url
        return product_category_for_url(url)
    except Exception:
        return "phone"


# ════════════════════════════════════════════════════════════════
# 1. 애플스토커 — DATA / COPY / VISUAL
# ════════════════════════════════════════════════════════════════
METRIC_EN = {"data": "DATA", "copy": "COPY", "visual": "VISUAL"}

# 화면 세부 지표(sharedScoring.ts metricScoreBreakdown 과 같은 계산) — 문장에 쓰는 한글 이름
COMP_KO = {
    "Schema": "스키마 적용률", "H-tag": "H1 적용률", "Structured": "스키마 타입 다양성",
    "역할적합성": "페이지 유형별 스키마", "Product 완성도": "Product 스키마 완성도", "@id 연결성": "@id 연결",
    "Copy richness": "카피 구체성", "CTA coverage": "구매 CTA 보유율", "Word coverage": "본문 분량",
    "FAQ 품질": "FAQ 품질", "intent 충족": "구체성 기준 충족 페이지", "중복 회피": "중복 문구 회피",
    "ALT ratio": "설명형 ALT 비율", "Image diversity": "사용 장면 이미지 비율", "Coverage": "이미지 보유율",
}

# 스키마 타입 → 삼성에서 넣을 위치 (D1 할 일)
SCHEMA_WHERE = {
    "FAQPage": "PDP", "Offer": "Buying·PDP", "AggregateOffer": "Buying·PDP", "AggregateRating": "PDP Product",
    "Review": "PDP Product", "VideoObject": "PDP 영상 영역", "BreadcrumbList": "전 페이지", "ItemList": "PF",
    "Product": "PDP", "ProductGroup": "PDP", "HowTo": "PDP·가이드 페이지", "QAPage": "PDP",
    "Organization": "전 페이지", "WebPage": "전 페이지", "WebSite": "홈", "ImageObject": "PDP 이미지 영역",
    "Brand": "PDP Product", "OfferCatalog": "PF·Buying",
}
# 비교 의미가 큰 타입만 D1 대상으로 삼는다(WebPage 같은 범용 타입 제외)
SCHEMA_MEANINGFUL = {"FAQPage", "Offer", "AggregateOffer", "AggregateRating", "Review", "VideoObject",
                     "BreadcrumbList", "ItemList", "Product", "ProductGroup", "HowTo", "QAPage", "OfferCatalog"}
# 추천 우선순위(검색·구매 영향이 큰 순) — 여러 타입이 부족할 때 할 일에는 앞의 것을 쓴다
SCHEMA_PRIORITY = ["Offer", "AggregateOffer", "Product", "FAQPage", "AggregateRating", "Review", "VideoObject",
                   "ProductGroup", "ItemList", "OfferCatalog", "QAPage", "HowTo", "BreadcrumbList"]


def _by_priority(types: Iterable[str]) -> List[str]:
    return sorted(types, key=lambda t: (SCHEMA_PRIORITY.index(t) if t in SCHEMA_PRIORITY else 99, t))


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) else None


def metric_components(metric: str, block: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """세부 지표 값(0~100). 수집 페이지가 0개면 None(근거 없음) — 0점과 구분한다. [A7]"""
    f = (block or {}).get("facts") or {}
    if metric == "data":
        sch = f.get("schema") or {}
        total = sch.get("total_pages") or 0
        if not total:
            return {k: None for k in ("Schema", "H-tag", "Structured", "역할적합성", "Product 완성도", "@id 연결성")}
        hs = (f.get("html_structure") or {}).get("h_tag_coverage") or {}
        schema = _num(sch.get("coverage_pct"))
        tc = len(sch.get("schema_type_counts") or {})
        roles = len(sch.get("role_alignment_gaps") or [])
        prod = ((sch.get("completeness") or {}).get("Product") or {}).get("filled_ratio")
        idl = sch.get("id_linkage") or {}
        idt, idk = idl.get("total_id_nodes") or 0, idl.get("linked_ids") or 0
        return {
            "Schema": round(schema) if schema is not None else None,
            "H-tag": round(hs["h1_coverage_pct"]) if isinstance(hs.get("h1_coverage_pct"), (int, float)) else None,
            "Structured": min(100, tc * 30) if tc else (round(schema) if schema is not None else None),
            "역할적합성": round((total - min(roles, total)) / total * 100),
            "Product 완성도": round(prod * 100) if isinstance(prod, (int, float)) else None,
            "@id 연결성": round(idk / idt * 100) if idt else None,
        }
    if metric == "copy":
        pages = ((f.get("copy_richness") or {}).get("all_pages")) or []
        total = len(pages) or ((f.get("page_inventory") or {}).get("total_pages") or 0)
        if not pages:
            return {k: None for k in ("Copy richness", "CTA coverage", "Word coverage", "FAQ 품질", "intent 충족", "중복 회피")}
        rich = round(sum(float(p.get("score") or 0) for p in pages) / len(pages))
        buy = (f.get("commerce_cta") or {}).get("pages_with_buy_cta")
        faq = (f.get("faq") or {}).get("detail") or []
        gap = len((f.get("copy_richness") or {}).get("intent_gap_pages") or [])
        dup = len((f.get("duplication") or {}).get("duplicate_copy_pages") or []) + \
            len((f.get("duplication") or {}).get("duplicate_cta_pages") or [])
        return {
            "Copy richness": rich,
            "CTA coverage": round(buy / total * 100) if isinstance(buy, int) and total else None,
            "Word coverage": round(sum(1 for p in pages if (p.get("word_count") or 0) >= 80) / len(pages) * 100),
            "FAQ 품질": round(sum(float(d.get("avg_score") or 0) for d in faq) / len(faq)) if faq else None,
            "intent 충족": round((len(pages) - min(gap, len(pages))) / len(pages) * 100),
            "중복 회피": 100 - round(min(dup, total) / total * 100) if total else None,
        }
    # visual
    div = f.get("image_diversity") or {}
    total_images = div.get("total_images") or 0
    if not total_images:
        return {"ALT ratio": None, "Image diversity": None, "Coverage": None}
    alt = (f.get("alt_text_quality") or {}).get("descriptive_ratio_pct")
    pages = (f.get("page_inventory") or {}).get("total_pages") or total_images
    return {
        "ALT ratio": round(alt) if isinstance(alt, (int, float)) else None,
        "Image diversity": round(div["lifestyle_ratio_pct"]) if isinstance(div.get("lifestyle_ratio_pct"), (int, float)) else None,
        "Coverage": min(100, round(total_images / pages * 100)) if pages else None,
    }


def metric_total(metric: str, block: Optional[Dict[str, Any]]) -> Optional[int]:
    vals = [v for v in metric_components(metric, block).values() if v is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _schema_types(block: Optional[Dict[str, Any]]) -> set:
    f = (block or {}).get("facts") or {}
    return set(((f.get("schema") or {}).get("schema_type_counts") or {}).keys())


def _copy_pages(block: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    f = (block or {}).get("facts") or {}
    return ((f.get("copy_richness") or {}).get("all_pages")) or []


def _quant_avg(block) -> Optional[float]:
    ps = _copy_pages(block)
    return round(sum(float(p.get("quant_per_100w") or 0) for p in ps) / len(ps), 1) if ps else None


def _evidence_ratio(block) -> Optional[int]:
    ps = _copy_pages(block)
    return round(sum(1 for p in ps if p.get("has_comparison") or p.get("has_evidence_keyword")) / len(ps) * 100) if ps else None


def _avg(vals: Iterable[Optional[float]]) -> Optional[float]:
    xs = [v for v in vals if v is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def _paths(urls: Iterable[str], n: int = 2) -> str:
    return _join([page_name(u) for u in urls], n)


def _samsung_detail(metric: str, comp: str, value: Optional[float], comp_avg: Optional[float],
                    sblock: Dict[str, Any], cblocks: Dict[str, Dict[str, Any]], who: str = "삼성") -> Optional[Tuple[str, str, bool]]:
    """삼성 세부 지표 하나 → (결론, 할 일). 데이터에서 구체 대상(페이지·속성)을 찾아 넣는다."""
    f = sblock.get("facts") or {}
    v = _pct(value)
    vs = f" (경쟁사 평균 {_pct(comp_avg)})" if comp_avg is not None else ""
    if metric == "data":
        sch = f.get("schema") or {}
        if comp == "Product 완성도":
            miss = ((sch.get("completeness") or {}).get("Product") or {}).get("missing_properties") or []
            if miss:
                return (f"{who} Product 스키마 완성도 {v}, {_join(miss)} 누락", f"PDP Product 스키마에 {_join(miss)} 추가 필요", True)
        if comp == "역할적합성":
            gaps = sch.get("role_alignment_gaps") or []
            by: Dict[Tuple[str, str], List[str]] = {}
            for g in gaps:
                by.setdefault((g.get("page_role") or "", "·".join(g.get("missing") or [])), []).append(g.get("url") or "")
            if by:
                (role, types), urls = max(by.items(), key=lambda kv: len(kv[1]))
                rk = ROLE_KO.get(role, role)
                return (f"{who} {rk} {len(urls)}개 페이지에 {types} 스키마 없음 ({_paths(urls)})", f"{rk}에 {types} 스키마 적용 필요", True)
        if comp == "H-tag":
            iss = [h.get("url") for h in ((f.get("html_structure") or {}).get("heading_issues") or []) if h.get("issue") == "H1 없음"]
            if iss:
                return (f"{who} {len(iss)}개 페이지 H1 없음 ({_paths(iss)})", "해당 페이지에 제품명 H1 추가 필요", True)
        if comp == "Schema":
            return (f"{who} 스키마 적용률 {v}{vs}", "스키마 없는 페이지에 JSON-LD 추가 필요", False)
        if comp == "@id 연결성":
            return (f"{who} @id 연결 {v}{vs}", "Product·Organization 노드에 @id 부여·연결 필요", False)
        if comp == "Structured":
            have = _schema_types(sblock)
            common = set()
            for b in cblocks.values():
                common |= (_schema_types(b) & SCHEMA_MEANINGFUL)
            lack = _by_priority(common - have)
            if lack:
                return (f"{who} 스키마 타입 {len(have)}종, 경쟁사가 쓰는 {_join(lack)} 미적용",
                        f"{SCHEMA_WHERE.get(lack[0], 'PDP')}에 {lack[0]} 스키마 추가 필요", True)
        return None
    if metric == "copy":
        if comp == "Copy richness":
            q = _quant_avg(sblock)
            cq = _avg(_quant_avg(b) for b in cblocks.values())
            qtxt = f", 수치 표현 100단어당 {q}개" + (f" (경쟁사 평균 {cq}개)" if cq is not None else "") if q is not None else ""
            return (f"{who} 카피 구체성 {round(value)}점{qtxt}", "PDP·Buying 카피에 배터리·무게 등 스펙 수치 추가 필요", False)
        if comp == "CTA coverage":
            miss = (f.get("commerce_cta") or {}).get("missing_buy_cta_pages") or []
            urls = [m.get("url") if isinstance(m, dict) else m for m in miss]
            if urls:
                return (f"{who} {len(urls)}개 페이지 구매 CTA 없음 ({_paths(urls)})", "해당 페이지에 Buy/Shop CTA 추가 필요", True)
        if comp == "Word coverage":
            thin = [p.get("url") for p in _copy_pages(sblock) if (p.get("word_count") or 0) < 80]
            if thin:
                return (f"{who} {len(thin)}개 페이지 본문 80단어 미만 ({_paths(thin)})", "해당 페이지에 기능 설명 본문 보강 필요", True)
        if comp == "FAQ 품질":
            return (f"{who} FAQ 품질 {v}{vs}", "FAQ 답변에 가격·조건 등 구체 정보 보강 필요", False)
        if comp == "intent 충족":
            gap = [p.get("url") for p in ((f.get("copy_richness") or {}).get("intent_gap_pages") or [])]
            if gap:
                return (f"{who} {len(gap)}개 페이지 카피 구체성 40점 미만 ({_paths(gap)})", "해당 페이지 카피에 수치·근거 문구 보강 필요", True)
        if comp == "중복 회피":
            dup = [d.get("url") for d in ((f.get("duplication") or {}).get("duplicate_copy_pages") or [])]
            if dup:
                return (f"{who} {len(dup)}개 페이지 같은 문구 반복 ({_paths(dup)})", "반복 문구 정리 필요", True)
        return None
    # visual
    if comp == "ALT ratio":
        gp = [g.get("url") for g in ((f.get("alt_text_quality") or {}).get("gap_pages") or [])]
        where = f", 부족 페이지 {_paths(gp)}" if gp else ""
        return (f"{who} 설명형 ALT {v}{vs}{where}", "제품명·기능이 들어간 설명형 ALT로 교체 필요", False)
    if comp == "Image diversity":
        return (f"{who} 사용 장면 이미지 {v}{vs}", "기능별 사용 장면 이미지 추가 필요", False)
    if comp == "Coverage":
        return (f"{who} 이미지 보유율 {v}{vs}", "이미지 없는 페이지에 제품 이미지 추가 필요", False)
    return None


def _competitor_detail(metric: str, site: str, cblock: Dict[str, Any], sblock: Dict[str, Any]
                       ) -> Optional[Tuple[str, str, int]]:
    """경쟁사가 삼성보다 우세한 지점 → (결론, 할 일, 격차). 우세하지 않으면 None."""
    ct, st = metric_total(metric, cblock), metric_total(metric, sblock)
    if ct is None or st is None:
        return None
    name = site_short(site)
    head = f"{name} {METRIC_EN[metric]} {ct}점"
    # D1 — 스키마 타입: 경쟁사 보유·삼성 미보유
    if metric == "data":
        lack = _by_priority((_schema_types(cblock) - _schema_types(sblock)) & SCHEMA_MEANINGFUL)
        if lack and ct >= st:
            return (f"{head}, 삼성({st}점) 대비 {_join(lack)} 스키마 적용에서 우세",
                    f"삼성 {SCHEMA_WHERE.get(lack[0], 'PDP')}에 {lack[0]} 스키마 추가 필요", max(ct - st, GAP_PP))
    # COPY — 구체적인 격차(전작 비교·근거 문구 → 수치 표현 밀도)를 먼저 본다
    if metric == "copy" and ct >= st:
        ce, se = _evidence_ratio(cblock), _evidence_ratio(sblock)
        if ce is not None and se is not None and ce - se >= GAP_PP:
            return (f"{head}, 삼성({st}점) 대비 전작 비교·근거 문구에서 우세 (보유 페이지 {ce}% vs {se}%)",
                    "삼성 PDP에 전작 대비 개선 수치 문구 추가 필요", ce - se)
        cq, sq = _quant_avg(cblock), _quant_avg(sblock)
        if cq is not None and sq is not None and cq >= max(sq * 1.5, sq + 0.5) and ct - st >= GAP_PP:
            return (f"{head}, 삼성({st}점) 대비 수치 표현에서 우세 (100단어당 {cq}개 vs {sq}개)",
                    "삼성 PDP 카피에 배터리·무게 등 스펙 수치 추가 필요", ct - st)
    cc, sc = metric_components(metric, cblock), metric_components(metric, sblock)
    best = None
    for k, cv in cc.items():
        sv = sc.get(k)
        if cv is None or sv is None or cv - sv < GAP_PP:
            continue
        if best is None or cv - sv > best[2]:
            best = (k, cv, cv - sv, sv)
    if not best or (ct - st < GAP_PP and best[2] < 2 * GAP_PP):
        return None
    k, cv, gap, sv = best
    label = COMP_KO.get(k, k)
    extra = ""
    act = {
        "Schema": "삼성 스키마 미적용 페이지에 JSON-LD 추가 필요",
        "H-tag": "삼성 H1 없는 페이지에 제품명 H1 추가 필요",
        "역할적합성": "삼성 페이지 유형별 핵심 스키마(PF ItemList·PDP Product·Buying Offer) 적용 필요",
        "Product 완성도": "삼성 PDP Product 스키마 누락 속성 추가 필요",
        "@id 연결성": "삼성 Product·Organization 노드 @id 연결 필요",
        "Copy richness": "삼성 PDP 카피에 스펙 수치·혜택 수치 추가 필요",
        "CTA coverage": "삼성 CTA 없는 페이지에 Buy/Shop CTA 추가 필요",
        "Word coverage": "삼성 짧은 페이지에 기능 설명 본문 보강 필요",
        "FAQ 품질": f"{name} FAQ 구성 참고해 삼성 FAQ 답변 구체화 필요",
        "intent 충족": "삼성 구체성 낮은 페이지 카피 보강 필요",
        "중복 회피": "삼성 반복 문구 정리 필요",
        "ALT ratio": "삼성 ALT를 제품명·기능 설명형으로 교체 필요",
        "Image diversity": "삼성 기능별 사용 장면 이미지 추가 필요",
        "Coverage": "삼성 이미지 없는 페이지에 이미지 추가 필요",
    }.get(k, "")
    return (f"{head}, 삼성({st}점) 대비 {label}에서 우세 ({round(cv)}% vs {round(sv)}%){extra}", act, gap)


# ── 변경점(X1) ────────────────────────────────────────────────────
_PRICE_KW = ("price", "$", "₩", "£", "€", "per month", "/mo", "trade-in", "trade in", "financing", "installment",
             "save", "off", "deal", "할부", "보상", "할인", "가격", "buy now", "pre-order", "사전예약")
FIELD_KO = {"body_content": "본문", "h1": "H1", "title": "타이틀", "meta_description": "검색 설명문",
            "canonical_url": "canonical", "schema_type": "스키마", "schema_types": "스키마",
            "schema_props_by_type": "스키마 속성", "ctas": "CTA", "faqs": "FAQ", "images": "이미지",
            "nav": "메뉴", "dom": "페이지 구조"}


def humanize_change_summary(field: str, summary: str) -> str:
    """DB 에 저장된 개발 표기(예: 'body_content 변경 (문장 +3/-13)')를 화면 표기로. [A3]
    과거 수집분도 화면에서 바로 바뀌도록 응답 시점에 변환한다."""
    s = summary or ""
    for k, ko in FIELD_KO.items():
        if s.startswith(k + " ") or s == k:
            rest = s[len(k):].strip()
            m = re.match(r"변경 \(문장 \+(\d+)/-(\d+)\)", rest)
            if m:
                a, r = int(m.group(1)), int(m.group(2))
                parts = ([f"{a}문장 추가"] if a else []) + ([f"{r}문장 삭제"] if r else [])
                return f"{ko} 변경: {', '.join(parts) or '문구 수정'}"
            if rest.startswith("변경 (단어 단위)"):
                return f"{ko} 변경: 단어 수정"
            return f"{ko} {rest}".strip()
    return s


def _change_kind(c: Dict[str, Any]) -> str:
    fld = c.get("field") or ""
    ev = c.get("evidence") or {}
    if fld.startswith("schema"):
        return "schema_added" if ev.get("kind") == "schema_added" else "schema"
    if fld == "body_content":
        added = " ".join(ev.get("sentences_added") or []).lower()
        if any(k in added for k in _PRICE_KW):
            return "price_copy"
        return "body"
    if fld in ("title", "meta_description", "h1"):
        return "meta"
    if fld in ("ctas",):
        return "cta"
    if fld in ("faqs",):
        return "faq"
    if fld in ("images",):
        return "image"
    return "other"


def _sent_counts(c: Dict[str, Any]) -> Tuple[int, int]:
    m = re.search(r"\+(\d+)/-(\d+)", c.get("summary_raw") or c.get("summary") or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"(\d+)문장 추가", c.get("summary") or "")
    m3 = re.search(r"(\d+)문장 삭제", c.get("summary") or "")
    return (int(m2.group(1)) if m2 else 0, int(m3.group(1)) if m3 else 0)


def change_insights(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """경쟁사 변경(High/Medium)을 사이트·유형별로 묶어 '무엇을 바꿨나 → 삼성은 무엇을 비교' 한 줄로. [X1]"""
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for c in changes:
        if c.get("level") not in ("High", "Medium"):
            continue
        groups.setdefault((c.get("site") or "", _change_kind(c)), []).append(c)
    out = []
    for (site, kind), cs in groups.items():
        high = sum(1 for c in cs if c.get("level") == "High")
        urls = list(dict.fromkeys(c.get("url") or "" for c in cs))
        pages = _paths(urls, 3)
        cats = list(dict.fromkeys(CAT_KO.get(_cat(u), "") for u in urls))
        roles = list(dict.fromkeys(ROLE_KO.get(_role(u), "") for u in urls))
        target = f"{'·'.join(c for c in cats if c)} {'·'.join(r for r in roles if r)}".strip() or "동일 유형 페이지"
        name = site_short(site)
        sev = 1 if high else 2
        cnt = f"{len(cs)}건" + (f", High {high}" if high else "")
        if site == "samsung":
            out.append(_ins("X1", sev + 1, f"삼성 {pages} {FIELD_KO.get(cs[0].get('field') or '', '페이지')} 변경 ({cnt})",
                            "의도한 배포인지 담당자 확인 필요", metric=_bucket(cs[0]), site=site))
            continue
        if kind == "schema_added":
            types = _join(list(dict.fromkeys((c.get("evidence") or {}).get("type") or c.get("after") or "" for c in cs)))
            out.append(_ins("X1", sev, f"{name} {pages}에 {types} 스키마 신규 적용 ({cnt})",
                            f"삼성 {target}의 {types} 적용 여부 확인 필요", metric="data", site=site))
        elif kind == "price_copy":
            out.append(_ins("X1", sev, f"{name} {pages} 본문에 가격·혜택 문구 추가 ({cnt})",
                            f"삼성 {target} 가격·혜택 문구 비교 필요", metric="copy", site=site))
        elif kind == "body":
            a = sum(_sent_counts(c)[0] for c in cs)
            r = sum(_sent_counts(c)[1] for c in cs)
            how = "본문 축소 개편" if r > a * 2 and r >= 5 else "본문 확대" if a > r * 2 and a >= 5 else "본문 대폭 변경"
            out.append(_ins("X1", sev, f"{name} {pages} {how} (문장 +{a}/-{r}, {cnt})",
                            f"삼성 {target} 카피 구성 비교 필요", metric="copy", site=site))
        elif kind == "meta":
            out.append(_ins("X1", sev, f"{name} {pages} 타이틀·H1·검색 설명문 변경 ({cnt})",
                            f"삼성 {target} 검색 노출 문구 비교 필요", metric="data", site=site))
        elif kind == "cta":
            out.append(_ins("X1", sev, f"{name} {pages} 구매 CTA 변경 ({cnt})",
                            f"삼성 {target} CTA 문구·위치 비교 필요", metric="copy", site=site))
        elif kind == "faq":
            out.append(_ins("X1", sev, f"{name} {pages} FAQ 변경 ({cnt})",
                            f"삼성 {target} FAQ 질문 구성 비교 필요", metric="copy", site=site))
        elif kind == "image":
            out.append(_ins("X1", sev, f"{name} {pages} 이미지 구성 변경 ({cnt})",
                            f"삼성 {target} 이미지 구성 비교 필요", metric="visual", site=site))
        else:
            out.append(_ins("X1", sev + 1, f"{name} {pages} 구조 변경 ({cnt})", "", metric=_bucket(cs[0]), site=site))
        # 개별 변경 행(우선 확인 목록·변경 표)에서도 같은 할 일을 보여주도록 변경 dict 에 붙인다
        last = out[-1]
        last["urls"] = urls
        for c in cs:
            c["action"] = last["action"]
            c["insight"] = last["line"]
    return out


def _bucket(c: Dict[str, Any]) -> str:
    cat = c.get("category") or ""
    return "data" if cat == "데이터·스키마" else "visual" if cat == "비주얼" else "copy"


def apple_stalker_insights(dcv: Dict[str, Dict[str, Any]], changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """애플스토커 인사이트 묶음.
    top        : 화면 최상단·이메일 요약(최대 3줄) — 가장 큰 경쟁사 변화 1 + 삼성 부족 1~2 + 경쟁사 우세 1
    by_metric  : DATA/COPY/VISUAL 탭·축 카드용 (각 최대 3줄)
    by_site    : 사이트 카드용 (사이트별 최대 2줄)
    changes    : 변경 액션 표용 (사이트·유형 묶음)
    """
    dcv = dcv or {}
    out_metric: Dict[str, List[Dict[str, Any]]] = {}
    by_site: Dict[str, List[Dict[str, Any]]] = {}
    by_site_metric: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    samsung_all: List[Dict[str, Any]] = []
    comp_all: List[Dict[str, Any]] = []
    sites = set()
    for m in ("data", "copy", "visual"):
        sites |= set((dcv.get(m) or {}).keys())
    for m in ("data", "copy", "visual"):
        blocks = dcv.get(m) or {}
        sblock = blocks.get("samsung")
        cblocks = {s: b for s, b in blocks.items() if s != "samsung"}
        items: List[Dict[str, Any]] = []
        if sblock is not None and metric_total(m, sblock) is not None:
            sc = metric_components(m, sblock)
            comp_avg = {k: _avg(metric_components(m, b).get(k) for b in cblocks.values()) for k in sc}
            for k, v in sc.items():
                if v is None:
                    continue
                ca = comp_avg.get(k)
                weak = v < WEAK_BELOW
                behind = ca is not None and ca - v >= GAP_PP
                if not (weak or behind):
                    continue
                det = _samsung_detail(m, k, v, ca, sblock, cblocks)
                if not det:
                    continue
                kind = "열세" if behind else "부족"
                # 점수형 문장(예: '삼성 설명형 ALT 54% (경쟁사 평균 70%)')에만 상태어를 붙인다.
                # 대상이 특정된 문장(누락·없음·반복…)은 그 자체가 상태라 덧붙이지 않는다.
                text = det[0] if det[2] else f"{det[0]}로 {kind}"
                sev = 1 if v < 40 else 2
                it = _ins(f"{m[0].upper()}-{k}", sev, text, det[1], metric=m, site="samsung", value=v, comp_avg=ca)
                items.append(it)
            # 삼성 자체 세부 지표가 양호해도 경쟁사가 쓰는 스키마 타입이 없으면 D1 성격으로 1줄
            if m == "data":
                det = _samsung_detail("data", "Structured", None, None, sblock, cblocks)
                if det and not any(i["rule"] == "D-Structured" for i in items):
                    items.append(_ins("D-Structured", 2, det[0], det[1], metric=m, site="samsung"))
        samsung_all += items
        by_site.setdefault("samsung", []).extend(items)
        for s, b in cblocks.items():
            if sblock is None:
                continue
            if metric_total(m, b) is None:
                continue
            det = _competitor_detail(m, s, b, sblock)
            if det:
                it = _ins("D1" if m == "data" else "C-adv" if m == "copy" else "V-adv", 2, det[0], det[1],
                          metric=m, site=s, gap=det[2])
                comp_all.append(it)
                by_site.setdefault(s, []).append(it)
                items.append(it)
        for it in items:
            by_site_metric.setdefault(it["site"], {}).setdefault(m, []).append(it)
        out_metric[m] = _top(items)

    # 사이트 카드: 근거 없음 / 삼성보다 전 영역 낮음
    for s in sites:
        if s == "samsung":
            continue
        totals = [metric_total(m, (dcv.get(m) or {}).get(s)) for m in ("data", "copy", "visual")]
        if all(t is None for t in totals):
            by_site[s] = [_ins("E0", 3, f"{site_short(s)} 수집 근거 없음", "URL·렌더링 상태 확인 필요", site=s)]
        elif not by_site.get(s):
            by_site[s] = [_ins("E1", 3, f"{site_short(s)} 삼성보다 전 영역 낮거나 비슷", "참고 불필요", site=s)]
    for s in list(by_site):
        by_site[s] = _top(by_site[s], 2)

    ch = change_insights(changes or [])
    top: List[Dict[str, Any]] = []
    comp_ch = sorted([c for c in ch if c["site"] != "samsung"], key=lambda x: x["sev"])
    if comp_ch:
        top.append(comp_ch[0])
    top += _top(samsung_all, 2 if comp_ch else 2)
    if len(top) < MAX_LINES and comp_all:
        top.append(sorted(comp_all, key=lambda x: -x.get("gap", 0))[0])
    for m, lst in out_metric.items():
        extra = [c for c in ch if c["metric"] == m]
        out_metric[m] = _top(lst + extra) if not lst else lst
    for s_, mm in by_site_metric.items():
        for m_ in mm:
            mm[m_] = _top(mm[m_], 2)
    return {"top": _top(top), "by_metric": out_metric, "by_site": by_site, "by_site_metric": by_site_metric,
            "changes": ch, "basis": BASIS_SCORE}


def page_insights(page_url: str, blocks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """[2026-11 A10] 페이지 1개 상세 패널용 — 같은 룰을 페이지 facts 에 적용(비교 대상 없이 절대 기준 70점만)."""
    try:
        from config import site_key_for_url
        who = site_short(site_key_for_url(page_url) or "")
    except Exception:
        who = "이 페이지"
    out: Dict[str, List[Dict[str, Any]]] = {}
    for m in ("data", "copy", "visual"):
        b = blocks.get(m) or {}
        items = []
        for k, v in metric_components(m, b).items():
            if v is None or v >= WEAK_BELOW:
                continue
            det = _samsung_detail(m, k, v, None, b, {}, who=who)
            if det:
                items.append(_ins(f"P-{k}", 1 if v < 40 else 2, det[0] if det[2] else f"{det[0]}로 부족", det[1], metric=m))
        out[m] = _top(items)
    return {"by_metric": out, "basis": f"판단 기준: {WEAK_BELOW}점 미만 = 부족 (이 페이지 단독 기준)"}


# ════════════════════════════════════════════════════════════════
# 메일 본문용 HTML (애플스토커·큐비·honeyComb 메일이 공유) — 화면 InsightBox 와 같은 모양
# ════════════════════════════════════════════════════════════════
_SEV_DOT_HTML = {1: "#D8362F", 2: "#E0A008", 3: "#98A2B3"}


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def email_line_html(it: Dict[str, Any]) -> str:
    dot = _SEV_DOT_HTML.get(it.get("sev", 3), "#98A2B3")
    act = (" <span style='color:#98A2B3'>→</span> <b style='color:#1B4FD8'>" + _esc(it["action"]) + "</b>") if it.get("action") else ""
    return ("<div style='font-size:12.5px;color:#344054;line-height:1.6;margin:3px 0'>"
            "<span style='display:inline-block;width:7px;height:7px;border-radius:50%;background:" + dot +
            ";margin-right:7px;vertical-align:middle'></span>" + _esc(it["text"]) + act + "</div>")


def email_box_html(items: Optional[List[Dict[str, Any]]], basis: str = "", title: str = "",
                   empty: str = "") -> str:
    items = list(items or [])[:MAX_LINES]
    if not items and not empty:
        return ""
    body = "".join(email_line_html(i) for i in items) if items else \
        "<div style='font-size:12.5px;color:#667085'>" + _esc(empty) + "</div>"
    head = ("<div style='font-size:13px;font-weight:700;color:#101318;margin:0 0 6px'>" + _esc(title) + "</div>") if title else ""
    foot = ("<div style='font-size:10.5px;color:#98A2B3;margin-top:6px;border-top:1px dashed #EAECF0;padding-top:5px'>"
            + _esc(basis) + "</div>") if basis else ""
    return ("<div style='background:#F7F9FC;border:1px solid #EAECF0;border-radius:10px;padding:12px 14px;margin:0 0 14px'>"
            + head + body + foot + "</div>")

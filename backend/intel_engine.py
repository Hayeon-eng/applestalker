"""
Intel Engine — DATA / COPY / VISUAL 3분류 분석 (할루시네이션 차단형)
================================================================
요구사항 1.1~1.5 반영:
  - 모든 분석 결과는 DATA / COPY / VISUAL 3개 카테고리로 "중복 없이" 분리.
  - 각 인사이트는 정확히 하나의 카테고리에만 귀속.
  - Schema 완결성은 단일 페이지가 아니라 "플랫폼 단위" — 페이지 간 @id 연결성
    (Samsung 식 linked schema vs Apple 식 inline 임베딩)을 기준으로 판단.

원칙(기존 유지):
  1) LLM 에는 "이번 크롤에서 실제로 추출된 데이터"만 컨텍스트로 준다.
  2) 비교 분석은 두 사이트 데이터가 모두 있을 때만 수행.
  3) 모든 인사이트는 evidence(url+field+실제값)에 바인딩.
  4) 출력은 엄격한 JSON. 파싱 실패 시 규칙기반 fallback.
  5) 규칙기반 facts는 LLM 유무와 무관하게 항상 계산 — 핵심 사실은 AI 없이도 100% 정확.
"""

from __future__ import annotations
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
    _GENAI = True
except Exception:
    _GENAI = False


# ════════════════════════════════════════════════════════════════
# 공통 유틸
# ════════════════════════════════════════════════════════════════

def _s(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _template_key(url: str) -> str:
    """URL 경로의 첫 세그먼트를 '템플릿' 단위로 취급 (숫자/슬러그는 # 처리)."""
    try:
        after_host = url.split("//", 1)[-1]
        path = after_host.split("/", 1)[1] if "/" in after_host else ""
    except Exception:
        path = ""
    path = path.strip("/")
    if not path:
        return "홈"
    seg = path.split("/")[0]
    seg = re.sub(r"\d+", "#", seg)
    return seg or "홈"


def _expected_schema_type(url: str) -> Optional[str]:
    """URL 패턴 기반 '이 페이지엔 이 schema가 있어야 한다' 휴리스틱 (Alignment 판단용)."""
    u = url.lower().rstrip("/")
    after_host = u.split("//", 1)[-1]
    depth = after_host.count("/")
    if depth <= 1:
        return "WebSite"
    if "faq" in u:
        return "FAQPage"
    if any(k in u for k in ("galaxy-", "iphone", "smartphone", "product", "/buy", "macbook", "ipad", "watch")):
        return "Product"
    return None


def _walk_schema_nodes(sd: Any) -> List[Dict[str, Any]]:
    """JSON-LD 리스트에서 @graph 까지 펼친 평탄화 노드 리스트."""
    nodes: List[Dict[str, Any]] = []

    def add(n):
        if not isinstance(n, dict):
            return
        nodes.append(n)
        for g in (n.get("@graph") or []):
            add(g)

    for item in (sd or []):
        add(item)
    return nodes


def _node_types(n: Dict[str, Any]) -> List[str]:
    t = n.get("@type")
    if isinstance(t, list):
        return [str(x) for x in t]
    return [str(t)] if t else []


# 카테고리별 필수 속성 (없으면 '완결성 미흡'으로 판단)
REQUIRED_PROPS = {
    "Product": ["name", "image", "description", "brand", "offers", "aggregateRating", "review"],
    "FAQPage": ["mainEntity"],
    "Organization": ["name", "url", "logo", "sameAs"],
    "BreadcrumbList": ["itemListElement"],
    "WebSite": ["name", "url"],
}
PROP_KO = {
    "aggregateRating": "aggregateRating(평점)", "offers": "offers(가격/재고)",
    "review": "review(리뷰)", "brand": "brand(브랜드)", "image": "image(이미지)",
    "description": "description(설명)", "name": "name(이름)", "logo": "logo(로고)",
    "sameAs": "sameAs(SNS 연결)", "url": "url", "mainEntity": "mainEntity(FAQ 본문)",
    "itemListElement": "itemListElement(목록)",
}


# ════════════════════════════════════════════════════════════════
# DATA — Schema(플랫폼 단위 Qid 연결성) + HTML 구조 + Meta + H-tag
# ════════════════════════════════════════════════════════════════

def data_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(pages)
    pages_with_schema = 0
    type_counts: Dict[str, int] = {}
    template_buckets: Dict[str, Dict[str, int]] = {}
    all_nodes: List[Any] = []          # (url, node)
    id_index: Dict[str, Any] = {}      # "@id" -> (url, node)

    for p in pages:
        url = p.get("url", "")
        sd = p.get("structured_data") or []
        nodes = _walk_schema_nodes(sd)
        tmpl = _template_key(url)
        b = template_buckets.setdefault(tmpl, {"pages": 0, "with_schema": 0})
        b["pages"] += 1
        if nodes:
            pages_with_schema += 1
            b["with_schema"] += 1
        for n in nodes:
            for t in _node_types(n):
                type_counts[t] = type_counts.get(t, 0) + 1
            nid = n.get("@id")
            if nid:
                id_index[nid] = (url, n)
            all_nodes.append((url, n))

    # ── @id 연결성(Qid) 스캔: 다른 노드 안에서 이 @id 가 참조되는가 ──
    referenced_ids = set()
    for _, n in all_nodes:
        for k, v in n.items():
            if k == "@id":
                continue
            if isinstance(v, dict) and "@id" in v and v["@id"] in id_index:
                referenced_ids.add(v["@id"])
            elif isinstance(v, str) and v in id_index:
                referenced_ids.add(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and item.get("@id") in id_index:
                        referenced_ids.add(item["@id"])
                    elif isinstance(item, str) and item in id_index:
                        referenced_ids.add(item)

    isolated_ids = set(id_index.keys()) - referenced_ids
    if id_index:
        linkage_pattern = "Linked(@id 기반 연결형)" if referenced_ids else "Inline(개별 페이지 임베딩형)"
    else:
        linkage_pattern = "스키마 없음"

    # ── Completeness: 타입별 필수 속성 충족률 ──
    completeness: Dict[str, Any] = {}
    for typ, req in REQUIRED_PROPS.items():
        matching = [n for _, n in all_nodes if typ in _node_types(n)]
        if not matching:
            continue
        missing_counter: Dict[str, int] = {}
        for n in matching:
            for prop in req:
                if not n.get(prop):
                    missing_counter[prop] = missing_counter.get(prop, 0) + 1
        filled_ratio = 1 - (sum(missing_counter.values()) / (len(matching) * len(req)))
        completeness[typ] = {
            "instances": len(matching),
            "filled_ratio": round(filled_ratio, 2),
            "missing_properties": sorted(missing_counter.keys(), key=lambda k: -missing_counter[k]),
        }

    # ── Distribution: 템플릿(페이지 유형)별 schema 적용 고르기 ──
    distribution = {
        tmpl: {"pages": b["pages"], "with_schema": b["with_schema"],
               "coverage_pct": round(b["with_schema"] / b["pages"] * 100, 1) if b["pages"] else 0}
        for tmpl, b in template_buckets.items()
    }

    # ── Alignment: 페이지 목적과 schema 타입 불일치 ──
    mismatches = []
    for p in pages:
        url = p.get("url", "")
        nodes = _walk_schema_nodes(p.get("structured_data") or [])
        found_types = {t for n in nodes for t in _node_types(n)}
        expected = _expected_schema_type(url)
        if expected and expected not in found_types:
            mismatches.append({"url": url, "expected": expected, "found": sorted(found_types) or ["없음"]})

    # ── HTML 구조: heading depth, semantic 비율(nav 보유율), p-tag 활용(=본문 비율) ──
    heading_issues = []
    semantic_pages = 0
    for p in pages:
        h1 = p.get("h1")
        h2 = p.get("h2") or []
        h3 = p.get("h3") or []
        if not h1:
            heading_issues.append({"url": p.get("url"), "issue": "H1 없음"})
        if h3 and not h2:
            heading_issues.append({"url": p.get("url"), "issue": "H2 없이 H3만 존재 (depth 불연속)"})
        nav = p.get("navigation") or {}
        if (nav.get("main") or []):
            semantic_pages += 1

    # ── Meta 상태 ──
    missing_meta = [p.get("url") for p in pages if not _s(p.get("meta_description")).strip()]
    missing_title = [p.get("url") for p in pages if not _s(p.get("title")).strip()]

    return {
        "schema": {
            "coverage_pct": round(pages_with_schema / total * 100, 1) if total else 0,
            "pages_with_schema": pages_with_schema, "total_pages": total,
            "schema_type_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
            "distribution": distribution,
            "completeness": completeness,
            "alignment_mismatches": mismatches[:10],
            "id_linkage": {
                "total_id_nodes": len(id_index),
                "linked_ids": len(referenced_ids),
                "isolated_ids": len(isolated_ids),
                "linkage_pattern": linkage_pattern,
            },
        },
        "html_structure": {
            "semantic_nav_pages": semantic_pages,
            "heading_issues": heading_issues[:10],
            "pages_missing_meta_description": missing_meta[:10],
            "pages_missing_title": missing_title[:10],
        },
    }


def _narrate_schema_completeness(schema: Dict[str, Any]) -> List[str]:
    """규칙기반 자연어 서술 — 'Schema 완결성 전반적으로 우수하나 aggregateRating 누락' 패턴."""
    lines = []
    cov = schema["coverage_pct"]
    if cov >= 80:
        base = f"Schema 적용 범위는 전체 페이지의 {cov}%로 우수"
    elif cov >= 40:
        base = f"Schema 적용 범위는 전체 페이지의 {cov}%로 부분적"
    else:
        base = f"Schema 적용 범위는 전체 페이지의 {cov}%로 미흡"

    for typ, c in schema["completeness"].items():
        if c["missing_properties"]:
            missing_ko = ", ".join(PROP_KO.get(m, m) for m in c["missing_properties"][:3])
            ratio_pct = round(c["filled_ratio"] * 100)
            if ratio_pct >= 70:
                lines.append(f"{base}하나, {typ} 스키마는 {missing_ko} 등 상세 속성 누락 (충족률 {ratio_pct}%)")
            else:
                lines.append(f"{typ} 스키마 완결성 미흡 — {missing_ko} 등 다수 속성 누락 (충족률 {ratio_pct}%)")
        else:
            lines.append(f"{typ} 스키마는 필수 속성을 빠짐없이 충족")

    # [재정립] @id 연결성은 '구조적 특성'으로만 서술. Linked=좋음/Inline=나쁨이 아니라
    # 사이트가 어떤 스키마 아키텍처를 택했는지를 보여주는 참고 정보일 뿐 — 점수화하지 않음.
    lk = schema["id_linkage"]
    if lk["total_id_nodes"]:
        if lk["linkage_pattern"].startswith("Linked"):
            lines.append(f"스키마 아키텍처: @id 기반 연결형(Linked) — {lk['linked_ids']}/{lk['total_id_nodes']}개 노드가 "
                         f"상호 참조됨. (참고: 연결형 자체가 우열 기준은 아니며, 완결성은 위 충족률로 별도 판단)")
        else:
            lines.append(f"스키마 아키텍처: 개별 페이지 인라인 임베딩형(Inline) — {lk['total_id_nodes']}개 @id 노드가 "
                         f"페이지별로 독립 적용됨. (참고: 임베딩형 자체가 열위 기준은 아니며, 완결성은 위 충족률로 별도 판단)")

    if not lines:
        lines.append(base)
    return lines


# ════════════════════════════════════════════════════════════════
# COPY — 콘텐츠 밀도 / FAQ 질 / 카피 풍부성 / intent fulfillment
# ════════════════════════════════════════════════════════════════

def _density_tier(wc: int) -> str:
    if wc < 150:
        return "빈약(thin, <150)"
    if wc < 400:
        return "경량(light, 150~400)"
    if wc < 800:
        return "적정(moderate, 400~800)"
    return "풍부(rich, 800+)"


COMPARISON_KW = ("비교", "vs", "차이", "compared", "versus")
EVIDENCE_KW = ("스펙", "사양", "spec", "성능", "테스트", "research", "benchmark")

# 정량 클레임 탐지: 숫자+단위 패턴 (스펙/가격/용량 등 '구체적 근거'의 대리 지표)
QUANT_UNIT_RE = re.compile(
    r"\d+(\.\d+)?\s?(GB|TB|MB|MP|mAh|mm|cm|kg|g|%|원|만원|시간|분|배|개|fps|nit|Hz|인치|inch)",
    re.IGNORECASE,
)
# 100단어당 정량표현 몇 개면 만점(100점)으로 칠지 — 임계값. 과도한 나열은 cap.
QUANT_TARGET_PER_100W = 3.0

# 카피 풍부성 = 4개 하위지표 가중합산. 가중치 명시(투명성 확보용, 합 1.0).
COPY_RICHNESS_WEIGHTS = {"quant": 0.35, "structure": 0.25, "evidence_kw": 0.20, "faq_presence": 0.20}
COPY_RICHNESS_TIERS = [(70, "우수"), (40, "보통"), (0, "미흡")]

# FAQ 품질 = 3개 하위지표 가중합산. 가중치 명시(합 1.0).
FAQ_SCORE_WEIGHTS = {"specificity": 0.4, "question_realism": 0.3, "citability": 0.3}
FAQ_QUESTION_PARTICLES = ("나요", "까요", "인가요", "입니까", "어떻게", "무엇", "왜", "언제", "어디", "얼마",
                          "how", "what", "why", "when", "where", "does", "is it", "can i")


def _tier(score: float, tiers=COPY_RICHNESS_TIERS) -> str:
    for th, label in tiers:
        if score >= th:
            return label
    return tiers[-1][1]


def _faq_item_score(question: str, answer: str) -> Dict[str, Any]:
    """FAQ 1문항 품질 점수 (0~100). 가중치: 구체성40 / 질문현실성30 / AI인용적합성30."""
    q, a = _s(question).strip(), _s(answer).strip()

    specificity = 1.0 if QUANT_UNIT_RE.search(a) else 0.0

    q_lower = q.lower()
    question_realism = 1.0 if (len(q) >= 8 and (q.rstrip().endswith("?") or
                               any(p in q_lower for p in FAQ_QUESTION_PARTICLES))) else 0.0

    first_sentence = re.split(r"(?<=[.!?。])\s|\n", a, maxsplit=1)[0] if a else ""
    citability = 1.0 if 20 <= len(first_sentence) <= 180 else 0.0

    score = (specificity * FAQ_SCORE_WEIGHTS["specificity"]
             + question_realism * FAQ_SCORE_WEIGHTS["question_realism"]
             + citability * FAQ_SCORE_WEIGHTS["citability"]) * 100
    return {"score": round(score, 1), "specificity": bool(specificity),
            "question_realism": bool(question_realism), "citability": bool(citability)}


def copy_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    density_dist: Dict[str, int] = {}
    thin_pages, rich_pages = [], []
    faq_page_results = []
    richness_pages = []
    intent_gap_pages = []
    all_richness_pages = []

    for p in pages:
        wc = max(p.get("word_count") or 0, 1)
        tier = _density_tier(wc)
        density_dist[tier] = density_dist.get(tier, 0) + 1
        if wc < 150:
            thin_pages.append(p.get("url"))
        if wc >= 800:
            rich_pages.append(p.get("url"))

        body = p.get("body_content") or ""
        body_lower = body.lower()
        has_comparison = any(k in body_lower for k in COMPARISON_KW)
        has_evidence = any(k in body_lower for k in EVIDENCE_KW)
        faqs = p.get("faqs") or []
        has_faq = bool(faqs)
        h2 = p.get("h2") or []
        h3 = p.get("h3") or []
        has_cta = bool(p.get("ctas") or [])

        # ── 정량지표: 100단어당 숫자+단위 출현 빈도 (cap 후 0~100 스케일) ──
        quant_count = len(list(QUANT_UNIT_RE.finditer(body)))
        quant_per_100w = quant_count / wc * 100
        quant_score = min(quant_per_100w / QUANT_TARGET_PER_100W, 1.0) * 100

        # ── 구조지표: H2 보유 / H3 고립(H2 없이 H3만) 여부 / CTA / FAQ 4요소 ──
        structure_components = [bool(h2), not (h3 and not h2), has_cta, has_faq]
        structure_score = sum(structure_components) / len(structure_components) * 100

        evidence_kw_score = 100.0 if (has_comparison or has_evidence) else 0.0
        faq_presence_score = 100.0 if has_faq else 0.0

        richness = (quant_score * COPY_RICHNESS_WEIGHTS["quant"]
                    + structure_score * COPY_RICHNESS_WEIGHTS["structure"]
                    + evidence_kw_score * COPY_RICHNESS_WEIGHTS["evidence_kw"]
                    + faq_presence_score * COPY_RICHNESS_WEIGHTS["faq_presence"])

        entry = {
            "url": p.get("url"), "score": round(richness, 1), "tier": _tier(richness),
            "word_count": wc, "quant_count": quant_count, "quant_per_100w": round(quant_per_100w, 2),
            "quant_score": round(quant_score, 1), "structure_score": round(structure_score, 1),
            "has_comparison": has_comparison, "has_evidence_keyword": has_evidence,
            "has_faq": has_faq, "h2_count": len(h2), "cta_count": len(p.get("ctas") or []),
        }
        all_richness_pages.append(entry)
        if richness >= 70:
            richness_pages.append(entry)
        if richness < 40:
            intent_gap_pages.append(entry)

        # ── FAQ 품질: 문항별 가중점수 → 페이지 평균 ──
        item_scores = []
        for faq in faqs:
            main_entity = faq.get("mainEntity") if isinstance(faq, dict) else None
            items = main_entity if isinstance(main_entity, list) else ([main_entity] if main_entity else [])
            for it in items:
                if not isinstance(it, dict):
                    continue
                q_text = it.get("name") or ""
                ans = ((it.get("acceptedAnswer") or {}).get("text") or "") if isinstance(it.get("acceptedAnswer"), dict) else ""
                item_scores.append(_faq_item_score(q_text, ans))
        if item_scores:
            avg = sum(s["score"] for s in item_scores) / len(item_scores)
            faq_page_results.append({"url": p.get("url"), "items": len(item_scores),
                                     "avg_score": round(avg, 1), "tier": _tier(avg),
                                     "weak_items": sum(1 for s in item_scores if s["score"] < 40)})

    return {
        "content_density": {
            "distribution": density_dist,
            "thin_pages": thin_pages[:10],
            "rich_pages": rich_pages[:10],
        },
        "copy_richness": {
            "weights": COPY_RICHNESS_WEIGHTS,
            "all_pages": sorted(all_richness_pages, key=lambda x: x["score"]),
            "rich_pages": sorted(richness_pages, key=lambda x: -x["score"])[:10],
            "intent_gap_pages": sorted(intent_gap_pages, key=lambda x: x["score"])[:10],
        },
        "faq": {
            "weights": FAQ_SCORE_WEIGHTS,
            "pages_with_faq": len(faq_page_results),
            "total_items": sum(x["items"] for x in faq_page_results),
            "detail": sorted(faq_page_results, key=lambda x: x["avg_score"])[:10],
        },
    }


# ════════════════════════════════════════════════════════════════
# VISUAL — 이미지 다양성 / lifestyle 비율 / 편중도 / 스토리텔링
# ════════════════════════════════════════════════════════════════

LIFESTYLE_KW = (
    "lifestyle", "life", "people", "family", "outdoor", "hand", "hands", "person", "scene", "moment",
    "woman", "man", "girl", "boy", "couple", "portrait", "selfie", "using", "usecase", "daily",
    "travel", "gaming", "workout", "kitchen", "home", "office", "night", "camera-sample",
    "라이프", "사람", "가족", "손", "일상", "야외", "사용", "여행", "셀피", "게임",
)
PRODUCT_KW = (
    "product", "device", "render", "studio", "front", "back", "angle", "colorway", "spec", "gallery",
    "kv", "keyvisual", "key-visual", "design", "color", "colors", "exclusive", "carousel",
    "galaxy", "iphone", "ipad", "macbook", "watch", "buds", "airpods", "phone", "smartphone", "tablet",
    "fold", "flip", "ultra", "plus", "edge", "s25", "s24", "z-fold", "z-flip",
    "제품", "기기", "스펙", "색상", "디자인", "갤럭시", "워치", "버즈",
)
# alt 텍스트가 비어있지 않아도 의미 없는 placeholder 인 경우가 많아 별도 필터링
GENERIC_ALT_WORDS = ("image", "photo", "picture", "img", "banner", "icon", "사진", "이미지", "배너", "아이콘")
ALT_RICH_MIN_LEN = 15   # 이 길이 이상 + generic 단어 아니면 '설명적'으로 분류


def _classify_image(img: Dict[str, Any], page_url: str = "") -> str:
    alt = _s(img.get("alt")).lower()
    src = _s(img.get("src")).lower()
    blob = f"{alt} {src}"

    lifestyle_hit = any(k in blob for k in LIFESTYLE_KW)
    product_hit = any(k in blob for k in PRODUCT_KW)

    # Samsung CDN/페이지는 alt가 브랜드·모델명 위주인 경우가 많아 product 신호를 넓게 잡는다.
    # 단, 사람/손/사용 장면 신호가 있으면 lifestyle을 우선한다.
    if lifestyle_hit:
        return "lifestyle"
    if product_hit:
        return "product"

    # 파일명만으로도 제품 컷임을 알 수 있는 패턴
    if re.search(r"(?:^|[-_/])(kv|pf|pdp|gallery|design|color|spec|front|back|device)(?:[-_/]|\.)", blob):
        return "product"
    if re.search(r"(?:galaxy|samsung|iphone|ipad|macbook|watch|buds|airpods)", page_url.lower() + " " + blob):
        return "product"
    return "unclassified"


def _alt_quality(img: Dict[str, Any]) -> str:
    """alt 텍스트 품질만 별도 지표로 — 분류(product/lifestyle)와 독립적으로 평가.
    비용 0(텍스트 길이/제네릭 단어 체크)이며, 실제 이미지 시각 내용 분석은 아님(한계 명시)."""
    alt = _s(img.get("alt")).strip()
    if not alt:
        return "비어있음"
    alt_lower = alt.lower()
    if len(alt) < ALT_RICH_MIN_LEN or any(w == alt_lower or w in alt_lower.split() for w in GENERIC_ALT_WORDS):
        return "일반적"
    return "설명적"


def visual_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_images = 0
    lifestyle = 0
    product = 0
    unclassified = 0
    alt_desc = alt_generic = alt_empty = 0
    per_page_counts = []
    storytelling_pages = []
    image_heavy_pages = []
    all_srcs: List[str] = []
    all_alts: List[str] = []

    for p in pages:
        imgs = p.get("images") or []
        n = len(imgs)
        total_images += n
        per_page_counts.append(n)
        page_types = set()
        alt_rich = 0
        for img in imgs:
            cls = _classify_image(img, p.get("url", ""))
            page_types.add(cls)
            if cls == "lifestyle":
                lifestyle += 1
            elif cls == "product":
                product += 1
            else:
                unclassified += 1

            aq = _alt_quality(img)
            if aq == "설명적":
                alt_desc += 1; alt_rich += 1
            elif aq == "일반적":
                alt_generic += 1
            else:
                alt_empty += 1

            src = _s(img.get("src")).strip()
            if src:
                all_srcs.append(src)
            alt_txt = _s(img.get("alt")).strip()
            if alt_txt:
                all_alts.append(alt_txt)

        if n >= 6:
            image_heavy_pages.append({"url": p.get("url"), "count": n})
        if {"lifestyle", "product"}.issubset(page_types) and alt_rich >= 2:
            storytelling_pages.append(p.get("url"))

    avg = (sum(per_page_counts) / len(per_page_counts)) if per_page_counts else 0
    max_count = max(per_page_counts) if per_page_counts else 0
    concentration = round((max_count / total_images) * 100, 1) if total_images else 0

    # ── 이미지 자체 다양성(저비용 대리지표): 같은 이미지가 여러 페이지에 재사용되는지(src 중복),
    #    alt 문구가 천편일률적인지(alt 중복). Vision 분석이 아니라 '템플릿 재사용도' 추정치임을 명시.
    unique_src_ratio = round(len(set(all_srcs)) / len(all_srcs) * 100, 1) if all_srcs else 0
    unique_alt_ratio = round(len(set(all_alts)) / len(all_alts) * 100, 1) if all_alts else 0

    return {
        "image_diversity": {
            "_note": "alt/src/파일명/페이지 URL 텍스트 기반 분류. Vision 분석은 아니지만 Samsung 모델명·KV·gallery 패턴을 제품 이미지로 인식하도록 보강.",
            "total_images": total_images,
            "product": product, "lifestyle": lifestyle, "unclassified": unclassified,
            "lifestyle_ratio_pct": round(lifestyle / total_images * 100, 1) if total_images else 0,
        },
        "alt_text_quality": {
            "_note": "alt 텍스트 길이/제네릭 단어 기반 판정. 실제 이미지 시각 내용 분석(Vision)은 아님.",
            "설명적": alt_desc, "일반적": alt_generic, "비어있음": alt_empty,
            "descriptive_ratio_pct": round(alt_desc / total_images * 100, 1) if total_images else 0,
        },
        "image_uniqueness": {
            "_note": "src/alt 중복도 기반 추정치. 같은 이미지·문구 재사용(템플릿화) 정도를 가늠하는 보조지표.",
            "unique_src_ratio_pct": unique_src_ratio,
            "unique_alt_ratio_pct": unique_alt_ratio,
        },
        "concentration": {
            "avg_per_page": round(avg, 1),
            "max_single_page_pct": concentration,   # 한 페이지에 몰린 비중 — 높을수록 편중
            "image_heavy_pages": image_heavy_pages[:10],
        },
        "storytelling": {
            "pages_with_storytelling": storytelling_pages[:10],
            "count": len(storytelling_pages),
        },
    }


# ════════════════════════════════════════════════════════════════
# IntelEngine — DATA/COPY/VISUAL 출력 + LLM 보강(옵션)
# ════════════════════════════════════════════════════════════════

class IntelEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.model = None
        self.ready = False
        if _GENAI and self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.ready = True
            except Exception as e:
                print(f"[intel] gemini init failed: {e}")

    def is_available(self) -> bool:
        return self.ready

    # ── 메인: 한 사이트의 DATA/COPY/VISUAL 분석 (근거기반) ──────

    def analyze_site(
        self,
        site_display: str,
        is_ours: bool,
        pages: List[Dict[str, Any]],
        change_events: List[Dict[str, Any]],
        max_level: str = "L0",
    ) -> Dict[str, Any]:
        d_facts = data_facts(pages)
        c_facts = copy_facts(pages)
        v_facts = visual_facts(pages)

        data_block = self._build_category("DATA", site_display, is_ours, d_facts,
                                            _narrate_schema_completeness(d_facts["schema"]),
                                            [e for e in change_events if self._bucket(e) == "DATA"])
        copy_block = self._build_category("COPY", site_display, is_ours, c_facts,
                                           self._narrate_copy(c_facts),
                                           [e for e in change_events if self._bucket(e) == "COPY"])
        visual_block = self._build_category("VISUAL", site_display, is_ours, v_facts,
                                             self._narrate_visual(v_facts),
                                             [e for e in change_events if self._bucket(e) == "VISUAL"])

        return {
            "summary": f"{site_display} {len(pages)}개 페이지 분석 (DATA/COPY/VISUAL). "
                       f"변화 {len(change_events)}건.",
            "data": data_block,
            "copy": copy_block,
            "visual": visual_block,
            "_evidence_bound": True,
        }

    def _bucket(self, e: Dict[str, Any]) -> str:
        """변경 이벤트를 DATA/COPY/VISUAL 중 정확히 하나로 귀속 (중복 금지)."""
        ct = e.get("change_type") or e.get("field_name") or ""
        field = e.get("field_name") or ""
        if ct == "visual" or field in ("screenshot", "image"):
            return "VISUAL"
        if ct in ("technical", "navigation") or field in ("schema_type", "dom", "canonical_url"):
            return "DATA"
        return "COPY"   # content, commerce(가격 텍스트) 포함

    def _rule_actions(self, is_ours: bool, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """LLM 없이도 변화 등급에 맞춘 액션을 생성한다."""
        if not events:
            return [{"action": "정기 모니터링 유지", "priority": "low", "evidence_url": "(집계)"}]
        rank = {"L5": 5, "L4": 4, "L3": 3, "L2": 2, "L1": 1, "L0": 0}
        top = sorted(events, key=lambda e: rank.get(e.get("severity_level") or "L0", 0), reverse=True)[:5]
        out = []
        for e in top:
            lv = e.get("severity_level") or "L0"
            if lv in ("L5", "L4"):
                action = "즉시 변경사항 확인 및 대응 필요" if is_ours else "경쟁사 핵심 변경 즉시 확인 및 당사 영향 검토"
                priority = "high"
            elif lv in ("L3", "L2"):
                action = "지속 모니터링 및 필요 시 후속 점검" if is_ours else "경쟁사 변화 지속 모니터링"
                priority = "medium"
            else:
                action = "참고용 기록 유지 및 다음 수집에서 재확인"
                priority = "low"
            out.append({"action": action, "priority": priority, "evidence_url": e.get("url")})
        return out

    def _build_category(self, name, site_display, is_ours, facts, narrative_lines, events) -> Dict[str, Any]:
        insights = [{"point": line, "evidence_url": "(집계)", "evidence": name} for line in narrative_lines]
        for e in events[:8]:
            insights.append({"point": e.get("summary"), "evidence_url": e.get("url"),
                             "evidence": f"{e.get('field_name')} [{e.get('severity_level')}]"})
        rule_actions = self._rule_actions(is_ours, events)

        if self.ready:
            # 일시적 오류(레이트리밋/타임아웃/JSON 파싱 실패) 대비 최대 3회 시도
            llm_out = None
            last_err = None
            for attempt in range(3):
                try:
                    llm_out = self._llm_enrich(name, site_display, is_ours, facts, narrative_lines, events)
                except Exception as e:
                    last_err = e
                    llm_out = None
                if llm_out:
                    break
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))  # 1.5s, 3s backoff
            if llm_out:
                llm_out["facts"] = facts
                llm_out.setdefault("action_items", rule_actions)
                llm_out["_source"] = "gemini"
                return llm_out
            if last_err:
                print(f"[intel] {name} llm enrich gave up after retries: {last_err}")

        return {
            "facts": facts,
            "insights": insights,
            "action_items": rule_actions,
            "confidence": 0.7,
            "_source": "rule_based",
        }

    def _llm_enrich(self, category, site_display, is_ours, facts, narrative_lines, events) -> Optional[Dict[str, Any]]:
        evidence_block = {
            "category": category, "site": site_display, "is_samsung(ours)": is_ours,
            "facts": facts, "rule_based_findings": narrative_lines,
            "related_changes": [{"url": e.get("url"), "summary": e.get("summary")} for e in events[:15]],
        }
        guard = (
            f"너는 삼성전자 디지털마케팅팀의 {category} 영역 분석가다.\n"
            "절대 규칙:\n"
            "1) 아래 EVIDENCE 에 실제로 존재하는 데이터만 근거로 삼아라.\n"
            "2) EVIDENCE 에 없는 내용을 지어내지 마라. 근거 부족 시 'insufficient_data'.\n"
            f"3) {category} 카테고리에만 집중하라. 다른 카테고리(DATA/COPY/VISUAL) 내용은 언급하지 마라.\n"
            "4) 모든 insight 는 'evidence_url' 과 'evidence' 를 포함한다.\n"
        )
        schema = (
            '{"insights":[{"point":"...", "evidence_url":"...", "evidence":"..."}],'
            '"action_items":[{"action":"...", "priority":"high|medium|low", "evidence_url":"..."}],'
            '"confidence":0.0}'
        )
        prompt = f"{guard}\nEVIDENCE(JSON):\n{json.dumps(evidence_block, ensure_ascii=False)[:6500]}\n\nJSON 만 응답:\n{schema}"
        try:
            resp = self.model.generate_content(prompt)
            return self._parse_json(resp.text)
        except Exception as e:
            print(f"[intel] {category} llm enrich failed: {e}")
            return None

    def _narrate_copy(self, c: Dict[str, Any]) -> List[str]:
        lines = []
        dist = c["content_density"]["distribution"]
        total_pages = sum(dist.values()) if dist else 0
        if dist:
            dist_str = ", ".join(f"{k} {v}페이지" for k, v in dist.items())
            lines.append(f"콘텐츠 밀도 분포: 총 {total_pages}페이지 — {dist_str}")

        all_pages = c["copy_richness"].get("all_pages") or []
        if all_pages:
            avg_score = round(sum(p["score"] for p in all_pages) / len(all_pages), 1)
            avg_quant = round(sum(p.get("quant_per_100w", 0) for p in all_pages) / len(all_pages), 2)
            with_faq = sum(1 for p in all_pages if p.get("has_faq"))
            with_cta = sum(1 for p in all_pages if p.get("cta_count", 0) > 0)
            lines.append(f"카피 풍부성 평균 {avg_score}점 — 100단어당 정량 근거 평균 {avg_quant}개, FAQ 보유 {with_faq}페이지, CTA 보유 {with_cta}페이지")

        thin = c["content_density"].get("thin_pages") or []
        if thin:
            sample = ", ".join(_template_key(u) for u in thin[:3])
            lines.append(f"빈약 콘텐츠(150단어 미만) {len(thin)}페이지 — 대표: {sample}")

        gap = c["copy_richness"].get("intent_gap_pages") or []
        if gap:
            sample = []
            for g in gap[:3]:
                reasons = []
                if g.get("quant_count", 0) == 0:
                    reasons.append("정량 근거 없음")
                if not g.get("has_faq"):
                    reasons.append("FAQ 없음")
                if g.get("cta_count", 0) == 0:
                    reasons.append("CTA 없음")
                sample.append(f"{_template_key(g.get('url',''))} {g.get('score')}점({', '.join(reasons) or '구조 약함'})")
            lines.append("풍부성 미흡 페이지: " + " / ".join(sample))
        else:
            rich = c["copy_richness"].get("rich_pages") or []
            if rich:
                sample = ", ".join(f"{_template_key(x.get('url',''))} {x.get('score')}점" for x in rich[:3])
                lines.append(f"풍부성 우수 페이지: {sample}")

        faq = c["faq"]
        if faq["pages_with_faq"]:
            weak = sum(f["weak_items"] for f in faq["detail"])
            avg_faq = round(sum(f["avg_score"] for f in faq["detail"]) / len(faq["detail"]), 1) if faq["detail"] else 0
            lines.append(f"FAQ {faq['pages_with_faq']}페이지 / {faq.get('total_items', 0)}문항 — 평균 품질 {avg_faq}점, 미흡 문항 {weak}건")
        else:
            lines.append("FAQ 전무 — 문답형 검색/AI 답변에 직접 인용할 구조가 없음")
        return lines

    def _narrate_visual(self, v: Dict[str, Any]) -> List[str]:
        lines = []
        idv = v["image_diversity"]
        lines.append(f"이미지 {idv['total_images']}장 중 product {idv['product']} / "
                     f"lifestyle {idv['lifestyle']} ({idv['lifestyle_ratio_pct']}%) / 미분류 {idv['unclassified']}")

        alt = v["alt_text_quality"]
        lines.append(f"alt 텍스트 품질 — 설명적 {alt['설명적']} / 일반적(제네릭) {alt['일반적']} / "
                     f"비어있음 {alt['비어있음']} (설명적 비율 {alt['descriptive_ratio_pct']}%)")

        uniq = v["image_uniqueness"]
        if uniq["unique_src_ratio_pct"] < 60:
            lines.append(f"이미지 재사용도 높음 — 고유 이미지 비율 {uniq['unique_src_ratio_pct']}% "
                         f"(같은 이미지가 여러 페이지에 반복 사용, 템플릿화 추정)")

        conc = v["concentration"]
        if conc["max_single_page_pct"] >= 40:
            lines.append(f"이미지 편중 — 단일 페이지에 전체의 {conc['max_single_page_pct']}% 집중")

        story = v["storytelling"]
        if story["count"]:
            lines.append(f"제품+라이프스타일 혼합 스토리텔링 페이지 {story['count']}건")
        else:
            lines.append("제품/라이프스타일 혼합형 스토리텔링 페이지 없음 — 시각적 서사 단조로움")
        return lines

    # ── 비교 분석: DATA/COPY/VISUAL 각각 양사 facts 비교 ──────

    def compare(self, ours: Dict[str, Any], theirs: Dict[str, Any]) -> Dict[str, Any]:
        if not ours.get("pages") or not theirs.get("pages"):
            return {"status": "insufficient_data", "reason": "비교하려면 양사 모두 크롤 데이터가 필요합니다."}

        of_d, tf_d = data_facts(ours["pages"]), data_facts(theirs["pages"])
        of_c, tf_c = copy_facts(ours["pages"]), copy_facts(theirs["pages"])
        of_v, tf_v = visual_facts(ours["pages"]), visual_facts(theirs["pages"])

        def _avg_richness(f):
            rp = f["copy_richness"]["rich_pages"] + f["copy_richness"]["intent_gap_pages"]
            return round(sum(x["score"] for x in rp) / len(rp), 1) if rp else "N/A"

        def _avg_faq(f):
            d = f["faq"]["detail"]
            return round(sum(x["avg_score"] for x in d) / len(d), 1) if d else "N/A"

        return {
            "status": "ok",
            "data": self._compare_rows("DATA", of_d, tf_d, [
                ("Schema Coverage", lambda f: f"{f['schema']['coverage_pct']}%"),
                # [재정립] 연결 패턴은 우열 비교가 아니라 구조적 차이 참고용으로만 표기
                ("Schema 아키텍처(참고용, 우열 아님)", lambda f: f['schema']['id_linkage']['linkage_pattern']),
                ("meta description 누락", lambda f: f"{len(f['html_structure']['pages_missing_meta_description'])}+"),
            ]),
            "copy": self._compare_rows("COPY", of_c, tf_c, [
                ("카피 풍부성 평균점수(0~100)", _avg_richness),
                ("FAQ 평균 품질점수(0~100)", _avg_faq),
                ("빈약 콘텐츠 페이지(150단어 미만)", lambda f: f"{len(f['content_density']['thin_pages'])}+"),
            ]),
            "visual": self._compare_rows("VISUAL", of_v, tf_v, [
                ("Lifestyle 이미지 비율", lambda f: f"{f['image_diversity']['lifestyle_ratio_pct']}%"),
                ("alt 텍스트 설명적 비율", lambda f: f"{f['alt_text_quality']['descriptive_ratio_pct']}%"),
                ("고유 이미지 비율(재사용도 역지표)", lambda f: f"{f['image_uniqueness']['unique_src_ratio_pct']}%"),
            ]),
            "_source": "rule_based",
        }

    def _compare_rows(self, category, of, tf, dims):
        rows = []
        for label, fn in dims:
            sv, av = fn(of), fn(tf)
            rows.append({"dimension": label, "samsung": sv, "apple": av,
                        "gap": "insufficient_data" if sv == av else "차이 존재"})
        return {"comparison": rows}

    # ── JSON 파서 ────────────────────────────────────────────

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        text = text.strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None


# ── 하위호환: 기존 aeo_facts() 를 쓰는 코드(email_service 등)를 위해 유지 ──
def aeo_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    d = data_facts(pages)
    sc = d["schema"]
    return {
        "page_count": len(pages),
        "schema_type_counts": sc["schema_type_counts"],
        "faqpage_count": sc["schema_type_counts"].get("FAQPage", 0),
        "faq_item_total": sum(len(p.get("faqs") or []) for p in pages),
        "breadcrumb_pages": sc["schema_type_counts"].get("BreadcrumbList", 0),
        "product_schema_pages": sc["schema_type_counts"].get("Product", 0),
        "pages_missing_meta_description": d["html_structure"]["pages_missing_meta_description"],
        "thin_content_pages": [p.get("url") for p in pages if (p.get("word_count") or 0) < 150][:10],
    }

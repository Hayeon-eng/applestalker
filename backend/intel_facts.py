"""
Intel facts/metrics helpers.

Split out of intel_engine.py so GitHub Web Editor can open the engine file easily.
Contains DATA / COPY / VISUAL rule-based analysis and shared text utilities.
"""

from __future__ import annotations
import re
from urllib.parse import unquote
from typing import Any, Dict, List, Optional
from collections import Counter

# ════════════════════════════════════════════════════════════════
# 공통 유틸
# ════════════════════════════════════════════════════════════════

def _s(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _report_tone(text: Any) -> Any:
    """대시보드 분석 문구를 존댓말/대화체가 아닌 보고서체로 정규화."""
    if not isinstance(text, str):
        return text
    out = text.strip()
    replacements = [
        ("필요합니다", "필요"), ("가능합니다", "가능"), ("불가능합니다", "불가"),
        ("확인되었습니다", "확인"), ("감지되었습니다", "감지"), ("판단됩니다", "판단"),
        ("추정됩니다", "추정"), ("예상됩니다", "예상"), ("권장됩니다", "권장"),
        ("나타납니다", "나타남"), ("보입니다", "보임"), ("됩니다", "됨"),
        ("합니다", "함"), ("있습니다", "있음"), ("없습니다", "없음"),
        ("주세요", "필요"), ("하십시오", "필요"),
    ]
    for a, b in replacements:
        out = out.replace(a, b)
    return out


def _normalize_report_tone(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize_report_tone(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_report_tone(v) for v in obj]
    return _report_tone(obj)


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


def _readable_path(url: str) -> str:
    """대시보드 인사이트용 짧은 URL 표기."""
    try:
        after_host = _s(url).split("//", 1)[-1]
        path = after_host.split("/", 1)[1] if "/" in after_host else ""
        path = "/" + path.strip("/")
        return path if path != "/" else "홈"
    except Exception:
        return _template_key(url)


def _page_role(url: str) -> str:
    """PF/PDP/Buying/Compare/Home 역할 추정. config.page_role_for_url 과 같은 기준의 경량판."""
    u = _s(url).lower().rstrip("/")
    path = u.split("//", 1)[-1].split("/", 1)[1] if "//" in u and "/" in u.split("//", 1)[-1] else ""
    path = "/" + path.strip("/") if path else "/"
    if path in ("/", "/sg", "/global", "/en-us", "/en"):
        return "home"
    if any(k in path for k in ("/shop/buy", "/buy", "/config/", "/cty/pdp/")):
        return "buying"
    if any(k in path for k in ("compare", "find-your", "switch-to", "apple-intelligence", "galaxy-ai", "ai-glasses")) and "ray-ban-meta" not in path:
        return "campaign_or_compare"
    if any(k in path for k in ("specs", "specifications", "tech-specs")):
        return "specs"
    if any(k in path for k in ("iphone-", "pixel_", "xiaomi-", "find-x", "x300", "wf1000", "wf-1000",
                               "apple-watch-", "airpods-pro", "macbook-pro", "xps-16", "dell-da", "xps-da",
                               "/p/1701921", "/p/1723221", "ray-ban-meta", "galaxy-", "watch-ultra", "buds4")):
        return "pdp"
    if any(k in path for k in ("iphone", "phones", "smartphones", "product-list", "products", "airpods", "watch",
                               "mac", "laptops", "headphones", "wearables", "all-smartphones", "all-watches", "all-audio")):
        return "pf"
    return "content"


def _schema_expectations_for_role(role: str) -> List[str]:
    if role == "home":
        return ["WebPage", "Organization"]
    if role == "pf":
        return ["WebPage", "CollectionPage", "ItemList", "BreadcrumbList"]
    if role in ("pdp", "buying", "specs"):
        return ["WebPage", "ItemPage", "Product", "BreadcrumbList"]
    if role == "campaign_or_compare":
        return ["WebPage", "ItemList", "FAQPage"]
    return ["WebPage"]


def _expected_schema_type(url: str) -> Optional[str]:
    """URL 패턴 기반 '이 페이지엔 이 schema가 있어야 한다' 휴리스틱 (Alignment 판단용)."""
    role = _page_role(url)
    if role == "home":
        return "WebPage"
    if role == "pf":
        return "CollectionPage"
    if role in ("pdp", "buying", "specs"):
        return "Product"
    if role == "campaign_or_compare":
        return "WebPage"
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

    # ── PF/PDP/Buying 등 페이지 역할별 schema 기대값 정합성 ──
    role_distribution: Dict[str, int] = {}
    role_alignment = []
    for p in pages:
        url = p.get("url", "")
        role = _page_role(url)
        role_distribution[role] = role_distribution.get(role, 0) + 1
        nodes = _walk_schema_nodes(p.get("structured_data") or [])
        found_types = {t for n in nodes for t in _node_types(n)}
        expected_types = _schema_expectations_for_role(role)
        missing_expected = [t for t in expected_types if t not in found_types]
        if missing_expected:
            role_alignment.append({
                "url": url, "page_role": role, "expected": expected_types,
                "missing": missing_expected, "found": sorted(found_types) or ["없음"],
            })

    # ── HTML 구조: heading depth, semantic 비율(nav 보유율), p-tag 활용(=본문 비율) ──
    heading_issues = []
    semantic_pages = 0
    h1_pages = h2_pages = h3_pages = 0
    for p in pages:
        h1 = p.get("h1")
        h2 = p.get("h2") or []
        h3 = p.get("h3") or []
        if h1:
            h1_pages += 1
        if h2:
            h2_pages += 1
        if h3:
            h3_pages += 1
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
            "page_role_distribution": dict(sorted(role_distribution.items())),
            "completeness": completeness,
            "alignment_mismatches": mismatches[:10],
            "role_alignment_gaps": role_alignment[:12],
            "id_linkage": {
                "total_id_nodes": len(id_index),
                "linked_ids": len(referenced_ids),
                "isolated_ids": len(isolated_ids),
                "linkage_pattern": linkage_pattern,
            },
        },
        "html_structure": {
            "semantic_nav_pages": semantic_pages,
            "semantic_nav_coverage_pct": round(semantic_pages / total * 100, 1) if total else 0,
            "h_tag_coverage": {
                "h1_pages": h1_pages, "h2_pages": h2_pages, "h3_pages": h3_pages,
                "h1_coverage_pct": round(h1_pages / total * 100, 1) if total else 0,
                "h2_coverage_pct": round(h2_pages / total * 100, 1) if total else 0,
            },
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

    role_dist = schema.get("page_role_distribution") or {}
    if role_dist:
        role_line = ", ".join(f"{k} {v}페이지" for k, v in role_dist.items())
        lines.append(f"페이지 역할 분포(PF/PDP/Buying 등): {role_line}")

    role_gaps = schema.get("role_alignment_gaps") or []
    if role_gaps:
        sample = []
        for g in role_gaps[:3]:
            sample.append(f"{_readable_path(g.get('url',''))} — {g.get('page_role')}에서 {', '.join(g.get('missing') or [])} 누락")
        lines.append("페이지 역할 대비 Schema 보강 필요: " + " / ".join(sample))

    if not lines:
        lines.append(base)
    return lines


# ════════════════════════════════════════════════════════════════
# COPY — 콘텐츠 양 / FAQ 질 / 카피 구체성 / intent fulfillment
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

# 구체 근거 탐지: 숫자+단위 패턴 (스펙/가격/용량 등 '구체적 근거'의 대리 지표)
QUANT_UNIT_RE = re.compile(
    r"\d+(\.\d+)?\s?(GB|TB|MB|MP|mAh|mm|cm|kg|g|%|원|만원|시간|분|배|개|fps|nit|Hz|인치|inch)",
    re.IGNORECASE,
)
# 100단어당 구체 근거가 몇 개면 만점(100점)으로 칠지 — 임계값. 과도한 나열은 cap.
QUANT_TARGET_PER_100W = 3.0

# 카피 구체성 = 4개 하위지표 가중합산. 가중치 명시(투명성 확보용, 합 1.0).
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


TONE_KW = {
    "spec_proof": ("mp", "mah", "hz", "nit", "gb", "tb", "hours", "battery", "camera", "display", "processor", "chip", "spec", "performance", "benchmark"),
    "benefit": ("easy", "seamless", "effortless", "personal", "comfort", "protect", "creative", "productivity", "immersive", "편리", "간편", "몰입", "생산성"),
    "urgency": ("limited", "today", "now", "pre-order", "offer", "deal", "save", "exclusive", "한정", "지금", "혜택", "할인"),
    "ai": ("ai", "artificial intelligence", "apple intelligence", "galaxy ai", "copilot", "gemini", "machine learning"),
    "sustainability": ("carbon", "recycled", "sustainability", "environment", "eco", "recycle", "neutrality"),
}


def _tone_flags(text: str) -> Dict[str, int]:
    low = _s(text).lower()
    return {name: sum(1 for kw in kws if kw in low) for name, kws in TONE_KW.items()}


def _copy_units_for_dup(text: str) -> List[str]:
    raw = re.sub(r"\s+", " ", _s(text)).strip()
    chunks = re.split(r"(?<=[.!?。！？])\s+|\s[•·|]\s", raw)
    out = []
    for c in chunks:
        c = c.strip(" -–—|·•")
        if len(c) >= 28:
            out.append(c[:180])
    return out[:280]


def copy_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    density_dist: Dict[str, int] = {}
    thin_pages, rich_pages = [], []
    faq_page_results = []
    richness_pages = []
    intent_gap_pages = []
    all_richness_pages = []
    length_by_role: Dict[str, List[int]] = {}
    tone_counter: Counter = Counter()
    duplicate_cta_pages = []
    duplicate_copy_pages = []

    for p in pages:
        wc = max(p.get("word_count") or 0, 1)
        role = _page_role(p.get("url"))
        length_by_role.setdefault(role, []).append(wc)
        tier = _density_tier(wc)
        density_dist[tier] = density_dist.get(tier, 0) + 1
        if wc < 150:
            thin_pages.append(p.get("url"))
        if wc >= 800:
            rich_pages.append(p.get("url"))

        body = p.get("body_content") or ""
        body_lower = body.lower()
        for tone, count in _tone_flags(body).items():
            tone_counter[tone] += count
        has_comparison = any(k in body_lower for k in COMPARISON_KW)
        has_evidence = any(k in body_lower for k in EVIDENCE_KW)
        faqs = p.get("faqs") or []
        has_faq = bool(faqs)
        h2 = p.get("h2") or []
        h3 = p.get("h3") or []
        ctas = p.get("ctas") or []
        has_cta = bool(ctas)

        # 중복 CTA / 중복 본문 문구 점검
        cta_texts = [re.sub(r"\s+", " ", _s(x.get("text") if isinstance(x, dict) else x)).strip().lower() for x in ctas]
        cta_dups = [t for t, n in Counter([t for t in cta_texts if t]).items() if n >= 2]
        if cta_dups:
            duplicate_cta_pages.append({"url": p.get("url"), "duplicates": cta_dups[:5]})
        unit_counts = Counter(_copy_units_for_dup(body))
        repeated_units = [u for u, n in unit_counts.items() if n >= 2]
        if repeated_units:
            duplicate_copy_pages.append({"url": p.get("url"), "samples": repeated_units[:3]})

        # ── 구체 근거 밀도: 100단어당 숫자+단위 출현 빈도 (cap 후 0~100 스케일) ──
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
            "url": p.get("url"), "page_role": role, "score": round(richness, 1), "tier": _tier(richness),
            "word_count": wc, "quant_count": quant_count, "quant_per_100w": round(quant_per_100w, 2),
            "quant_score": round(quant_score, 1), "structure_score": round(structure_score, 1),
            "has_comparison": has_comparison, "has_evidence_keyword": has_evidence,
            "has_faq": has_faq, "h2_count": len(h2), "cta_count": len(ctas),
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

    length_summary = {
        role: {
            "pages": len(vals),
            "avg_word_count": round(sum(vals) / len(vals), 1) if vals else 0,
            "min_word_count": min(vals) if vals else 0,
            "max_word_count": max(vals) if vals else 0,
        }
        for role, vals in sorted(length_by_role.items())
    }
    dominant_tone = tone_counter.most_common(1)[0][0] if tone_counter else "insufficient_data"

    return {
        "content_density": {
            "distribution": density_dist,
            "thin_pages": thin_pages[:10],
            "rich_pages": rich_pages[:10],
        },
        "copy_length": {
            "by_page_role": length_summary,
            "note": "PF/PDP/Buying 등 페이지 역할별 평균 단어 수. 역할별 기대 카피 길이 차이를 분리해 보기 위한 보조 지표.",
        },
        "copy_richness": {
            "weights": COPY_RICHNESS_WEIGHTS,
            "all_pages": sorted(all_richness_pages, key=lambda x: x["score"]),
            "rich_pages": sorted(richness_pages, key=lambda x: -x["score"])[:10],
            "intent_gap_pages": sorted(intent_gap_pages, key=lambda x: x["score"])[:10],
        },
        "tonality": {
            "signals": dict(tone_counter),
            "dominant_tone": dominant_tone,
            "note": "스펙/혜택/긴급성/AI/지속가능성 키워드 기반 토널리티 대리지표. 문체 감성 분석이 아니라 페이지 카피 내 신호량 집계.",
        },
        "duplication": {
            "duplicate_cta_pages": duplicate_cta_pages[:10],
            "duplicate_copy_pages": duplicate_copy_pages[:10],
            "note": "같은 CTA 또는 긴 문장 단위가 반복되는 페이지를 점검. 의도적 반복일 수 있으므로 삭제 전 수동 확인 필요.",
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
    "lifestyle", "life-style", "life_style", "people", "family", "outdoor", "hand", "hands",
    "person", "scene", "moment", "woman", "man", "girl", "boy", "couple", "portrait",
    "selfie", "using", "usecase", "use-case", "daily", "travel", "gaming", "workout",
    "kitchen", "living", "laundry", "bedroom", "home-living", "office", "night",
    "camera-sample", "experience", "story", "with-galaxy", "hands-on", "in-use", "use-case",
    "라이프", "사람", "가족", "손", "일상", "야외", "사용", "사용성", "여행", "셀피", "게임",
)
PRODUCT_KW = (
    "product", "device", "render", "studio", "front", "back", "angle", "colorway", "spec",
    "gallery", "pdp", "pcd", "pf", "kv", "keyvisual", "key-visual", "design", "color",
    "colors", "exclusive", "carousel", "buy", "shop", "offer", "model",
    "galaxy", "iphone", "ipad", "macbook", "watch", "buds", "airpods", "phone", "smartphone",
    "tablet", "fold", "flip", "ultra", "plus", "edge", "s25", "s24", "z-fold", "z-flip",
    "mobile", "tv", "qled", "oled", "neo-qled", "the-frame", "soundbar", "audio", "monitor",
    "odyssey", "refrigerator", "fridge", "washing-machine", "washer", "dryer", "vacuum",
    "air-conditioner", "bespoke", "sm-", "qa", "qe", "ww", "dv", "rs", "rf", "lc", "ls",
    "제품", "기기", "스펙", "색상", "디자인", "갤럭시", "워치", "버즈", "티비", "냉장고",
)
SAMSUNG_PRODUCT_PATH_KW = (
    "/sg/mobile", "/sg/tvs", "/sg/audio-sound", "/sg/home-appliances", "/sg/computing",
    "/sg/monitors", "/sg/watches", "/sg/tablets", "/sg/smartphones", "/sg/shop",
)
# alt 텍스트가 비어있지 않아도 의미 없는 placeholder 인 경우가 많아 별도 필터링
GENERIC_ALT_WORDS = ("image", "photo", "picture", "img", "banner", "icon", "사진", "이미지", "배너", "아이콘")
ALT_RICH_MIN_LEN = 15   # 이 길이 이상 + generic 단어 아니면 '설명적'으로 분류


def _image_blob(img: Dict[str, Any], page_url: str = "") -> str:
    fields = [
        page_url,
        img.get("alt"), img.get("src"), img.get("srcset"), img.get("title"),
        img.get("aria_label"), img.get("class"), img.get("id"),
        img.get("parent_class"), img.get("parent_id"), img.get("context"),
    ]
    raw = " ".join(_s(v) for v in fields if v)
    try:
        raw = unquote(raw)
    except Exception:
        pass
    return raw.lower().replace("_", "-")


def _keyword_score(blob: str, keywords) -> int:
    return sum(1 for k in keywords if k and k in blob)


def _is_samsung_context(blob: str) -> bool:
    return "samsung.com" in blob or "images.samsung.com" in blob or "/samsung/" in blob or "galaxy" in blob


def _page_default_image_class(page: Dict[str, Any]) -> str:
    url = _s(page.get("url")).lower()
    text = " ".join([
        _s(page.get("url")), _s(page.get("title")), _s(page.get("h1")),
        " ".join(page.get("h2") or []), " ".join(page.get("h3") or []),
    ]).lower().replace("_", "-")

    if any(k in text for k in LIFESTYLE_KW) and not any(k in url for k in SAMSUNG_PRODUCT_PATH_KW):
        return "lifestyle"
    if any(k in text for k in PRODUCT_KW) or any(k in url for k in SAMSUNG_PRODUCT_PATH_KW):
        return "product"
    if "samsung.com/sg" in url:
        # Singapore 사이트의 lazy-loaded/KV 이미지는 파일 힌트가 비어도 당사 제품/브랜드 비주얼로 취급
        return "product"
    return "unclassified"


def _classify_image(img: Dict[str, Any], page_url: str = "", page_default: str = "unclassified") -> str:
    blob = _image_blob(img, "")
    fallback_blob = _image_blob(img, page_url)

    lifestyle_score = _keyword_score(blob, LIFESTYLE_KW)
    product_score = _keyword_score(blob, PRODUCT_KW)

    # Samsung Singapore는 srcset/data-src/picture 구조와 모델 코드 중심 파일명이 많다.
    # 주변 class/context/title까지 합산해 사람·사용 장면이 더 강하면 lifestyle, 모델·제품·카테고리 신호가 강하면 product.
    if lifestyle_score > 0 and lifestyle_score >= product_score:
        return "lifestyle"
    if product_score > 0:
        return "product"
    if lifestyle_score > 0:
        return "lifestyle"

    if re.search(r"(?:^|[-_/])(kv|pcd|pf|pdp|gallery|design|color|spec|front|back|device|product|model)(?:[-_/]|\.)", blob):
        return "product"
    if re.search(r"(?:sm-[a-z0-9]+|galaxy-s\d+|s2[0-9]|z-fold|z-flip|qled|oled|bespoke|odyssey|soundbar)", blob):
        return "product"
    if _is_samsung_context(fallback_blob) and page_default in ("product", "lifestyle"):
        return page_default
    return page_default if page_default in ("product", "lifestyle") else "unclassified"

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


def _visual_tactic(page: Dict[str, Any], imgs: List[Dict[str, Any]], page_types: set[str]) -> Dict[str, Any]:
    """페이지 역할별 Visual tactic을 텍스트/이미지 메타 기반으로 추정."""
    role = _page_role(page.get("url"))
    text = " ".join([
        _s(page.get("title")), _s(page.get("h1")),
        " ".join(page.get("h2") or []), " ".join(page.get("h3") or []),
    ]).lower()
    image_count = len(imgs)
    if role == "buying":
        tactic = "commerce_cta"
    elif any(k in text for k in ("gallery", "color", "design", "camera", "display", "performance", "chip")):
        tactic = "feature_gallery"
    elif "lifestyle" in page_types and "product" in page_types:
        tactic = "product_lifestyle_story"
    elif role == "pf":
        tactic = "category_grid"
    elif image_count <= 2:
        tactic = "copy_led"
    else:
        tactic = "product_showcase" if "product" in page_types else "mixed_or_unclear"
    return {
        "url": page.get("url"),
        "page_role": role,
        "tactic": tactic,
        "image_count": image_count,
        "word_count": page.get("word_count") or 0,
    }


def visual_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_images = 0
    lifestyle = 0
    product = 0
    unclassified = 0
    alt_desc = alt_generic = alt_empty = 0
    per_page_counts = []
    storytelling_pages = []
    image_heavy_pages = []
    alt_gap_pages = []
    all_srcs: List[str] = []
    all_alts: List[str] = []
    alt_samples: List[Dict[str, str]] = []
    tactic_counter: Counter = Counter()
    tactic_pages: List[Dict[str, Any]] = []
    role_visual_stats: Dict[str, Dict[str, Any]] = {}

    for p in pages:
        imgs = p.get("images") or []
        n = len(imgs)
        total_images += n
        per_page_counts.append(n)
        page_types = set()
        alt_rich = 0
        role = _page_role(p.get("url"))
        role_stat = role_visual_stats.setdefault(role, {"pages": 0, "images": 0, "words": 0})
        role_stat["pages"] += 1
        role_stat["images"] += n
        role_stat["words"] += p.get("word_count") or 0
        page_default = _page_default_image_class(p)
        for img in imgs:
            cls = _classify_image(img, p.get("url", ""), page_default)
            page_types.add(cls)
            if cls == "lifestyle":
                lifestyle += 1
            elif cls == "product":
                product += 1
            else:
                unclassified += 1

            aq = _alt_quality(img)
            alt_txt = _s(img.get("alt")).strip()
            if aq == "설명적":
                alt_desc += 1; alt_rich += 1
                if alt_txt and len(alt_samples) < 12:
                    alt_samples.append({"url": p.get("url"), "alt": alt_txt[:160]})
            elif aq == "일반적":
                alt_generic += 1
            else:
                alt_empty += 1

            src = _s(img.get("src")).strip()
            if src:
                all_srcs.append(src)
            if alt_txt:
                all_alts.append(alt_txt)

        if n >= 6:
            image_heavy_pages.append({"url": p.get("url"), "count": n, "page_role": role})
        if n and alt_rich / n < 0.4:
            alt_gap_pages.append({"url": p.get("url"), "image_count": n, "descriptive_alt": alt_rich, "page_role": role})
        if {"lifestyle", "product"}.issubset(page_types) and alt_rich >= 2:
            storytelling_pages.append(p.get("url"))

        tactic = _visual_tactic(p, imgs, page_types)
        tactic_counter[tactic["tactic"]] += 1
        tactic_pages.append(tactic)

    avg = (sum(per_page_counts) / len(per_page_counts)) if per_page_counts else 0
    max_count = max(per_page_counts) if per_page_counts else 0
    concentration = round((max_count / total_images) * 100, 1) if total_images else 0

    unique_src_ratio = round(len(set(all_srcs)) / len(all_srcs) * 100, 1) if all_srcs else 0
    unique_alt_ratio = round(len(set(all_alts)) / len(all_alts) * 100, 1) if all_alts else 0
    role_summary = {
        role: {
            "pages": vals["pages"],
            "avg_images": round(vals["images"] / vals["pages"], 1) if vals["pages"] else 0,
            "avg_words": round(vals["words"] / vals["pages"], 1) if vals["pages"] else 0,
        }
        for role, vals in sorted(role_visual_stats.items())
    }

    return {
        "image_diversity": {
            "_note": "alt/src/srcset/data-src/파일명/페이지 URL/주변 텍스트 기반 분류. Vision 분석은 아니지만 lazy-loaded 이미지와 모델명·KV·gallery 패턴을 제품/라이프스타일 이미지로 인식하도록 보강.",
            "total_images": total_images,
            "product": product, "lifestyle": lifestyle, "unclassified": unclassified,
            "lifestyle_ratio_pct": round(lifestyle / total_images * 100, 1) if total_images else 0,
        },
        "alt_text_quality": {
            "_note": "alt 텍스트 길이/제네릭 단어 기반 판정. 실제 이미지 시각 내용 분석(Vision)은 아님.",
            "설명적": alt_desc, "일반적": alt_generic, "비어있음": alt_empty,
            "descriptive_ratio_pct": round(alt_desc / total_images * 100, 1) if total_images else 0,
            "samples": alt_samples,
            "gap_pages": alt_gap_pages[:10],
        },
        "visual_tactics": {
            "_note": "PF/PDP/Buying 역할, 이미지 수, heading/파일명 힌트 기반 Visual tactic 분류. 픽셀 단위 Vision 판독은 아님.",
            "distribution": dict(tactic_counter),
            "pages": sorted(tactic_pages, key=lambda x: (x["page_role"], x["tactic"]))[:30],
            "role_summary": role_summary,
        },
        "image_uniqueness": {
            "_note": "src/alt 중복도 기반 추정치. 같은 이미지·문구 재사용(템플릿화) 정도를 가늠하는 보조지표.",
            "unique_src_ratio_pct": unique_src_ratio,
            "unique_alt_ratio_pct": unique_alt_ratio,
        },
        "concentration": {
            "avg_per_page": round(avg, 1),
            "max_single_page_pct": concentration,
            "image_heavy_pages": image_heavy_pages[:10],
        },
        "storytelling": {
            "pages_with_storytelling": storytelling_pages[:10],
            "count": len(storytelling_pages),
        },
    }



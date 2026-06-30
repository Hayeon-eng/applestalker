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

    lk = schema["id_linkage"]
    if lk["total_id_nodes"]:
        if lk["linkage_pattern"].startswith("Linked"):
            lines.append(f"@id 기반 연결형 구조 — {lk['linked_ids']}/{lk['total_id_nodes']}개 노드가 상호 참조됨 "
                         f"(플랫폼 단위 그래프 연결성 확보)")
        else:
            lines.append(f"개별 페이지 인라인 임베딩형 — {lk['total_id_nodes']}개 @id 노드가 모두 고립 "
                         f"(페이지 간 연결성 없음)")

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


def copy_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    density_dist: Dict[str, int] = {}
    thin_pages, rich_pages = [], []
    faq_quality = []
    richness_pages = []
    intent_gap_pages = []

    for p in pages:
        wc = p.get("word_count") or 0
        tier = _density_tier(wc)
        density_dist[tier] = density_dist.get(tier, 0) + 1
        if wc < 150:
            thin_pages.append(p.get("url"))
        if wc >= 800:
            rich_pages.append(p.get("url"))

        body = (p.get("body_content") or "").lower()
        has_comparison = any(k in body for k in COMPARISON_KW)
        has_evidence = any(k in body for k in EVIDENCE_KW)
        faqs = p.get("faqs") or []
        has_faq = bool(faqs)

        richness_score = sum([has_comparison, has_evidence, has_faq, wc >= 400])
        if richness_score >= 3:
            richness_pages.append({"url": p.get("url"), "score": richness_score})

        if not (has_comparison or has_evidence or has_faq):
            intent_gap_pages.append(p.get("url"))

        for faq in faqs:
            main_entity = faq.get("mainEntity") if isinstance(faq, dict) else None
            items = main_entity if isinstance(main_entity, list) else ([main_entity] if main_entity else [])
            shallow = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                ans = ((it.get("acceptedAnswer") or {}).get("text") or "") if isinstance(it.get("acceptedAnswer"), dict) else ""
                if len(_s(ans)) < 40:
                    shallow += 1
            if items:
                faq_quality.append({"url": p.get("url"), "items": len(items),
                                    "shallow_answers": shallow,
                                    "quality": "낮음" if shallow > len(items) / 2 else "양호"})

    return {
        "content_density": {
            "distribution": density_dist,
            "thin_pages": thin_pages[:10],
            "rich_pages": rich_pages[:10],
        },
        "copy_richness": {
            "rich_pages": richness_pages[:10],
            "intent_gap_pages": intent_gap_pages[:10],   # 비교/근거/FAQ 어느 것도 없는 페이지
        },
        "faq": {
            "pages_with_faq": len(faq_quality),
            "detail": faq_quality[:10],
        },
    }


# ════════════════════════════════════════════════════════════════
# VISUAL — 이미지 다양성 / lifestyle 비율 / 편중도 / 스토리텔링
# ════════════════════════════════════════════════════════════════

LIFESTYLE_KW = ("lifestyle", "life", "people", "family", "outdoor", "hand", "person", "scene", "moment")
PRODUCT_KW = ("product", "device", "render", "studio", "front", "back", "angle", "colorway", "spec")


def _classify_image(img: Dict[str, Any]) -> str:
    blob = (_s(img.get("alt")) + " " + _s(img.get("src"))).lower()
    if any(k in blob for k in LIFESTYLE_KW):
        return "lifestyle"
    if any(k in blob for k in PRODUCT_KW):
        return "product"
    return "unclassified"


def visual_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_images = 0
    lifestyle = 0
    product = 0
    unclassified = 0
    per_page_counts = []
    storytelling_pages = []
    image_heavy_pages = []

    for p in pages:
        imgs = p.get("images") or []
        n = len(imgs)
        total_images += n
        per_page_counts.append(n)
        page_types = set()
        alt_rich = 0
        for img in imgs:
            cls = _classify_image(img)
            page_types.add(cls)
            if cls == "lifestyle":
                lifestyle += 1
            elif cls == "product":
                product += 1
            else:
                unclassified += 1
            if len(_s(img.get("alt"))) >= 15:
                alt_rich += 1
        if n >= 6:
            image_heavy_pages.append({"url": p.get("url"), "count": n})
        if {"lifestyle", "product"}.issubset(page_types) and alt_rich >= 2:
            storytelling_pages.append(p.get("url"))

    avg = (sum(per_page_counts) / len(per_page_counts)) if per_page_counts else 0
    max_count = max(per_page_counts) if per_page_counts else 0
    concentration = round((max_count / total_images) * 100, 1) if total_images else 0

    return {
        "image_diversity": {
            "total_images": total_images,
            "product": product, "lifestyle": lifestyle, "unclassified": unclassified,
            "lifestyle_ratio_pct": round(lifestyle / total_images * 100, 1) if total_images else 0,
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

    def _build_category(self, name, site_display, is_ours, facts, narrative_lines, events) -> Dict[str, Any]:
        insights = [{"point": line, "evidence_url": "(집계)", "evidence": name} for line in narrative_lines]
        for e in events[:8]:
            insights.append({"point": e.get("summary"), "evidence_url": e.get("url"),
                             "evidence": f"{e.get('field_name')} [{e.get('severity_level')}]"})

        if self.ready:
            llm_out = self._llm_enrich(name, site_display, is_ours, facts, narrative_lines, events)
            if llm_out:
                llm_out["facts"] = facts
                llm_out["_source"] = "gemini"
                return llm_out

        return {
            "facts": facts,
            "insights": insights,
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
        if dist:
            dist_str = ", ".join(f"{k} {v}페이지" for k, v in dist.items())
            lines.append(f"콘텐츠 밀도 분포: {dist_str}")
        if c["content_density"]["thin_pages"]:
            lines.append(f"빈약 콘텐츠(150단어 미만) {len(c['content_density']['thin_pages'])}+ 페이지")
        gap = c["copy_richness"]["intent_gap_pages"]
        if gap:
            lines.append(f"비교/근거/FAQ 모두 없음(intent 미충족) {len(gap)}+ 페이지")
        faq = c["faq"]
        if faq["pages_with_faq"]:
            low_q = sum(1 for f in faq["detail"] if f["quality"] == "낮음")
            lines.append(f"FAQ 보유 {faq['pages_with_faq']}페이지 중 답변 부실 {low_q}건")
        else:
            lines.append("FAQ 전무 — AI 답변 직접 인용 구조 부재")
        return lines

    def _narrate_visual(self, v: Dict[str, Any]) -> List[str]:
        lines = []
        idv = v["image_diversity"]
        lines.append(f"이미지 {idv['total_images']}장 중 product {idv['product']} / "
                     f"lifestyle {idv['lifestyle']} ({idv['lifestyle_ratio_pct']}%) / 미분류 {idv['unclassified']}")
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
    """
    AEO Insight 기반 비교 엔진 (v2)
    - 단순 수치 비교 제거
    - 의미 중심 비교 (왜 중요한지 포함)
    - actionable insight 생성
    """

    if not ours.get("pages") or not theirs.get("pages"):
        return {
            "status": "insufficient_data",
            "reason": "두 사이트 모두 크롤 데이터가 필요합니다."
        }

    of_d, tf_d = data_facts(ours["pages"]), data_facts(theirs["pages"])
    of_c, tf_c = copy_facts(ours["pages"]), copy_facts(theirs["pages"])
    of_v, tf_v = visual_facts(ours["pages"]), visual_facts(theirs["pages"])

    # -----------------------------
    # 1. DATA INSIGHT LAYER
    # -----------------------------
    data_insights = []

    cov_gap = of_d["schema"]["coverage_pct"] - tf_d["schema"]["coverage_pct"]

    data_insights.append({
        "dimension": "Schema Coverage",
        "samsung": f"{of_d['schema']['coverage_pct']}%",
        "apple": f"{tf_d['schema']['coverage_pct']}%",
        "insight": (
            "스키마 커버리지가 낮으면 AI 검색(AEO) 노출 구조가 약화됨. "
            + ("삼성 우위" if cov_gap > 0 else "애플 우위" if cov_gap < 0 else "유사 수준")
        )
    })

    data_insights.append({
        "dimension": "Schema 연결 구조 (@id linkage)",
        "samsung": of_d["schema"]["id_linkage"]["linkage_pattern"],
        "apple": tf_d["schema"]["id_linkage"]["linkage_pattern"],
        "insight": (
            "Linked 구조일수록 사이트 전체를 하나의 지식 그래프로 인식 → AI 검색 유리"
        )
    })

    data_insights.append({
        "dimension": "Meta Description 누락",
        "samsung": f"{len(of_d['html_structure']['pages_missing_meta_description'])}+",
        "apple": f"{len(tf_d['html_structure']['pages_missing_meta_description'])}+",
        "insight": (
            "메타 디스크립션 누락은 CTR 감소 + 검색 스니펫 품질 저하로 직접 영향"
        )
    })

    # -----------------------------
    # 2. COPY INSIGHT LAYER
    # -----------------------------
    copy_insights = []

    copy_insights.append({
        "dimension": "콘텐츠 깊이 (Intent 충족)",
        "samsung": f"{len(of_c['copy_richness']['intent_gap_pages'])}+ gap pages",
        "apple": f"{len(tf_c['copy_richness']['intent_gap_pages'])}+ gap pages",
        "insight": (
            "비교/근거/FAQ가 없는 페이지는 검색 의도 충족 실패 → AI 답변 노출 불리"
        )
    })

    copy_insights.append({
        "dimension": "FAQ Coverage",
        "samsung": of_c["faq"]["pages_with_faq"],
        "apple": tf_c["faq"]["pages_with_faq"],
        "insight": (
            "FAQ는 AI Overview / Answer Engine 직접 소스 역할 → 많을수록 유리"
        )
    })

    # -----------------------------
    # 3. VISUAL INSIGHT LAYER
    # -----------------------------
    visual_insights = []

    visual_insights.append({
        "dimension": "Lifestyle 이미지 비율",
        "samsung": f"{of_v['image_diversity']['lifestyle_ratio_pct']}%",
        "apple": f"{tf_v['image_diversity']['lifestyle_ratio_pct']}%",
        "insight": (
            "라이프스타일 이미지 비율이 높을수록 브랜드 컨텍스트 이해도 증가"
        )
    })

    visual_insights.append({
        "dimension": "이미지 스토리텔링 페이지",
        "samsung": of_v["storytelling"]["count"],
        "apple": tf_v["storytelling"]["count"],
        "insight": (
            "제품+라이프스타일 혼합은 전환 중심 UX 신호로 작동"
        )
    })

    # -----------------------------
    # 4. OVERALL INSIGHT
    # -----------------------------
    def score(d, c, v):
        return (
            d["schema"]["coverage_pct"]
            + len(c["copy_richness"]["rich_pages"])
            + v["image_diversity"]["lifestyle_ratio_pct"]
        )

    s_score = score(of_d, of_c, of_v)
    a_score = score(tf_d, tf_c, tf_v)

    overall = {
        "summary": (
            "삼성 우위" if s_score > a_score else "애플 우위" if a_score > s_score else "유사 수준"
        ),
        "samsung_score": s_score,
        "apple_score": a_score,
        "interpretation": (
            "이 점수는 SEO가 아니라 AEO 구조 완성도를 반영한 종합 지표"
        )
    }

    # -----------------------------
    # FINAL RETURN
    # -----------------------------
    return {
        "status": "ok",

        "data": data_insights,
        "copy": copy_insights,
        "visual": visual_insights,

        "overall": overall,

        "_source": "insight_v2"
    }

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

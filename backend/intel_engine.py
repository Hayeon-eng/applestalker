"""
Intel Engine — 할루시네이션 차단형 분석 (요구사항 1,6 + 사용자 핵심 불만 해결)
================================================================
문제(사용자 지적): 크롤은 사이트 1개씩 도는데, LLM 에게 "삼성 vs 애플 비교"를
시키면 모델이 갖지 않은 데이터를 지어낸다.

해결 원칙 (strict, 근거기반):
  1) LLM 에는 "이번 크롤에서 실제로 추출된 데이터"만 컨텍스트로 준다.
  2) 비교 분석은 두 사이트 데이터가 모두 있을 때만 수행. 없으면 단일 사이트
     현황/AEO 분석만 하고, 비교 필드는 'insufficient_data' 로 명시.
  3) 모든 인사이트는 evidence (url + field + 실제 값)에 바인딩. 근거 없는 주장 금지.
  4) 출력은 엄격한 JSON 스키마. 파싱 실패 시 규칙기반 fallback (지어내지 않음).
  5) 변화 크기(max_level)에 따라 분석 깊이 자동 조절 (요구사항 6).

이 엔진은 "현황 분석"도 담당한다 (요구사항: 변경 없어도 정해진 시간에 분석).
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


# AEO(Answer Engine Optimization) 관점 — 당사(삼성)에 시사점을 주는 체크리스트.
# LLM 없이도 사실 기반으로 계산 가능한 항목들(지어내지 않음).
def aeo_facts(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """크롤 데이터에서 '사실'만 집계 (AI 아님). 모든 인사이트의 근거 토대."""
    schema_types: Dict[str, int] = {}
    faq_pages = 0
    total_faq = 0
    pages_with_breadcrumb = 0
    pages_with_product = 0
    missing_meta = []
    thin_content = []
    for p in pages:
        sd = p.get("structured_data") or p.get("schema_types") or []
        types = []
        for s in sd:
            if isinstance(s, dict):
                t = s.get("@type")
                types += (t if isinstance(t, list) else [t]) if t else []
                for g in (s.get("@graph") or []):
                    if isinstance(g, dict) and g.get("@type"):
                        gt = g["@type"]
                        types += gt if isinstance(gt, list) else [gt]
            elif isinstance(s, str):
                types.append(s)
        for t in types:
            t = str(t)
            schema_types[t] = schema_types.get(t, 0) + 1
        if "FAQPage" in types:
            faq_pages += 1
        if "BreadcrumbList" in types:
            pages_with_breadcrumb += 1
        if "Product" in types:
            pages_with_product += 1
        total_faq += len(p.get("faqs") or [])
        if not (p.get("meta_description") or "").strip():
            missing_meta.append(p.get("url"))
        if (p.get("word_count") or 0) < 150:
            thin_content.append(p.get("url"))
    return {
        "page_count": len(pages),
        "schema_type_counts": dict(sorted(schema_types.items(), key=lambda x: -x[1])),
        "faqpage_count": faq_pages,
        "faq_item_total": total_faq,
        "breadcrumb_pages": pages_with_breadcrumb,
        "product_schema_pages": pages_with_product,
        "pages_missing_meta_description": missing_meta[:10],
        "thin_content_pages": thin_content[:10],
    }


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

    # ── 메인: 단일 사이트 현황/변화 분석 (근거기반) ──────────────

    def analyze_site(
        self,
        site_display: str,
        is_ours: bool,
        pages: List[Dict[str, Any]],
        change_events: List[Dict[str, Any]],
        max_level: str = "L0",
    ) -> Dict[str, Any]:
        """
        한 사이트의 이번 크롤 결과를 분석.
        change_events: diff_engine.ChangeEvent.to_dict() 리스트 (실제 변화만).
        반환: 엄격 JSON. 근거 없는 비교는 하지 않음.
        """
        facts = aeo_facts(pages)
        depth = self._depth_for(max_level, len(change_events))

        if not self.ready:
            return self._fallback(site_display, is_ours, facts, change_events, depth)

        # LLM 에 주는 컨텍스트 = 사실 + 실제 변화 이벤트만 (지어낼 여지 차단)
        evidence_block = {
            "site": site_display,
            "is_samsung(ours)": is_ours,
            "aeo_facts": facts,
            "detected_changes": [
                {"url": e.get("url"), "field": e.get("field_name"),
                 "level": e.get("severity_level"), "summary": e.get("summary"),
                 "before": (e.get("before_value") or "")[:160],
                 "after": (e.get("after_value") or "")[:160]}
                for e in change_events[:25]
            ],
        }

        guard = (
            "너는 삼성전자 디지털마케팅팀의 경쟁 인텔리전스 분석가다.\n"
            "절대 규칙:\n"
            "1) 아래 EVIDENCE 에 실제로 존재하는 데이터만 근거로 삼아라.\n"
            "2) EVIDENCE 에 없는 수치/문구/경쟁사 상태를 추측하거나 지어내지 마라.\n"
            "3) 근거가 부족하면 해당 항목 값에 \"insufficient_data\" 라고 써라.\n"
            "4) 모든 insight 는 반드시 'evidence_url' 과 'evidence' 를 포함한다.\n"
            "5) 이 크롤에는 한 사이트 데이터만 있으므로, 경쟁사 직접 비교는 하지 말고 "
            "   '당사(삼성) AEO 관점 시사점'에 집중하라.\n"
        )
        schema = (
            '{\n'
            '  "summary": "이번 크롤 핵심 1-2문장 (사실 기반)",\n'
            '  "aeo_implications_for_samsung": "당사 AEO 관점 시사점 2-3문장",\n'
            '  "insights": [{"point":"...", "evidence_url":"...", "evidence":"실제 추출값/변화"}],\n'
            '  "action_items": [{"action":"...", "priority":"critical|high|medium|low", "evidence_url":"..."}],\n'
            '  "confidence": 0.0\n'
            '}'
        )
        prompt = (
            f"{guard}\nEVIDENCE(JSON):\n"
            f"{json.dumps(evidence_block, ensure_ascii=False)[:7000]}\n\n"
            f"분석 깊이: {depth} (insights {depth['insights']}개, actions {depth['actions']}개).\n"
            f"다음 JSON 스키마로만 응답(마크다운 금지):\n{schema}"
        )
        try:
            resp = self.model.generate_content(prompt)
            out = self._parse_json(resp.text)
            if out is None:
                return self._fallback(site_display, is_ours, facts, change_events, depth)
            out["_source"] = "gemini"
            out["_facts"] = facts
            out["_evidence_bound"] = True
            return out
        except Exception as e:
            print(f"[intel] gemini analyze failed: {e}")
            return self._fallback(site_display, is_ours, facts, change_events, depth)

    # ── 비교 분석: 두 사이트 데이터가 모두 있을 때만 ─────────────

    def compare(
        self,
        ours: Dict[str, Any],            # {"display","facts","pages"} 삼성
        theirs: Dict[str, Any],          # 애플
    ) -> Dict[str, Any]:
        """
        양사 크롤 데이터가 모두 존재할 때만 호출. 둘 다 실제 facts 를 근거로 비교.
        한쪽이라도 비면 insufficient_data 반환 (지어내지 않음).
        """
        if not ours.get("facts") or not theirs.get("facts"):
            return {"status": "insufficient_data",
                    "reason": "비교하려면 양사 모두 크롤 데이터가 필요합니다."}
        if not self.ready:
            return self._fallback_compare(ours, theirs)

        block = {"samsung_facts": ours["facts"], "apple_facts": theirs["facts"]}
        guard = (
            "너는 삼성 경쟁 인텔리전스 분석가다. 아래 두 사실집합(facts)만 근거로 "
            "AEO/스키마/콘텐츠 구조를 비교하라. facts 에 없는 내용은 지어내지 말고 "
            "insufficient_data 로 표기하라. 모든 비교 항목에 수치 근거를 붙여라.\n"
        )
        schema = (
            '{"comparison":[{"dimension":"스키마 커버리지|FAQ|메타|콘텐츠 깊이",'
            '"samsung":"수치 근거","apple":"수치 근거","gap":"당사 격차/우위",'
            '"action":"당사 액션"}],"overall":"2-3문장","confidence":0.0}'
        )
        prompt = f"{guard}FACTS:\n{json.dumps(block, ensure_ascii=False)[:6000]}\n\nJSON 만:\n{schema}"
        try:
            out = self._parse_json(self.model.generate_content(prompt).text)
            if out is None:
                return self._fallback_compare(ours, theirs)
            out["_source"] = "gemini"
            return out
        except Exception as e:
            print(f"[intel] compare failed: {e}")
            return self._fallback_compare(ours, theirs)

    # ── 깊이 자동 조절 (요구사항 6) ──────────────────────────────

    def _depth_for(self, max_level: str, n_changes: int) -> Dict[str, int]:
        order = ["L0", "L1", "L2", "L3", "L4", "L5"]
        lvl = order.index(max_level) if max_level in order else 0
        if lvl >= 5 or n_changes >= 15:
            return {"insights": 6, "actions": 5}
        if lvl >= 3 or n_changes >= 5:
            return {"insights": 4, "actions": 3}
        return {"insights": 3, "actions": 2}

    # ── JSON 파서 (엄격) ─────────────────────────────────────────

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

    # ── Fallback (규칙기반, 지어내지 않음) ──────────────────────

    def _fallback(self, site, is_ours, facts, events, depth) -> Dict[str, Any]:
        sc = facts["schema_type_counts"]
        insights = []
        if facts["faqpage_count"]:
            insights.append({"point": f"FAQPage 스키마 {facts['faqpage_count']}개 페이지 보유 — AI 답변 노출 토대 존재",
                             "evidence_url": "(집계)", "evidence": f"FAQPage×{facts['faqpage_count']}"})
        else:
            insights.append({"point": "FAQPage 스키마 미보유 — AI Overview 직접 노출 구조 부재",
                             "evidence_url": "(집계)", "evidence": "FAQPage=0"})
        if facts["pages_missing_meta_description"]:
            insights.append({"point": f"meta description 누락 {len(facts['pages_missing_meta_description'])}+ 페이지",
                             "evidence_url": facts["pages_missing_meta_description"][0] or "(집계)",
                             "evidence": "meta description empty"})
        if facts["thin_content_pages"]:
            insights.append({"point": f"본문 빈약(150단어 미만) {len(facts['thin_content_pages'])}+ 페이지",
                             "evidence_url": facts["thin_content_pages"][0] or "(집계)",
                             "evidence": "word_count<150"})
        for e in events[:depth["insights"]]:
            insights.append({"point": e.get("summary"), "evidence_url": e.get("url"),
                             "evidence": f"{e.get('field_name')} [{e.get('severity_level')}]"})

        actions = []
        if is_ours and facts["faqpage_count"] == 0:
            actions.append({"action": "주요 제품 페이지에 FAQPage JSON-LD 인라인 임베드 적용",
                            "priority": "high", "evidence_url": "(집계)"})
        if facts["pages_missing_meta_description"]:
            actions.append({"action": "meta description 누락 페이지 보강",
                            "priority": "medium",
                            "evidence_url": facts["pages_missing_meta_description"][0] or "(집계)"})

        return {
            "summary": f"{site} {facts['page_count']}개 페이지 크롤 완료. "
                       f"변화 {len(events)}건. 스키마 타입 {len(sc)}종.",
            "aeo_implications_for_samsung":
                ("당사 사이트 분석: " if is_ours else "경쟁사 분석(당사 시사점): ") +
                (f"FAQPage {facts['faqpage_count']}개, Breadcrumb {facts['breadcrumb_pages']}개, "
                 f"Product {facts['product_schema_pages']}개 페이지. "
                 "GEMINI_API_KEY 설정 시 더 정밀한 시사점 제공."),
            "insights": insights[:depth["insights"] + 3],
            "action_items": actions[:depth["actions"]] or
                            [{"action": "현 상태 양호 — 정기 모니터링 유지",
                              "priority": "low", "evidence_url": "(집계)"}],
            "confidence": 0.55,
            "_source": "fallback",
            "_facts": facts,
            "_evidence_bound": True,
        }

    def _fallback_compare(self, ours, theirs) -> Dict[str, Any]:
        of, tf = ours["facts"], theirs["facts"]
        rows = []
        rows.append({"dimension": "FAQPage 스키마",
                     "samsung": f"{of['faqpage_count']}개 페이지",
                     "apple": f"{tf['faqpage_count']}개 페이지",
                     "gap": "당사 부족" if of['faqpage_count'] < tf['faqpage_count'] else "당사 우위/동등",
                     "action": "FAQPage 인라인 임베드 확대" if of['faqpage_count'] < tf['faqpage_count'] else "현 수준 유지"})
        rows.append({"dimension": "스키마 타입 다양성",
                     "samsung": f"{len(of['schema_type_counts'])}종",
                     "apple": f"{len(tf['schema_type_counts'])}종",
                     "gap": "당사 부족" if len(of['schema_type_counts']) < len(tf['schema_type_counts']) else "당사 우위/동등",
                     "action": "누락 스키마 타입 보강"})
        rows.append({"dimension": "meta description 누락",
                     "samsung": f"{len(of['pages_missing_meta_description'])}+",
                     "apple": f"{len(tf['pages_missing_meta_description'])}+",
                     "gap": "insufficient_data",
                     "action": "누락 페이지 보강"})
        return {"comparison": rows,
                "overall": "규칙기반 비교(수치 근거). 정밀 분석은 GEMINI_API_KEY 설정 후 제공.",
                "confidence": 0.5, "_source": "fallback"}

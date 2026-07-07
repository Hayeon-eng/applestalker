"""
Intel Engine — DATA / COPY / VISUAL 3분류 분석 (할루시네이션 차단형)

This file intentionally stays lightweight. Heavy rule-based DATA/COPY/VISUAL
facts are in intel_facts.py so GitHub Web Editor can open this file reliably.
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

from intel_facts import (
    _s,
    _report_tone,
    _normalize_report_tone,
    _readable_path,
    data_facts,
    copy_facts,
    visual_facts,
    _narrate_schema_completeness,
)

class IntelEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.model = None
        self.ready = False
        # Q3: 여러 사이트를 연속 분석할 때 RPM 초과로 뒤 순번(경쟁사)이 폴백되는 것을 완화하기 위한 호출 간 지연
        self._call_delay = float(os.getenv("GEMINI_CALL_DELAY_SEC", "0.8"))
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
        if self.ready and self._call_delay > 0:
            time.sleep(self._call_delay)
        copy_block = self._build_category("COPY", site_display, is_ours, c_facts,
                                           self._narrate_copy(c_facts),
                                           [e for e in change_events if self._bucket(e) == "COPY"])
        if self.ready and self._call_delay > 0:
            time.sleep(self._call_delay)
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
        insights = [{"point": _report_tone(line), "evidence_url": "(집계)", "evidence": name} for line in narrative_lines]
        for e in events[:8]:
            insights.append({"point": _report_tone(e.get("summary")), "evidence_url": e.get("url"),
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
                llm_out = _normalize_report_tone(llm_out)
                llm_out["facts"] = facts
                llm_out.setdefault("action_items", rule_actions)
                llm_out["_source"] = "gemini"
                return llm_out
            if last_err:
                print(f"[intel] {name} llm enrich gave up after retries: {last_err}")

        return {
            "facts": facts,
            "insights": _normalize_report_tone(insights),
            "action_items": _normalize_report_tone(rule_actions),
            "confidence": 0.7,
            "_source": "rule_based",
            "_fallback_reason": ("ai_response_failed" if self.ready else "ai_disabled"),
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
            "5) 문체는 대시보드 보고서체로 통일한다. '~합니다/~됩니다/~주세요' 같은 존댓말·대화체를 쓰지 말고 '~확인/~필요/~판단/~없음'처럼 간결하게 쓴다.\n"
            "6) word_count, quant_per_100w, quant_score 같은 내부 지표명은 그대로 쓰지 말고 '텍스트 양', '100단어당 구체 근거 수', '카피 구체성 점수'처럼 풀어서 설명한다.\n"
        )
        schema = (
            '{"insights":[{"point":"...", "evidence_url":"...", "evidence":"..."}],'
            '"action_items":[{"action":"...", "priority":"high|medium|low", "evidence_url":"..."}],'
            '"confidence":0.0}'
        )
        prompt = f"{guard}\nEVIDENCE(JSON):\n{json.dumps(evidence_block, ensure_ascii=False)[:6500]}\n\nJSON 만 응답:\n{schema}"
        try:
            # Q3: JSON 응답 모드 + 넉넉한 출력 토큰 — gemini-2.5 thinking 토큰이 출력을 다 먹어
            # 빈 응답이 오는 폴백을 줄인다. (구버전 SDK라 thinking 직접 제어는 불가)
            gen_cfg = {
                "temperature": 0.3,
                "max_output_tokens": int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096")),
                "response_mime_type": "application/json",
            }
            # [FIX] 호출당 상한(기본 20s)을 명시 — 이게 없으면 네트워크 지연/레이트리밋 시
            # SDK가 내부적으로 얼마나 오래 걸릴지 보장이 없어, 이 함수는 스레드에서 돌더라도
            # (asyncio.to_thread) 사이트 하나 처리 시간이 한없이 늘어질 수 있다.
            req_opts = {"timeout": int(os.getenv("GEMINI_CALL_TIMEOUT_S", "20"))}
            try:
                resp = self.model.generate_content(prompt, generation_config=gen_cfg, request_options=req_opts)
            except TypeError:
                # 구버전 SDK가 request_options 파라미터를 지원하지 않으면 조용히 폴백
                try:
                    resp = self.model.generate_content(prompt, generation_config=gen_cfg)
                except Exception:
                    resp = self.model.generate_content(prompt)
            except Exception:
                # response_mime_type 등을 모델/SDK가 거부하면 기본 호출로 폴백
                resp = self.model.generate_content(prompt, request_options=req_opts)
            return self._parse_json(resp.text)
        except Exception as e:
            # [FIX] 기존엔 "llm enrich failed"라고만 찍혀서 gemini-2.5+ thinking 토큰이
            # max_output_tokens를 다 써서 빈 응답이 온 건지, 다른 문제인지 로그만 봐선
            # 구분이 안 됐다. gemini_health의 동일 분류 로직을 재사용해 원인을 바로 남긴다.
            msg = str(e)
            if "quick accessor requires the response to contain a valid" in msg.lower():
                print(f"[intel] {category} llm enrich failed: gemini thinking 토큰이 "
                      f"output 예산을 다 써서 실제 응답 없음(구버전 SDK는 thinking 제어 불가) "
                      f"— rule-based로 폴백. raw={msg[:200]}")
            else:
                print(f"[intel] {category} llm enrich failed: {e}")
            return None

    def _narrate_copy(self, c: Dict[str, Any]) -> List[str]:
        """COPY 요약은 '단어 수가 많다/적다'가 아니라, 실제 운영 관점에서
        PF/PDP/Buying이 어떤 역할을 하고 있는지와 어떤 액션이 필요한지 중심으로 작성한다.
        """
        lines: List[str] = []
        role_len = c.get("copy_length", {}).get("by_page_role") or {}
        all_pages = c.get("copy_richness", {}).get("all_pages") or []
        total_pages = len(all_pages) or sum(v.get("pages", 0) for v in role_len.values())
        role_labels = {
            "pf": "PF", "pdp": "PDP", "buying": "Buying", "specs": "Specs",
            "campaign_or_compare": "Compare/Campaign", "home": "Home", "content": "Content",
        }

        if total_pages:
            role_parts = []
            for role in ["pf", "pdp", "buying", "specs", "campaign_or_compare", "home", "content"]:
                vals = role_len.get(role)
                if vals:
                    role_parts.append(f"{role_labels.get(role, role)} {vals.get('pages', 0)}p")
            lines.append(
                "수집 범위: " + ", ".join(role_parts[:7]) +
                ". 아래 카피 판단은 이 페이지 역할 조합 안에서만 해석합니다. Buying은 짧아도 정상일 수 있고, PDP/PF는 제품 이해·비교·전환 근거가 보이는지가 핵심입니다."
            )

        commerce = c.get("commerce_cta", {}) or {}
        buy_pages = commerce.get("buy_cta_pages") or []
        missing_buy = commerce.get("missing_buy_cta_pages") or []
        if total_pages:
            msg = f"구매 전환 신호: Buy/Shop/Add to cart/Where to buy 계열 CTA가 {len(buy_pages)}페이지에서 확인됩니다."
            if buy_pages:
                sample = ", ".join(f"{_readable_path(x.get('url', ''))}({x.get('page_role')})" for x in buy_pages[:3])
                msg += f" 대표 근거는 {sample}입니다."
            if missing_buy:
                sample_missing = ", ".join(f"{_readable_path(x.get('url', ''))}({x.get('page_role')})" for x in missing_buy[:3])
                msg += f" CTA가 수집되지 않은 PF/PDP/Buying 후보는 {len(missing_buy)}페이지이며, 우선 {sample_missing}를 확인하세요."
            else:
                msg += " PF/PDP/Buying에서 전환 CTA 공백은 크게 보이지 않습니다."
            lines.append(msg)

        faq = c.get("faq", {}) or {}
        if faq.get("pages_with_faq"):
            detail = faq.get("detail") or []
            weak = sum(f.get("weak_items", 0) for f in detail)
            lines.append(
                f"FAQ/질문 대응: FAQ 구조가 {faq.get('pages_with_faq')}페이지에서 {faq.get('total_items', 0)}문항 확인됩니다. "
                f"보강 후보 문항은 {weak}건입니다. 제품 비교·구매 조건·호환성처럼 실제 사용자가 물을 질문에 답하는지 확인하면 AI 답변 근거로 쓰기 좋습니다."
            )
        elif total_pages:
            lines.append(
                "FAQ/질문 대응: 이번 수집에서는 FAQ 구조가 확인되지 않았습니다. 모든 페이지에 FAQ가 필요하진 않지만, PDP와 Buying의 핵심 질문(가격·혜택·호환·배송·반품)은 별도 근거가 있는지 확인하세요."
            )

        rich = c.get("copy_richness", {}) or {}
        intent_gap = rich.get("intent_gap_pages") or []
        if intent_gap:
            sample = []
            role_priority = {"pdp": 0, "buying": 1, "pf": 2, "specs": 3, "campaign_or_compare": 4, "home": 5, "content": 6}
            for g in sorted(intent_gap, key=lambda x: (role_priority.get(x.get("page_role"), 9), x.get("score", 0)))[:4]:
                reasons = []
                if g.get("quant_count", 0) == 0:
                    reasons.append("스펙·조건 근거 부족")
                if not g.get("has_faq"):
                    reasons.append("FAQ 없음")
                if g.get("cta_count", 0) == 0:
                    reasons.append("CTA 없음")
                sample.append(f"{_readable_path(g.get('url',''))}({g.get('page_role')}: {', '.join(reasons) or '카피 근거 약함'})")
            lines.append(
                "우선 점검할 카피: " + " / ".join(sample) +
                ". 이 항목은 단어 수 평가가 아니라, 해당 역할에서 사용자가 결정을 내릴 근거가 충분한지 보는 후보입니다."
            )

        dup = c.get("duplication", {}) or {}
        dup_cta = dup.get("duplicate_cta_pages") or []
        dup_copy = dup.get("duplicate_copy_pages") or []
        if dup_cta or dup_copy:
            pieces = []
            if dup_cta:
                pieces.append(f"중복 CTA 후보 {len(dup_cta)}페이지")
            if dup_copy:
                pieces.append(f"중복 본문 후보 {len(dup_copy)}페이지")
            lines.append(
                "중복/불필요 문구 점검: " + " · ".join(pieces) +
                ". 공통 헤더·푸터 반복일 수 있으므로, 실제 본문 반복인지 확인한 뒤 정리 여부를 판단하세요."
            )

        tone = c.get("tonality", {}) or {}
        signals = tone.get("signals") or {}
        if signals:
            top_tones = sorted(signals.items(), key=lambda x: -x[1])[:3]
            tone_ko = {"spec_proof": "스펙/성능", "benefit": "사용자 혜택", "urgency": "프로모션/긴급성", "ai": "AI", "sustainability": "지속가능성"}
            lines.append(
                "토널리티: " + ", ".join(f"{tone_ko.get(name, name)} 신호 {count}" for name, count in top_tones) +
                ". 실제 문체 감성 분석이 아니라, 페이지 텍스트 안에 어떤 메시지 재료가 많이 쓰였는지 보는 기준입니다."
            )

        if not lines:
            lines.append("COPY 인사이트를 만들 수 있는 수집 근거가 아직 없습니다. 먼저 PF/PDP/Buying 페이지가 정상 수집됐는지 확인하세요.")
        return lines

    def _narrate_visual(self, v: Dict[str, Any]) -> List[str]:
        """Visual narrative.

        이미지 픽셀/스크린샷 분석이 아니라 crawler가 수집한 img alt/src/파일명,
        페이지 URL, 주변 텍스트 신호만으로 판단한다. 그래서 "보이는 이미지가 실제로
        무엇인가"보다 "사이트가 이미지 메타데이터를 어떻게 설계했는가"를 읽는 지표다.
        """
        lines: List[str] = []
        idv = v.get("image_diversity", {})
        total = idv.get("total_images", 0)
        product = idv.get("product", 0)
        lifestyle = idv.get("lifestyle", 0)
        unclassified = idv.get("unclassified", 0)
        lifestyle_pct = idv.get("lifestyle_ratio_pct", 0)
        lines.append(
            "이미지 분석 방식: 실제 스크린샷/픽셀을 보지 않고, HTML의 alt 텍스트·src 파일명·URL 신호로만 판단합니다. "
            f"현재 수집 기준으로 총 {total}장 중 제품 중심 {product}장, 사용 상황/lifestyle 추정 {lifestyle}장({lifestyle_pct}%), "
            f"분류 불가 {unclassified}장입니다. 이 수치는 실제 이미지 내용의 확정 판정이 아니라 메타데이터 기반 신호입니다."
        )

        alt = v.get("alt_text_quality", {})
        desc = alt.get("설명적", 0)
        generic = alt.get("일반적", 0)
        empty = alt.get("비어있음", 0)
        desc_pct = alt.get("descriptive_ratio_pct", 0)
        lines.append(
            f"alt.copy 품질: 설명적 alt {desc}건, 일반적 alt {generic}건, 비어 있음 {empty}건으로 설명적 비율은 {desc_pct}%입니다. "
            "설명적 alt가 높으면 접근성뿐 아니라 이미지가 검색·AI 요약에서 어떤 장면인지 이해되기 쉽고, 낮으면 이미지가 있어도 의미 신호가 약합니다."
        )
        gap_pages = alt.get("gap_pages") or []
        if gap_pages:
            sample = ", ".join(_readable_path(x.get("url", "")) for x in gap_pages[:3])
            lines.append(
                f"alt.copy 보강 필요: 비어 있거나 너무 일반적인 alt가 있는 페이지가 {len(gap_pages)}건 있습니다. "
                f"대표 페이지는 {sample}입니다. 우선 이 페이지들은 hero/KV·gallery 이미지가 무엇을 보여주는지 alt에 구체적으로 적는 것이 좋습니다."
            )
        samples = alt.get("samples") or []
        if samples:
            sample_text = " / ".join(_s(x.get("alt"))[:45] for x in samples[:3])
            lines.append(f"설명적 alt.copy 예시: {sample_text}. 이런 문구는 이미지가 전달하는 제품 기능이나 사용 장면을 비교적 잘 설명합니다.")

        tactics = v.get("visual_tactics", {}) or {}
        dist = tactics.get("distribution") or {}
        if dist:
            ordered = sorted(dist.items(), key=lambda x: -x[1])[:4]
            lines.append(
                "Visual tactic 분포: "
                + ", ".join(f"{name} {count}p" for name, count in ordered)
                + ". 이 분포는 사이트가 제품 실물, 기능 갤러리, 카테고리 그리드, 구매 CTA 중 어디에 시각적 무게를 두는지 보여줍니다."
            )
        role_summary = tactics.get("role_summary") or {}
        if role_summary:
            parts = []
            for role, vals in role_summary.items():
                parts.append(f"{role} 평균 이미지 {vals.get('avg_images', 0)}장/평균 단어 {vals.get('avg_words', 0)}개")
            lines.append(
                "페이지 역할별 길이와 이미지 밀도: " + " / ".join(parts[:6])
                + ". PF는 탐색용이라 이미지가 많아도 자연스럽고, PDP는 기능 설명과 이미지가 균형을 이루는지, Buying은 CTA와 구성 정보가 빠르게 보이는지가 핵심입니다."
            )

        uniq = v.get("image_uniqueness", {})
        uniq_pct = uniq.get("unique_src_ratio_pct", 100)
        if uniq_pct < 60:
            lines.append(
                f"이미지 재사용 신호: 고유 이미지 비율이 {uniq_pct}%로 낮습니다. "
                "동일 이미지가 여러 페이지에 반복되어 템플릿처럼 보일 수 있으므로, 핵심 PDP/Buying에서는 모델별 차별 이미지가 충분한지 확인이 필요합니다."
            )
        else:
            lines.append(f"이미지 고유성: 고유 이미지 비율 {uniq_pct}%로, 현재 수집 기준에서는 과도한 이미지 재사용 신호가 크지 않습니다.")

        conc = v.get("concentration", {})
        max_pct = conc.get("max_single_page_pct", 0)
        if max_pct >= 40:
            lines.append(
                f"이미지 편중: 한 페이지가 전체 이미지의 {max_pct}%를 차지합니다. "
                "특정 랜딩/PDP에 시각 자산이 몰려 있고 다른 페이지는 상대적으로 이미지 근거가 적을 수 있으니, 비교 시 페이지 역할을 나눠 봐야 합니다."
            )

        story = v.get("storytelling", {})
        if story.get("count"):
            lines.append(
                f"스토리텔링 페이지: 제품 이미지와 사용 상황/lifestyle 신호가 함께 잡힌 페이지가 {story.get('count')}건 있습니다. "
                "이 페이지들은 단순 스펙 나열보다 사용 장면을 통해 제품 가치를 설득하는 구조로 볼 수 있습니다."
            )
        else:
            lines.append(
                "스토리텔링 신호: 제품 이미지와 사용 상황/lifestyle 신호가 동시에 강하게 잡힌 페이지가 없습니다. "
                "이미지 메타데이터 기준으로는 기능·스펙 중심 구조에 가깝고, 생활 장면 기반 설득은 약하게 보입니다."
            )
        return lines

    # ── 비교 분석: DATA/COPY/VISUAL 각각 양사 facts 비교 ──────

    def compare(self, ours: Dict[str, Any], theirs: Dict[str, Any]) -> Dict[str, Any]:
        if not ours.get("pages") or not theirs.get("pages"):
            return {"status": "insufficient_data", "reason": "양사 크롤 데이터 모두 필요"}

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
                ("카피 구체성 평균점수(0~100)", _avg_richness),
                ("FAQ 평균 품질점수(0~100)", _avg_faq),
                ("짧은 텍스트 페이지(150단어 미만)", lambda f: f"{len(f['content_density']['thin_pages'])}+"),
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

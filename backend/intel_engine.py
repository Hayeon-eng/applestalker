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
            resp = self.model.generate_content(prompt)
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
        lines = []
        dist = c["content_density"]["distribution"]
        total_pages = sum(dist.values()) if dist else 0
        if dist:
            dist_str = ", ".join(f"{k} {v}페이지" for k, v in dist.items())
            lines.append(f"콘텐츠 양 기준 분포: 총 {total_pages}페이지 — {dist_str}")

        all_pages = c["copy_richness"].get("all_pages") or []
        if all_pages:
            avg_score = round(sum(p["score"] for p in all_pages) / len(all_pages), 1)
            avg_quant = round(sum(p.get("quant_per_100w", 0) for p in all_pages) / len(all_pages), 2)
            with_faq = sum(1 for p in all_pages if p.get("has_faq"))
            with_cta = sum(1 for p in all_pages if p.get("cta_count", 0) > 0)
            lines.append(
                f"카피 구체성 평균 {avg_score}점 — 숫자·스펙·가격·기간 등 구체 근거가 "
                f"100단어당 평균 {avg_quant}개 확인, FAQ 보유 {with_faq}페이지, CTA 보유 {with_cta}페이지"
            )

            low_quant_dense = [
                p for p in all_pages
                if p.get("word_count", 0) >= 400 and p.get("quant_per_100w", 0) < 1.0
            ]
            if low_quant_dense:
                sample = []
                for g in sorted(low_quant_dense, key=lambda x: (-x.get("word_count", 0), x.get("quant_per_100w", 0)))[:3]:
                    sample.append(
                        f"{_readable_path(g.get('url',''))} — 텍스트 {g.get('word_count', 0)}단어, "
                        f"구체 근거 {g.get('quant_count', 0)}개"
                    )
                lines.append(
                    "텍스트는 충분하지만 숫자·스펙·지원 조건 같은 구체 정보가 적은 페이지 확인: "
                    + " / ".join(sample)
                    + " — 카피 근거 보강 검토"
                )

        thin = c["content_density"].get("thin_pages") or []
        if thin:
            sample = ", ".join(_readable_path(u) for u in thin[:3])
            lines.append(f"텍스트 양이 부족한 페이지(150단어 미만) {len(thin)}건 — 대표: {sample}")

        gap = c["copy_richness"].get("intent_gap_pages") or []
        if gap:
            sample = []
            for g in gap[:3]:
                reasons = []
                if g.get("quant_count", 0) == 0:
                    reasons.append("숫자·스펙 등 구체 근거 부족")
                if not g.get("has_faq"):
                    reasons.append("FAQ 없음")
                if g.get("cta_count", 0) == 0:
                    reasons.append("CTA 없음")
                sample.append(f"{_readable_path(g.get('url',''))} {g.get('score')}점({', '.join(reasons) or '구조 약함'})")
            lines.append("카피 구체성 미흡 페이지: " + " / ".join(sample))
        else:
            rich = c["copy_richness"].get("rich_pages") or []
            if rich:
                sample = ", ".join(f"{_readable_path(x.get('url',''))} {x.get('score')}점" for x in rich[:3])
                lines.append(f"카피 구체성 우수 페이지: {sample}")

        copy_len = c.get("copy_length", {}).get("by_page_role") or {}
        if copy_len:
            parts = []
            for role, vals in copy_len.items():
                parts.append(f"{role} 평균 {vals.get('avg_word_count', 0)}단어({vals.get('pages', 0)}p)")
            lines.append("페이지 역할별 카피 길이: " + " / ".join(parts[:6]))

        tone = c.get("tonality", {})
        signals = tone.get("signals") or {}
        if signals:
            top_tones = sorted(signals.items(), key=lambda x: -x[1])[:3]
            lines.append("토널리티 신호: " + ", ".join(f"{name} {count}" for name, count in top_tones) + f" — dominant {tone.get('dominant_tone')}")

        dup = c.get("duplication", {})
        dup_cta = dup.get("duplicate_cta_pages") or []
        dup_copy = dup.get("duplicate_copy_pages") or []
        if dup_cta or dup_copy:
            pieces = []
            if dup_cta:
                pieces.append(f"중복 CTA {len(dup_cta)}페이지")
            if dup_copy:
                pieces.append(f"중복 문구 {len(dup_copy)}페이지")
            lines.append("불필요한 버튼/중복 텍스트 점검 필요 — " + " · ".join(pieces))

        faq = c["faq"]
        if faq["pages_with_faq"]:
            weak = sum(f["weak_items"] for f in faq["detail"])
            avg_faq = round(sum(f["avg_score"] for f in faq["detail"]) / len(faq["detail"]), 1) if faq["detail"] else 0
            lines.append(f"FAQ {faq['pages_with_faq']}페이지 / {faq.get('total_items', 0)}문항 — 평균 품질 {avg_faq}점, 보강 필요 문항 {weak}건")
        else:
            lines.append("FAQ 없음 — 문답형 검색/AI 답변에서 직접 인용할 수 있는 구조 부족")
        return lines

    def _narrate_visual(self, v: Dict[str, Any]) -> List[str]:
        lines = []
        idv = v["image_diversity"]
        lines.append(f"이미지 {idv['total_images']}장 중 product {idv['product']} / "
                     f"lifestyle {idv['lifestyle']} ({idv['lifestyle_ratio_pct']}%) / 미분류 {idv['unclassified']}")

        alt = v["alt_text_quality"]
        lines.append(f"alt 텍스트 품질 — 설명적 {alt['설명적']} / 일반적(제네릭) {alt['일반적']} / "
                     f"비어있음 {alt['비어있음']} (설명적 비율 {alt['descriptive_ratio_pct']}%)")
        gap_pages = alt.get("gap_pages") or []
        if gap_pages:
            sample = ", ".join(_readable_path(x.get("url", "")) for x in gap_pages[:3])
            lines.append(f"alt.copy 보강 필요 페이지 {len(gap_pages)}건 — 대표: {sample}")
        samples = alt.get("samples") or []
        if samples:
            sample_text = " / ".join(_s(x.get("alt"))[:45] for x in samples[:3])
            lines.append(f"설명적 alt.copy 샘플: {sample_text}")

        tactics = v.get("visual_tactics", {})
        dist = tactics.get("distribution") or {}
        if dist:
            ordered = sorted(dist.items(), key=lambda x: -x[1])[:4]
            lines.append("비주얼 택틱 분포: " + ", ".join(f"{name} {count}p" for name, count in ordered))
        role_summary = tactics.get("role_summary") or {}
        if role_summary:
            parts = []
            for role, vals in role_summary.items():
                parts.append(f"{role} 평균 이미지 {vals.get('avg_images', 0)}장/단어 {vals.get('avg_words', 0)}")
            lines.append("페이지 역할별 Visual/페이지 길이: " + " / ".join(parts[:6]))

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

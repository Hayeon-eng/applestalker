"""Diff Engine main module.

GitHub Web Editor에서 수정 가능하도록 구현을 2개 파일로만 분리했다.
- diff_engine.py: DiffEngine 본체와 기존 public API 호환 함수
- diff_engine_helpers.py: 이벤트 타입, 텍스트/구조/이미지 helper
"""
from __future__ import annotations
import base64
import io
import re
from typing import Any, Dict, List, Optional

from diff_engine_helpers import (
    ChangeEvent,
    SEVERITY_LABEL,
    SEVERITY_ORDER,
    SEVERITY_TO_LEGACY,
    _comparison_text,
    _copy_change_is_meaningful,
    _copy_importance_note,
    _dom_severity_level,
    _is_campaign_copy,
    _is_critical,
    _is_minor_ui_text,
    _meaningful_tag_deltas,
    _normalize_image_src,
    _s,
    _short_list_delta,
    _tag_count_delta,
    average_hash,
    char_diff,
    classify_text_severity,
    dom_fingerprint,
    hamming_distance,
    stable_snapshot_fingerprint,
    stable_text,
    structural_signature,
    token_sentence_diff,
)

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

        # [FIX] 렌더링 방식(httpx/playwright)이 직전 스냅샷과 다르면 body_content/DOM/이미지처럼
        # 추출 방식에 민감한 영역은 대량 오탐이 날 수 있다. 다만 title/meta/h1/canonical/schema_type은
        # 비교적 안정적이므로 전체 diff를 버리지 않고 안정 필드만 비교한다.
        prev_rb, cur_rb = previous.get("rendered_by"), current.get("rendered_by")
        render_mismatch = bool(prev_rb) and bool(cur_rb) and prev_rb != cur_rb
        render_evidence = {
            "render_mismatch_baseline_reset": True,
            "previous_rendered_by": prev_rb,
            "current_rendered_by": cur_rb,
            "comparison_scope": "렌더링 방식 변경 회차라 body/DOM/CTA/FAQ/이미지 비교는 새 기준선으로만 저장하고, 안정 필드만 비교",
        } if render_mismatch else {}

        prev_fp = stable_snapshot_fingerprint(previous)
        cur_fp = stable_snapshot_fingerprint(current)
        if prev_fp and cur_fp and prev_fp == cur_fp:
            return []

        # 1) 텍스트 필드 (char + token/sentence)
        for fld, ctype in self.TEXT_FIELDS.items():
            if render_mismatch and fld == "body_content":
                continue
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
            evidence = {
                "sentences_added": ts["sentences_added"][:5],
                "sentences_removed": ts["sentences_removed"][:5],
                "copy_importance": _copy_importance_note(fld, b_cmp, a_cmp),
                "comparison_note": "헤더·푸터·메뉴·쿠키·추천 영역은 페이지마다 반복되는 공통 요소라 제외하고, 실제 콘텐츠 카피만 비교했습니다." if fld == "body_content" else "",
            }
            if render_evidence:
                evidence.update(render_evidence)
            events.append(ChangeEvent(
                url=url, site_key=site_key, tier_level=tier_level,
                field_name=fld, change_type=ctype2,
                severity_level=sev, severity_legacy=SEVERITY_TO_LEGACY[sev],
                summary=self._text_summary(fld, b_cmp, a_cmp, ts),
                before_value=(b_cmp if fld == "body_content" else b)[:1000] or None,
                after_value=(a_cmp if fld == "body_content" else a)[:1000] or None,
                char_added=cd["char_added"], char_removed=cd["char_removed"],
                diff_ratio=cd["diff_ratio"],
                evidence=evidence,
            ))

        # 2) 구조 (DOM / nav / schema) — L4
        cs = structural_signature(current)
        ps = previous.get("_sig") or (structural_signature(previous) if previous.get("html_content") else {})
        events.extend(self._structural_events(
            url, site_key, tier_level, cs, ps,
            schema_only=render_mismatch,
            evidence_extra=render_evidence,
        ))

        # 렌더링 방식이 바뀐 회차는 추출 방식에 민감한 CTA/FAQ/이미지/DOM 비교를 스킵한다.
        # 현재 스냅샷은 crawl_service에서 저장되므로 다음 회차부터는 새 기준선으로 정상 비교된다.
        if render_mismatch:
            return events

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

    def _structural_events(self, url, site_key, tier, cs, ps,
                           schema_only: bool = False,
                           evidence_extra: Optional[Dict[str, Any]] = None) -> List[ChangeEvent]:
        out = []
        if not ps:
            return out
        evidence_extra = evidence_extra or {}
        # 스키마 타입 변화
        c_sch, p_sch = set(cs.get("schema_types", [])), set(ps.get("schema_types", []))
        for t in sorted(c_sch - p_sch):
            evidence = {"kind": "schema_added", "type": t}
            evidence.update(evidence_extra)
            out.append(self._mk(url, site_key, tier, "schema_type", "technical", "L4",
                                 f"스키마 신규: {t}", after=t,
                                 evidence=evidence))
        for t in sorted(p_sch - c_sch):
            evidence = {"kind": "schema_removed", "type": t}
            evidence.update(evidence_extra)
            out.append(self._mk(url, site_key, tier, "schema_type", "technical", "L4",
                                 f"스키마 제거: {t}", before=t,
                                 evidence=evidence))

        # 스키마 속성 변화: 타입은 유지됐지만 Product/offers/review 등 세부 property가 바뀐 경우 보강 감지
        c_props, p_props = cs.get("schema_props_by_type") or {}, ps.get("schema_props_by_type") or {}
        for typ in sorted(set(c_props) | set(p_props)):
            added = sorted(set(c_props.get(typ, [])) - set(p_props.get(typ, [])))
            removed = sorted(set(p_props.get(typ, [])) - set(c_props.get(typ, [])))
            if not added and not removed:
                continue
            severity = "L4" if typ in ("Product", "FAQPage", "BreadcrumbList") else "L3"
            evidence = {"kind": "schema_property_delta", "type": typ, "added": added[:10], "removed": removed[:10]}
            evidence.update(evidence_extra)
            out.append(self._mk(url, site_key, tier, "schema_property", "technical", severity,
                                 f"스키마 속성 변경: {typ} (+{len(added)}/-{len(removed)})",
                                 before=", ".join(removed[:12]) or None,
                                 after=", ".join(added[:12]) or None, evidence=evidence))
        if schema_only:
            return out
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

__all__ = [
    "ChangeEvent",
    "DiffEngine",
    "SEVERITY_LABEL",
    "SEVERITY_ORDER",
    "SEVERITY_TO_LEGACY",
    "average_hash",
    "char_diff",
    "classify_text_severity",
    "diff_regions",
    "dom_fingerprint",
    "hamming_distance",
    "stable_snapshot_fingerprint",
    "stable_text",
    "structural_signature",
    "summarize_events",
    "thumbnail_b64",
    "token_sentence_diff",
]

"""
Change Detection Engine — Fully defensive version
모든 감지 단계가 독립 try/except으로 감싸져 있어 하나 실패해도 나머지 계속 진행
"""

import difflib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Change:
    url: str
    change_type: str
    change_category: str
    field_name: Optional[str] = None
    before_value: Optional[str] = None
    after_value: Optional[str] = None
    severity: str = "medium"
    severity_reason: Optional[str] = None
    tier_level: int = 3
    detected_at: datetime = field(default_factory=datetime.utcnow)


def _safe_str(val) -> str:
    return str(val) if val is not None else ""


def _safe_list(val) -> List[str]:
    """Returns a flat list of strings, safe for set()"""
    if not val:
        return []
    result = []
    for item in val:
        if item is None:
            continue
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, (list, tuple)):
            result.extend(str(x) for x in item if x is not None)
        else:
            result.append(str(item))
    return result


class ChangeDetectionEngine:
    TIER_WEIGHTS = {0: 0.5, 1: 0.7, 2: 1.0, 3: 1.2, 4: 1.1, 5: 0.9, 6: 1.0}

    CHANGE_SEVERITY = {
        ("navigation", "added"): "high",
        ("navigation", "removed"): "high",
        ("navigation", "reordered"): "medium",
        ("content", "headline"): "medium",
        ("content", "copy"): "low",
        ("content", "faq_added"): "high",
        ("content", "faq_removed"): "high",
        ("content", "section_added"): "medium",
        ("content", "section_removed"): "medium",
        ("commerce", "buy_flow"): "high",
        ("commerce", "cta_added"): "medium",
        ("commerce", "cta_removed"): "medium",
        ("technical", "metadata"): "low",
        ("technical", "canonical"): "high",
        ("technical", "structured_data"): "medium",
        ("url", "new"): "critical",
        ("url", "removed"): "high",
        ("url", "redirect"): "high",
    }

    def __init__(self):
        self.changes: List[Change] = []

    def detect_all_changes(
        self,
        current_data: Dict[str, Any],
        previous_data: Dict[str, Any],
        site_name: str,
    ) -> List[Change]:
        self.changes = []

        steps = [
            ("URL changes",        self._detect_url_changes),
            ("Navigation changes", self._detect_navigation_changes),
            ("Content changes",    self._detect_content_changes),
            ("Commerce changes",   self._detect_commerce_changes),
            ("Technical changes",  self._detect_technical_changes),
            ("FAQ changes",        self._detect_faq_changes),
            ("Schema changes",     self._detect_structured_data_changes),
        ]

        for name, fn in steps:
            try:
                fn(current_data, previous_data)
            except Exception as e:
                # One step failing must NOT stop the rest
                from loguru import logger
                logger.warning(f"Change detection step [{name}] failed: {e}")

        return self.changes

    # ── URL Changes ──────────────────────────────────

    def _detect_url_changes(self, current: Dict, previous: Dict):
        current_urls = set(str(u) for u in (current.get("urls") or set()) if u)
        previous_urls = set(str(u) for u in (previous.get("urls") or set()) if u)

        for url in current_urls - previous_urls:
            tier = self._get_tier_for_url(url)
            self.changes.append(Change(
                url=url,
                change_type="url",
                change_category="new",
                severity="critical" if tier <= 2 else "high",
                severity_reason="New URL discovered",
                tier_level=tier,
            ))

        for url in previous_urls - current_urls:
            tier = self._get_tier_for_url(url)
            self.changes.append(Change(
                url=url,
                change_type="url",
                change_category="removed",
                severity="critical" if tier <= 2 else "high",
                severity_reason="URL removed",
                tier_level=tier,
            ))

    # ── Navigation Changes ────────────────────────────

    def _detect_navigation_changes(self, current: Dict, previous: Dict):
        current_nav = current.get("navigation") or {}
        previous_nav = previous.get("navigation") or {}

        current_main = current_nav.get("main") or []
        previous_main = previous_nav.get("main") or []

        if not isinstance(current_main, list):
            current_main = []
        if not isinstance(previous_main, list):
            previous_main = []

        current_texts = {_safe_str(i.get("text") if isinstance(i, dict) else i) for i in current_main}
        previous_texts = {_safe_str(i.get("text") if isinstance(i, dict) else i) for i in previous_main}

        for text in current_texts - previous_texts:
            if not text:
                continue
            self.changes.append(Change(
                url="",
                change_type="navigation",
                change_category="added",
                field_name="main_navigation",
                after_value=text,
                severity="high",
                severity_reason="New navigation item added",
                tier_level=1,
            ))

        for text in previous_texts - current_texts:
            if not text:
                continue
            self.changes.append(Change(
                url="",
                change_type="navigation",
                change_category="removed",
                field_name="main_navigation",
                before_value=text,
                severity="high",
                severity_reason="Navigation item removed",
                tier_level=1,
            ))

    # ── Content Changes ───────────────────────────────

    def _detect_content_changes(self, current: Dict, previous: Dict):
        current_pages = current.get("pages") or {}
        previous_pages = previous.get("pages") or {}
        common_urls = set(current_pages.keys()) & set(previous_pages.keys())

        for url in common_urls:
            try:
                cp = current_pages[url] or {}
                pp = previous_pages[url] or {}
                tier = self._get_tier_for_url(url)

                # H1
                if _safe_str(cp.get("h1")) != _safe_str(pp.get("h1")):
                    self.changes.append(Change(
                        url=url,
                        change_type="content",
                        change_category="headline",
                        field_name="h1",
                        before_value=_safe_str(pp.get("h1"))[:500],
                        after_value=_safe_str(cp.get("h1"))[:500],
                        severity=self._calculate_severity("content", "headline", tier),
                        severity_reason="Main headline changed",
                        tier_level=tier,
                    ))

                # H2 sections — use _safe_list to avoid unhashable errors
                current_h2s = set(_safe_list(cp.get("h2")))
                previous_h2s = set(_safe_list(pp.get("h2")))

                for h2 in current_h2s - previous_h2s:
                    self.changes.append(Change(
                        url=url, change_type="content", change_category="section_added",
                        field_name="h2", after_value=h2[:500], severity="medium",
                        severity_reason="New section added", tier_level=tier,
                    ))
                for h2 in previous_h2s - current_h2s:
                    self.changes.append(Change(
                        url=url, change_type="content", change_category="section_removed",
                        field_name="h2", before_value=h2[:500], severity="medium",
                        severity_reason="Section removed", tier_level=tier,
                    ))

                # Body content similarity
                current_body = _safe_str(cp.get("body_content"))[:10000]
                previous_body = _safe_str(pp.get("body_content"))[:10000]
                if current_body and previous_body:
                    similarity = self._text_similarity(current_body, previous_body)
                    if similarity < 0.8:
                        diff = self._get_diff_summary(previous_body, current_body)
                        self.changes.append(Change(
                            url=url, change_type="content", change_category="copy",
                            field_name="body_content",
                            before_value=(diff.get("removed") or "")[:500],
                            after_value=(diff.get("added") or "")[:500],
                            severity=self._calculate_severity("content", "copy", tier),
                            severity_reason=f"Content changed ({(1-similarity)*100:.0f}% difference)",
                            tier_level=tier,
                        ))

            except Exception as e:
                from loguru import logger
                logger.warning(f"Content change detection failed for {url}: {e}")

    # ── Commerce Changes ──────────────────────────────

    def _detect_commerce_changes(self, current: Dict, previous: Dict):
        current_pages = current.get("pages") or {}
        previous_pages = previous.get("pages") or {}

        for url in set(current_pages.keys()) & set(previous_pages.keys()):
            try:
                cp = current_pages[url] or {}
                pp = previous_pages[url] or {}
                tier = self._get_tier_for_url(url)

                def cta_texts(page):
                    ctas = page.get("ctas") or []
                    return {_safe_str(c.get("text") if isinstance(c, dict) else c) for c in ctas}

                for text in cta_texts(cp) - cta_texts(pp):
                    if text:
                        self.changes.append(Change(
                            url=url, change_type="commerce", change_category="cta_added",
                            field_name="cta", after_value=text[:500],
                            severity="medium", severity_reason="New CTA added", tier_level=tier,
                        ))
                for text in cta_texts(pp) - cta_texts(cp):
                    if text:
                        self.changes.append(Change(
                            url=url, change_type="commerce", change_category="cta_removed",
                            field_name="cta", before_value=text[:500],
                            severity="medium", severity_reason="CTA removed", tier_level=tier,
                        ))
            except Exception as e:
                from loguru import logger
                logger.warning(f"Commerce change detection failed for {url}: {e}")

    # ── Technical Changes ─────────────────────────────

    def _detect_technical_changes(self, current: Dict, previous: Dict):
        current_pages = current.get("pages") or {}
        previous_pages = previous.get("pages") or {}

        for url in set(current_pages.keys()) & set(previous_pages.keys()):
            try:
                cp = current_pages[url] or {}
                pp = previous_pages[url] or {}
                tier = self._get_tier_for_url(url)

                for field_name, severity, reason in [
                    ("canonical_url", "high", "Canonical URL changed"),
                    ("title", "medium", "Page title changed"),
                    ("meta_description", "low", "Meta description changed"),
                ]:
                    if _safe_str(cp.get(field_name)) != _safe_str(pp.get(field_name)):
                        self.changes.append(Change(
                            url=url, change_type="technical",
                            change_category="metadata" if field_name != "canonical_url" else "canonical",
                            field_name=field_name,
                            before_value=_safe_str(pp.get(field_name))[:500],
                            after_value=_safe_str(cp.get(field_name))[:500],
                            severity=severity, severity_reason=reason, tier_level=tier,
                        ))
            except Exception as e:
                from loguru import logger
                logger.warning(f"Technical change detection failed for {url}: {e}")

    # ── FAQ Changes ───────────────────────────────────

    def _detect_faq_changes(self, current: Dict, previous: Dict):
        current_pages = current.get("pages") or {}
        previous_pages = previous.get("pages") or {}

        for url in set(current_pages.keys()) & set(previous_pages.keys()):
            try:
                cp = current_pages[url] or {}
                pp = previous_pages[url] or {}
                tier = self._get_tier_for_url(url)

                def faq_questions(page):
                    faqs = page.get("faqs") or []
                    return {_safe_str(f.get("question") if isinstance(f, dict) else f) for f in faqs}

                for q in faq_questions(cp) - faq_questions(pp):
                    if q:
                        self.changes.append(Change(
                            url=url, change_type="content", change_category="faq_added",
                            field_name="faq", after_value=q[:500],
                            severity="high", severity_reason="New FAQ added (GEO signal)", tier_level=tier,
                        ))
                for q in faq_questions(pp) - faq_questions(cp):
                    if q:
                        self.changes.append(Change(
                            url=url, change_type="content", change_category="faq_removed",
                            field_name="faq", before_value=q[:500],
                            severity="high", severity_reason="FAQ removed", tier_level=tier,
                        ))
            except Exception as e:
                from loguru import logger
                logger.warning(f"FAQ change detection failed for {url}: {e}")

    # ── Structured Data Changes ───────────────────────

    def _detect_structured_data_changes(self, current: Dict, previous: Dict):
        current_pages = current.get("pages") or {}
        previous_pages = previous.get("pages") or {}

        for url in set(current_pages.keys()) & set(previous_pages.keys()):
            try:
                cp = current_pages[url] or {}
                pp = previous_pages[url] or {}
                tier = self._get_tier_for_url(url)

                def schema_types(page):
                    schemas = page.get("structured_data") or []
                    types = set()
                    for s in schemas:
                        if not isinstance(s, dict):
                            continue
                        t = s.get("@type")
                        if isinstance(t, str):
                            types.add(t)
                        elif isinstance(t, list):
                            types.update(_safe_str(x) for x in t if x)
                        # @graph pattern
                        for item in (s.get("@graph") or []):
                            if isinstance(item, dict):
                                gt = item.get("@type")
                                if gt:
                                    types.add(_safe_str(gt))
                    return types

                ct = schema_types(cp)
                pt = schema_types(pp)

                for sd_type in ct - pt:
                    self.changes.append(Change(
                        url=url, change_type="technical", change_category="structured_data",
                        field_name="schema_type", after_value=sd_type,
                        severity="medium", severity_reason=f"New schema: {sd_type}", tier_level=tier,
                    ))
                for sd_type in pt - ct:
                    self.changes.append(Change(
                        url=url, change_type="technical", change_category="structured_data",
                        field_name="schema_type", before_value=sd_type,
                        severity="medium", severity_reason=f"Schema removed: {sd_type}", tier_level=tier,
                    ))
            except Exception as e:
                from loguru import logger
                logger.warning(f"Schema change detection failed for {url}: {e}")

    # ── Helpers ───────────────────────────────────────

    def _get_tier_for_url(self, url: str) -> int:
        try:
            from urllib.parse import urlparse
            path = urlparse(_safe_str(url)).path.lower()
            segments = [s for s in path.split("/") if s]
            if not segments:
                return 0
            if any(kw in path for kw in ["iphone", "galaxy", "macbook", "watch", "qled"]):
                return 3
            if any(kw in path for kw in ["buy", "shop", "purchase", "trade"]):
                return 4
            if any(kw in path for kw in ["support", "help", "faq"]):
                return 5
            return min(len(segments), 3)
        except Exception:
            return 3

    def _calculate_severity(self, change_type: str, change_category: str, tier: int) -> str:
        base = self.CHANGE_SEVERITY.get((change_type, change_category), "medium")
        weight = self.TIER_WEIGHTS.get(tier, 1.0)
        if weight >= 1.2 and base == "medium":
            return "high"
        if weight >= 1.0 and base == "low":
            return "medium"
        return base

    def _text_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        try:
            return difflib.SequenceMatcher(None, text1, text2).ratio()
        except Exception:
            return 0.0

    def _get_diff_summary(self, text1: str, text2: str) -> Dict[str, str]:
        try:
            diff = list(difflib.ndiff(text1.splitlines()[:200], text2.splitlines()[:200]))
            added = "\n".join(l[2:] for l in diff if l.startswith("+ "))[:500]
            removed = "\n".join(l[2:] for l in diff if l.startswith("- "))[:500]
            return {"added": added, "removed": removed}
        except Exception:
            return {"added": "", "removed": ""}

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_changes": len(self.changes),
            "critical": sum(1 for c in self.changes if c.severity == "critical"),
            "high": sum(1 for c in self.changes if c.severity == "high"),
            "medium": sum(1 for c in self.changes if c.severity == "medium"),
            "low": sum(1 for c in self.changes if c.severity == "low"),
        }

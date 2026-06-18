"""
Change Detection Engine
Detects changes between crawl runs including navigation, content, commerce, and technical changes.
"""

import difflib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Change:
    """Represents a detected change"""
    url: str
    change_type: str  # navigation, content, commerce, technical, url
    change_category: str  # added, removed, reordered, modified
    field_name: Optional[str] = None
    before_value: Optional[str] = None
    after_value: Optional[str] = None
    severity: str = "medium"  # critical, high, medium, low
    severity_reason: Optional[str] = None
    tier_level: int = 3
    detected_at: datetime = field(default_factory=datetime.utcnow)


class ChangeDetectionEngine:
    """
    Detects changes between current and previous crawl data.
    Higher weight for Tier 2-6 changes.
    """

    # Severity weights by tier
    TIER_WEIGHTS = {
        0: 0.5,  # Homepage - lower weight (expected to change)
        1: 0.7,  # Global Nav
        2: 1.0,  # Sub Nav
        3: 1.2,  # Product Pages - highest weight
        4: 1.1,  # Commerce
        5: 0.9,  # Support
        6: 1.0,  # Internal Links
    }

    # Change type severity mapping
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
        """
        Detect all types of changes between current and previous crawl.

        Args:
            current_data: Current crawl data with URLs and page data
            previous_data: Previous crawl data
            site_name: 'apple' or 'samsung'

        Returns:
            List of detected changes
        """
        self.changes = []

        # 1. URL Changes (new, removed, redirect)
        self._detect_url_changes(current_data, previous_data)

        # 2. Navigation Changes
        self._detect_navigation_changes(current_data, previous_data)

        # 3. Content Changes
        self._detect_content_changes(current_data, previous_data)

        # 4. Commerce Changes
        self._detect_commerce_changes(current_data, previous_data)

        # 5. Technical Changes
        self._detect_technical_changes(current_data, previous_data)

        # 6. FAQ Changes
        self._detect_faq_changes(current_data, previous_data)

        # 7. Structured Data Changes
        self._detect_structured_data_changes(current_data, previous_data)

        return self.changes

    def _detect_url_changes(self, current: Dict, previous: Dict):
        """Detect new, removed, and redirected URLs"""
        current_urls = set(current.get("urls", set()))
        previous_urls = set(previous.get("urls", set()))

        # New URLs
        for url in current_urls - previous_urls:
            tier = self._get_tier_for_url(url)
            severity = "critical" if tier <= 2 else "high"
            self.changes.append(Change(
                url=url,
                change_type="url",
                change_category="new",
                severity=severity,
                severity_reason="New URL discovered" if tier <= 2 else "New page added",
                tier_level=tier,
            ))

        # Removed URLs
        for url in previous_urls - current_urls:
            tier = self._get_tier_for_url(url)
            severity = "critical" if tier <= 2 else "high"
            self.changes.append(Change(
                url=url,
                change_type="url",
                change_category="removed",
                severity=severity,
                severity_reason="URL no longer accessible" if tier <= 2 else "Page removed",
                tier_level=tier,
            ))

    def _detect_navigation_changes(self, current: Dict, previous: Dict):
        """Detect navigation structure changes"""
        current_nav = current.get("navigation", {})
        previous_nav = previous.get("navigation", {})

        # Compare main navigation
        current_main = current_nav.get("main", [])
        previous_main = previous_nav.get("main", [])

        # Check for added/removed nav items
        current_texts = {item.get("text", "") for item in current_main}
        previous_texts = {item.get("text", "") for item in previous_main}

        for text in current_texts - previous_texts:
            item = next((i for i in current_main if i.get("text") == text), {})
            self.changes.append(Change(
                url=item.get("href", ""),
                change_type="navigation",
                change_category="added",
                field_name="main_navigation",
                after_value=text,
                severity="high",
                severity_reason="New navigation item added",
                tier_level=1,
            ))

        for text in previous_texts - current_texts:
            item = next((i for i in previous_main if i.get("text") == text), {})
            self.changes.append(Change(
                url=item.get("href", ""),
                change_type="navigation",
                change_category="removed",
                field_name="main_navigation",
                before_value=text,
                severity="high",
                severity_reason="Navigation item removed",
                tier_level=1,
            ))

        # Check for reordering
        if current_texts == previous_texts and len(current_main) == len(previous_main):
            if self._is_reordered(current_main, previous_main):
                self.changes.append(Change(
                    url="",
                    change_type="navigation",
                    change_category="reordered",
                    field_name="main_navigation",
                    severity="medium",
                    severity_reason="Navigation order changed",
                    tier_level=1,
                ))

    def _detect_content_changes(self, current: Dict, previous: Dict):
        """Detect content changes (headlines, copy, sections)"""
        current_pages = current.get("pages", {})
        previous_pages = previous.get("pages", {})

        common_urls = set(current_pages.keys()) & set(previous_pages.keys())

        for url in common_urls:
            current_page = current_pages[url]
            previous_page = previous_pages[url]

            # H1 changes
            if current_page.get("h1") != previous_page.get("h1"):
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="content",
                    change_category="headline",
                    field_name="h1",
                    before_value=previous_page.get("h1", ""),
                    after_value=current_page.get("h1", ""),
                    severity=self._calculate_severity("content", "headline", tier),
                    severity_reason="Main headline changed",
                    tier_level=tier,
                ))

            # H2 changes (added/removed)
            current_h2s = set(current_page.get("h2", []))
            previous_h2s = set(previous_page.get("h2", []))

            for h2 in current_h2s - previous_h2s:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="content",
                    change_category="section_added",
                    field_name="h2",
                    after_value=h2,
                    severity="medium",
                    severity_reason="New section added",
                    tier_level=tier,
                ))

            for h2 in previous_h2s - current_h2s:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="content",
                    change_category="section_removed",
                    field_name="h2",
                    before_value=h2,
                    severity="medium",
                    severity_reason="Section removed",
                    tier_level=tier,
                ))

            # Body content changes (significant changes only)
            current_body = current_page.get("body_content", "")
            previous_body = previous_page.get("body_content", "")

            if current_body and previous_body:
                similarity = self._text_similarity(current_body, previous_body)
                if similarity < 0.8:  # More than 20% change
                    tier = self._get_tier_for_url(url)
                    diff_summary = self._get_diff_summary(previous_body, current_body)
                    self.changes.append(Change(
                        url=url,
                        change_type="content",
                        change_category="copy",
                        field_name="body_content",
                        before_value=diff_summary.get("removed", "")[:500],
                        after_value=diff_summary.get("added", "")[:500],
                        severity=self._calculate_severity("content", "copy", tier),
                        severity_reason=f"Content changed ({(1-similarity)*100:.0f}% difference)",
                        tier_level=tier,
                    ))

    def _detect_commerce_changes(self, current: Dict, previous: Dict):
        """Detect commerce-related changes (CTAs, buy flows)"""
        current_pages = current.get("pages", {})
        previous_pages = previous.get("pages", {})

        common_urls = set(current_pages.keys()) & set(previous_pages.keys())

        for url in common_urls:
            current_page = current_pages[url]
            previous_page = previous_pages[url]

            # CTA changes
            current_ctas = current_page.get("ctas", [])
            previous_ctas = previous_page.get("ctas", [])

            current_cta_texts = {cta.get("text", "") for cta in current_ctas}
            previous_cta_texts = {cta.get("text", "") for cta in previous_ctas}

            for cta_text in current_cta_texts - previous_cta_texts:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="commerce",
                    change_category="cta_added",
                    field_name="cta",
                    after_value=cta_text,
                    severity="medium",
                    severity_reason="New CTA added",
                    tier_level=tier,
                ))

            for cta_text in previous_cta_texts - current_cta_texts:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="commerce",
                    change_category="cta_removed",
                    field_name="cta",
                    before_value=cta_text,
                    severity="medium",
                    severity_reason="CTA removed",
                    tier_level=tier,
                ))

    def _detect_technical_changes(self, current: Dict, previous: Dict):
        """Detect technical SEO changes (metadata, canonical)"""
        current_pages = current.get("pages", {})
        previous_pages = previous.get("pages", {})

        common_urls = set(current_pages.keys()) & set(previous_pages.keys())

        for url in common_urls:
            current_page = current_pages[url]
            previous_page = previous_pages[url]

            # Canonical URL changes
            if current_page.get("canonical_url") != previous_page.get("canonical_url"):
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="technical",
                    change_category="canonical",
                    field_name="canonical_url",
                    before_value=previous_page.get("canonical_url", ""),
                    after_value=current_page.get("canonical_url", ""),
                    severity="high",
                    severity_reason="Canonical URL changed",
                    tier_level=tier,
                ))

            # Title changes
            if current_page.get("title") != previous_page.get("title"):
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="technical",
                    change_category="metadata",
                    field_name="title",
                    before_value=previous_page.get("title", ""),
                    after_value=current_page.get("title", ""),
                    severity="medium",
                    severity_reason="Page title changed",
                    tier_level=tier,
                ))

            # Meta description changes
            if current_page.get("meta_description") != previous_page.get("meta_description"):
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="technical",
                    change_category="metadata",
                    field_name="meta_description",
                    before_value=previous_page.get("meta_description", "")[:200],
                    after_value=current_page.get("meta_description", "")[:200],
                    severity="low",
                    severity_reason="Meta description changed",
                    tier_level=tier,
                ))

    def _detect_faq_changes(self, current: Dict, previous: Dict):
        """Detect FAQ changes"""
        current_pages = current.get("pages", {})
        previous_pages = previous.get("pages", {})

        common_urls = set(current_pages.keys()) & set(previous_pages.keys())

        for url in common_urls:
            current_page = current_pages[url]
            previous_page = previous_pages[url]

            current_faqs = current_page.get("faqs", [])
            previous_faqs = previous_page.get("faqs", [])

            current_questions = {faq.get("question", "") for faq in current_faqs}
            previous_questions = {faq.get("question", "") for faq in previous_faqs}

            # New FAQs
            for question in current_questions - previous_questions:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="content",
                    change_category="faq_added",
                    field_name="faq",
                    after_value=question,
                    severity="high",
                    severity_reason="New FAQ added (GEO signal)",
                    tier_level=tier,
                ))

            # Removed FAQs
            for question in previous_questions - current_questions:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="content",
                    change_category="faq_removed",
                    field_name="faq",
                    before_value=question,
                    severity="high",
                    severity_reason="FAQ removed",
                    tier_level=tier,
                ))

    def _detect_structured_data_changes(self, current: Dict, previous: Dict):
        """Detect structured data (JSON-LD) changes"""
        current_pages = current.get("pages", {})
        previous_pages = previous.get("pages", {})

        common_urls = set(current_pages.keys()) & set(previous_pages.keys())

        for url in common_urls:
            current_page = current_pages[url]
            previous_page = previous_pages[url]

            current_sd = current_page.get("structured_data", [])
            previous_sd = previous_page.get("structured_data", [])

            # Compare structured data types
            current_types = {sd.get("@type", "") for sd in current_sd if isinstance(sd, dict)}
            previous_types = {sd.get("@type", "") for sd in previous_sd if isinstance(sd, dict)}

            for sd_type in current_types - previous_types:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="technical",
                    change_category="structured_data",
                    field_name="structured_data_type",
                    after_value=sd_type,
                    severity="medium",
                    severity_reason=f"New structured data type: {sd_type}",
                    tier_level=tier,
                ))

            for sd_type in previous_types - current_types:
                tier = self._get_tier_for_url(url)
                self.changes.append(Change(
                    url=url,
                    change_type="technical",
                    change_category="structured_data",
                    field_name="structured_data_type",
                    before_value=sd_type,
                    severity="medium",
                    severity_reason=f"Structured data type removed: {sd_type}",
                    tier_level=tier,
                ))

    def _get_tier_for_url(self, url: str) -> int:
        """Determine tier level from URL"""
        from urllib.parse import urlparse

        path = urlparse(url).path.lower()
        segments = [s for s in path.split("/") if s]

        if not segments:
            return 0

        # Product pages
        if any(kw in path for kw in ["iphone", "galaxy", "macbook", "watch", "qled", "neo"]):
            return 3

        # Commerce
        if any(kw in path for kw in ["buy", "shop", "purchase", "trade"]):
            return 4

        # Support
        if any(kw in path for kw in ["support", "help", "faq"]):
            return 5

        # Compare/features
        if any(kw in path for kw in ["compare", "features", "specs"]):
            return 6

        # Default based on depth
        if len(segments) == 1:
            return 1
        elif len(segments) == 2:
            return 2
        else:
            return 3

    def _calculate_severity(self, change_type: str, change_category: str, tier: int) -> str:
        """Calculate severity based on change type and tier"""
        base_severity = self.CHANGE_SEVERITY.get(
            (change_type, change_category), "medium"
        )

        # Adjust based on tier weight
        weight = self.TIER_WEIGHTS.get(tier, 1.0)

        if weight >= 1.2 and base_severity == "medium":
            return "high"
        elif weight >= 1.0 and base_severity == "low":
            return "medium"

        return base_severity

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher"""
        if not text1 or not text2:
            return 0.0

        # Use first 10000 chars for performance
        text1 = text1[:10000]
        text2 = text2[:10000]

        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _get_diff_summary(self, text1: str, text2: str) -> Dict[str, str]:
        """Get a summary of text differences"""
        diff = difflib.ndiff(text1.splitlines(), text2.splitlines())

        added = []
        removed = []

        for line in diff:
            if line.startswith("+ "):
                added.append(line[2:])
            elif line.startswith("- "):
                removed.append(line[2:])

        return {
            "added": "\n".join(added[:50]),
            "removed": "\n".join(removed[:50]),
        }

    def _is_reordered(self, current: List, previous: List) -> bool:
        """Check if list items have been reordered"""
        if len(current) != len(previous):
            return False

        current_texts = [item.get("text", "") for item in current]
        previous_texts = [item.get("text", "") for item in previous]

        return current_texts != previous_texts and set(current_texts) == set(previous_texts)

    def get_changes_by_severity(self, severity: str) -> List[Change]:
        """Get changes filtered by severity"""
        return [c for c in self.changes if c.severity == severity]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all detected changes"""
        return {
            "total_changes": len(self.changes),
            "by_type": self._count_by_field("change_type"),
            "by_category": self._count_by_field("change_category"),
            "by_severity": self._count_by_field("severity"),
            "critical_count": len(self.get_changes_by_severity("critical")),
            "high_count": len(self.get_changes_by_severity("high")),
            "medium_count": len(self.get_changes_by_severity("medium")),
            "low_count": len(self.get_changes_by_severity("low")),
        }

    def _count_by_field(self, field: str) -> Dict[str, int]:
        """Count changes by a specific field"""
        counts = {}
        for change in self.changes:
            value = getattr(change, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

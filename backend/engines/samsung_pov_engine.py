"""
Samsung POV Engine
Generates Samsung Point of View recommendations based on observed changes.
Structure: Observation → Evidence → Hypothesis → Opportunity → Action
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SamsungPOV:
    """Samsung Point of View recommendation"""
    observation: str  # Actual change observed
    evidence: str  # Evidence supporting observation
    hypothesis: str  # Possible intent behind change
    opportunity: str  # Samsung opportunity area
    recommended_action: str  # Actionable recommendation
    priority: str = "medium"  # critical, high, medium, low
    functional_area: str = ""  # content, seo, geo, ux, commerce, schema, analytics
    created_at: datetime = field(default_factory=datetime.utcnow)


class SamsungPOVEngine:
    """
    Generates Samsung POV recommendations from observed changes.
    
    Output Structure:
    - Observation: What actually changed
    - Evidence: Supporting data
    - Hypothesis: Possible strategic intent
    - Opportunity: Samsung's opportunity
    - Recommended Action: Specific, actionable steps
    - Priority: Critical/High/Medium/Low
    - Functional Area: Content/SEO/GEO/UX/Commerce/Schema/Analytics
    """

    # Priority mapping based on change severity and tier
    PRIORITY_RULES = {
        ("critical", "ai"): "critical",
        ("critical", "product"): "critical",
        ("high", "ai"): "critical",
        ("high", "product"): "high",
        ("high", "faq"): "high",
        ("high", "schema"): "high",
        ("medium", "ai"): "high",
        ("medium", "product"): "medium",
    }

    # Functional area keywords
    AREA_KEYWORDS = {
        "geo": ["faq", "schema", "structured data", "answer", "definition", "llm", "citation"],
        "seo": ["meta", "canonical", "title", "heading", "keyword", "structured data"],
        "content": ["headline", "copy", "section", "content", "heading"],
        "commerce": ["buy", "cta", "shop", "purchase", "trade", "finance", "promo"],
        "ux": ["navigation", "menu", "link", "layout", "structure"],
        "schema": ["structured data", "schema", "json-ld", "faqpage", "howto"],
        "analytics": ["tracking", "pixel", "tag", "measurement"],
        "ai": ["ai", "intelligence", "galaxy ai", "apple intelligence", "machine learning"],
    }

    def __init__(self):
        self.povs: List[SamsungPOV] = []

    def generate_povs(
        self,
        changes: List[Any],
        apple_data: Dict[str, Any],
        samsung_data: Dict[str, Any],
    ) -> List[SamsungPOV]:
        """
        Generate Samsung POV recommendations from changes.

        Args:
            changes: List of detected changes
            apple_data: Apple crawl data
            samsung_data: Samsung crawl data

        Returns:
            List of Samsung POV recommendations
        """
        self.povs = []

        # Group changes by type
        changes_by_type = self._group_changes(changes)

        # Generate POVs for each change category
        self._generate_faq_povs(changes_by_type.get("faq", []), apple_data, samsung_data)
        self._generate_schema_povs(changes_by_type.get("structured_data", []), apple_data, samsung_data)
        self._generate_ai_povs(changes, apple_data, samsung_data)
        self._generate_commerce_povs(changes_by_type.get("commerce", []), apple_data, samsung_data)
        self._generate_content_povs(changes_by_type.get("content", []), apple_data, samsung_data)
        self._generate_navigation_povs(changes_by_type.get("navigation", []), apple_data, samsung_data)

        return self.povs

    def _group_changes(self, changes: List[Any]) -> Dict[str, List[Any]]:
        """Group changes by type"""
        grouped = {}
        for change in changes:
            change_type = getattr(change, "change_type", "unknown")
            if change_type not in grouped:
                grouped[change_type] = []
            grouped[change_type].append(change)
        return grouped

    def _generate_faq_povs(self, faq_changes: List, apple_data: Dict, samsung_data: Dict):
        """Generate POVs for FAQ changes"""
        if not faq_changes:
            return

        added_faqs = [c for c in faq_changes if getattr(c, "change_category", "") == "faq_added"]

        if added_faqs:
            # Count total new FAQs
            faq_count = len(added_faqs)
            faq_questions = [getattr(c, "after_value", "") for c in added_faqs[:5]]

            self.povs.append(SamsungPOV(
                observation=f"Apple added {faq_count} new FAQ items across their site",
                evidence=", ".join(faq_questions),
                hypothesis="Apple is strengthening their GEO/AEO presence by expanding FAQ coverage to improve AI engine visibility",
                opportunity="Samsung should audit FAQ coverage in corresponding product pages and identify gaps",
                recommended_action=f"Review Samsung.com/sg FAQ sections and add {max(3, faq_count)} FAQs covering similar topics, especially around Galaxy AI features",
                priority="high",
                functional_area="geo",
            ))

        removed_faqs = [c for c in faq_changes if getattr(c, "change_category", "") == "faq_removed"]
        if removed_faqs:
            self.povs.append(SamsungPOV(
                observation=f"Apple removed {len(removed_faqs)} FAQ items",
                evidence="FAQs were removed from key pages",
                hypothesis="Apple may be consolidating FAQ content or removing outdated information",
                opportunity="Review if removed FAQs indicate topics that are no longer relevant or were poorly performing",
                recommended_action="Audit Samsung FAQ performance metrics and consider consolidating low-engagement FAQs",
                priority="medium",
                functional_area="content",
            ))

    def _generate_schema_povs(self, schema_changes: List, apple_data: Dict, samsung_data: Dict):
        """Generate POVs for structured data changes"""
        if not schema_changes:
            return

        new_schemas = [c for c in schema_changes if getattr(c, "change_category", "") == "structured_data"]

        if new_schemas:
            schema_types = [getattr(c, "after_value", "") for c in new_schemas if getattr(c, "after_value", "")]

            self.povs.append(SamsungPOV(
                observation=f"Apple implemented new structured data types: {', '.join(set(schema_types))}",
                evidence="New JSON-LD schemas detected on Apple.com",
                hypothesis="Apple is enhancing machine-readable content to improve search and AI engine understanding",
                opportunity="Samsung should ensure equivalent or superior structured data coverage",
                recommended_action="Audit Samsung.com/sg structured data implementation and add missing schema types, particularly FAQPage and Product schemas",
                priority="high",
                functional_area="schema",
            ))

    def _generate_ai_povs(self, all_changes: List, apple_data: Dict, samsung_data: Dict):
        """Generate POVs for AI-related changes"""
        # Look for AI-related content changes
        ai_changes = []
        for change in all_changes:
            url = getattr(change, "url", "").lower()
            field = getattr(change, "field_name", "").lower()
            before = str(getattr(change, "before_value", "")).lower()
            after = str(getattr(change, "after_value", "")).lower()

            if any(kw in url or kw in field or kw in before or kw in after
                   for kw in ["intelligence", "ai", "machine learning", "neural"]):
                ai_changes.append(change)

        if ai_changes:
            self.povs.append(SamsungPOV(
                observation="Apple made changes to AI-related content/pages",
                evidence="Updates detected in Apple Intelligence or AI feature pages",
                hypothesis="Apple is actively refining their AI messaging and feature positioning",
                opportunity="Samsung should ensure Galaxy AI messaging is equally prominent and differentiated",
                recommended_action="Review Galaxy AI landing pages and ensure clear differentiation from Apple Intelligence, emphasizing Samsung's unique AI capabilities",
                priority="critical",
                functional_area="ai",
            ))

    def _generate_commerce_povs(self, commerce_changes: List, apple_data: Dict, samsung_data: Dict):
        """Generate POVs for commerce changes"""
        if not commerce_changes:
            return

        cta_additions = [c for c in commerce_changes if getattr(c, "change_category", "") == "cta_added"]
        cta_removals = [c for c in commerce_changes if getattr(c, "change_category", "") == "cta_removed"]

        if cta_additions:
            cta_texts = [getattr(c, "after_value", "") for c in cta_additions[:5]]
            self.povs.append(SamsungPOV(
                observation=f"Apple added new CTAs: {', '.join(cta_texts)}",
                evidence="New commerce CTAs detected on product pages",
                hypothesis="Apple is testing new conversion paths or promoting specific offers",
                opportunity="Evaluate if similar CTAs could improve Samsung's conversion rates",
                recommended_action="A/B test similar CTA placements on Samsung Shop, particularly for flagship products",
                priority="medium",
                functional_area="commerce",
            ))

        if cta_removals:
            self.povs.append(SamsungPOV(
                observation="Apple removed CTAs from key pages",
                evidence="Commerce CTAs were removed from previously optimized pages",
                hypothesis="Apple may be simplifying the user journey or testing reduced commerce pressure",
                opportunity="Monitor if this indicates a shift toward education-first approach",
                recommended_action="Consider testing reduced CTA density on Samsung product pages to focus on product education",
                priority="low",
                functional_area="ux",
            ))

    def _generate_content_povs(self, content_changes: List, apple_data: Dict, samsung_data: Dict):
        """Generate POVs for content changes"""
        if not content_changes:
            return

        headline_changes = [c for c in content_changes if getattr(c, "change_category", "") == "headline"]
        section_additions = [c for c in content_changes if getattr(c, "change_category", "") == "section_added"]

        if headline_changes:
            self.povs.append(SamsungPOV(
                observation="Apple updated key headlines on product pages",
                evidence="H1/H2 headline changes detected",
                hypothesis="Apple is refining their value proposition messaging",
                opportunity="Review if Samsung headlines are equally compelling and differentiated",
                recommended_action="Audit Samsung product page headlines and ensure they clearly communicate unique value propositions",
                priority="medium",
                functional_area="content",
            ))

        if section_additions:
            sections = [getattr(c, "after_value", "") for c in section_additions[:5]]
            self.povs.append(SamsungPOV(
                observation=f"Apple added new content sections: {', '.join(sections)}",
                evidence="New H2 sections detected on product pages",
                hypothesis="Apple is expanding content coverage in these areas",
                opportunity="These topics may represent emerging customer interests or competitive pressures",
                recommended_action=f"Review Samsung content strategy and consider adding sections covering: {', '.join(sections)}",
                priority="medium",
                functional_area="content",
            ))

    def _generate_navigation_povs(self, nav_changes: List, apple_data: Dict, samsung_data: Dict):
        """Generate POVs for navigation changes"""
        if not nav_changes:
            return

        nav_additions = [c for c in nav_changes if getattr(c, "change_category", "") == "added"]
        nav_removals = [c for c in nav_changes if getattr(c, "change_category", "") == "removed"]

        if nav_additions:
            items = [getattr(c, "after_value", "") for c in nav_additions]
            self.povs.append(SamsungPOV(
                observation=f"Apple added new navigation items: {', '.join(items)}",
                evidence="New items in main navigation menu",
                hypothesis="Apple is elevating the importance of these areas, possibly indicating strategic priority",
                opportunity="Samsung should evaluate if equivalent navigation prominence is given to similar areas",
                recommended_action="Review Samsung.com/sg navigation structure and consider elevating priority areas to match Apple's IA decisions",
                priority="high",
                functional_area="ux",
            ))

        if nav_removals:
            items = [getattr(c, "before_value", "") for c in nav_removals]
            self.povs.append(SamsungPOV(
                observation=f"Apple removed navigation items: {', '.join(items)}",
                evidence="Items removed from main navigation",
                hypothesis="Apple is simplifying navigation or deprioritizing these areas",
                opportunity="Monitor if this indicates a shift in strategic focus",
                recommended_action="Evaluate if Samsung navigation has similar complexity and consider simplification opportunities",
                priority="medium",
                functional_area="ux",
            ))

    def generate_no_changes_pov(self, site_name: str) -> SamsungPOV:
        """
        Generate POV when no significant changes detected.

        Args:
            site_name: 'apple' or 'samsung'

        Returns:
            Samsung POV for stable period
        """
        return SamsungPOV(
            observation=f"No significant changes detected on {site_name.capitalize()}.com",
            evidence="Crawl completed with no major content, navigation, or structural changes",
            hypothesis="Site is in a stable state; no active campaign or product launch",
            opportunity="Use this period for deep analysis of existing content and competitive benchmarking",
            recommended_action="Focus on long-term trend analysis and prepare for potential upcoming changes (product launches, campaigns)",
            priority="low",
            functional_area="analytics",
        )

    def get_priority_povs(self, priority: str) -> List[SamsungPOV]:
        """Get POVs filtered by priority"""
        return [p for p in self.povs if p.priority == priority]

    def get_povs_by_area(self, area: str) -> List[SamsungPOV]:
        """Get POVs filtered by functional area"""
        return [p for p in self.povs if p.functional_area == area]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of generated POVs"""
        return {
            "total_povs": len(self.povs),
            "by_priority": {
                "critical": len(self.get_priority_povs("critical")),
                "high": len(self.get_priority_povs("high")),
                "medium": len(self.get_priority_povs("medium")),
                "low": len(self.get_priority_povs("low")),
            },
            "by_functional_area": self._count_by_area(),
        }

    def _count_by_area(self) -> Dict[str, int]:
        """Count POVs by functional area"""
        counts = {}
        for pov in self.povs:
            area = pov.functional_area or "unspecified"
            counts[area] = counts.get(area, 0) + 1
        return counts

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert POVs to list of dictionaries"""
        return [
            {
                "observation": pov.observation,
                "evidence": pov.evidence,
                "hypothesis": pov.hypothesis,
                "opportunity": pov.opportunity,
                "recommended_action": pov.recommended_action,
                "priority": pov.priority,
                "functional_area": pov.functional_area,
                "created_at": pov.created_at.isoformat(),
            }
            for pov in self.povs
        ]

"""
GEO/AEO Signal Engine
Detects and analyzes GEO (Generative Engine Optimization) and AEO (Answer Engine Optimization) signals.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class GEOSignal:
    """Represents a GEO/AEO signal"""
    url: str
    signal_type: str
    evidence: Optional[str] = None
    signal_strength: float = 0.0  # 0.0 - 1.0
    related_content: Optional[Dict[str, Any]] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)


class GEOAEOEngine:
    """
    Detects GEO/AEO signals on pages.
    
    Signal Types:
    - faq_expansion: FAQ content growth
    - faq_schema: FAQ structured data
    - definition_content: Definition-style content
    - comparison_content: Comparison tables/content
    - entity_expansion: Entity/brand mentions
    - structured_data_growth: Schema.org expansion
    - knowledge_organization: Knowledge graph signals
    - ai_discoverability: AI-friendly content structure
    - llm_citation_optimization: LLM-friendly formatting
    - semantic_coverage: Topic coverage breadth
    """

    # Signal type weights for strength calculation
    SIGNAL_WEIGHTS = {
        "faq_expansion": 0.9,
        "faq_schema": 0.95,
        "definition_content": 0.7,
        "comparison_content": 0.85,
        "entity_expansion": 0.6,
        "structured_data_growth": 0.9,
        "knowledge_organization": 0.8,
        "ai_discoverability": 0.75,
        "llm_citation_optimization": 0.8,
        "semantic_coverage": 0.7,
    }

    # Keywords indicating GEO/AEO intent
    DEFINITION_KEYWORDS = [
        "what is", "what are", "how to", "how does", "why is",
        "definition", "meaning", "explained", "guide", "tutorial",
        "introduction to", "overview of", "understanding",
    ]

    COMPARISON_KEYWORDS = [
        "vs", "versus", "compare", "comparison", "difference",
        "better than", "compared to", "alternative",
    ]

    AI_DISCOVERABILITY_PATTERNS = [
        r"<h[23]>.+?</h[23]>.*?<p>.+?</p>",  # Heading followed by paragraph
        r"<dl>.*?<dt>.+?</dt>.*?<dd>.+?</dd>.*?</dl>",  # Definition list
        r"<table>.*?<thead>.*?</thead>.*?<tbody>.*?</tbody>.*?</table>",  # Data table
    ]

    def __init__(self):
        self.signals: List[GEOSignal] = []

    def analyze_page(self, page_data: Dict[str, Any]) -> List[GEOSignal]:
        """
        Analyze a page for GEO/AEO signals.

        Args:
            page_data: Crawled page data with content, FAQs, structured data, etc.

        Returns:
            List of detected GEO signals
        """
        self.signals = []

        url = page_data.get("url", "")

        # 1. FAQ Signals
        self._detect_faq_signals(page_data)

        # 2. Definition Content Signals
        self._detect_definition_signals(page_data)

        # 3. Comparison Content Signals
        self._detect_comparison_signals(page_data)

        # 4. Structured Data Signals
        self._detect_structured_data_signals(page_data)

        # 5. AI Discoverability Signals
        self._detect_ai_discoverability_signals(page_data)

        # 6. Semantic Coverage Signals
        self._detect_semantic_coverage_signals(page_data)

        # 7. LLM Citation Optimization
        self._detect_llm_citation_signals(page_data)

        return self.signals

    def _detect_faq_signals(self, page_data: Dict[str, Any]):
        """Detect FAQ-related GEO signals"""
        url = page_data.get("url", "")
        faqs = page_data.get("faqs", [])
        structured_data = page_data.get("structured_data", [])

        # FAQ Schema detection
        has_faq_schema = False
        for sd in structured_data:
            if isinstance(sd, dict):
                sd_type = sd.get("@type", "")
                if sd_type == "FAQPage" or (isinstance(sd_type, list) and "FAQPage" in sd_type):
                    has_faq_schema = True
                    break

        if has_faq_schema:
            self.signals.append(GEOSignal(
                url=url,
                signal_type="faq_schema",
                evidence="FAQPage structured data detected",
                signal_strength=0.95,
                related_content={"faq_count": len(faqs)},
            ))

        # FAQ Expansion detection
        if len(faqs) >= 3:
            strength = min(0.5 + (len(faqs) * 0.1), 0.9)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="faq_expansion",
                evidence=f"{len(faqs)} FAQ items detected",
                signal_strength=strength,
                related_content={
                    "faq_count": len(faqs),
                    "questions": [f.get("question", "") for f in faqs[:5]],
                },
            ))

    def _detect_definition_signals(self, page_data: Dict[str, Any]):
        """Detect definition-style content signals"""
        url = page_data.get("url", "")
        body_content = page_data.get("body_content", "")
        h2s = page_data.get("h2", [])
        h3s = page_data.get("h3", [])

        if not body_content:
            return

        # Check for definition keywords in headings
        definition_headings = []
        all_headings = h2s + h3s

        for heading in all_headings:
            heading_lower = heading.lower()
            if any(kw in heading_lower for kw in self.DEFINITION_KEYWORDS):
                definition_headings.append(heading)

        if definition_headings:
            strength = min(0.4 + (len(definition_headings) * 0.15), 0.85)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="definition_content",
                evidence=f"Found {len(definition_headings)} definition-style headings",
                signal_strength=strength,
                related_content={"headings": definition_headings[:10]},
            ))

        # Check for definition patterns in content
        definition_patterns = [
            r"is (?:a|an|the) \w+ (?:that|which|who)",
            r"refers to",
            r"defined as",
            r"means (?:that|the)",
        ]

        import re
        content_lower = body_content.lower()[:5000]
        matches = []
        for pattern in definition_patterns:
            found = re.findall(pattern, content_lower, re.IGNORECASE)
            matches.extend(found)

        if len(matches) >= 2:
            self.signals.append(GEOSignal(
                url=url,
                signal_type="definition_content",
                evidence=f"Found {len(matches)} definition patterns in content",
                signal_strength=min(0.3 + (len(matches) * 0.1), 0.7),
                related_content={"patterns": matches[:5]},
            ))

    def _detect_comparison_signals(self, page_data: Dict[str, Any]):
        """Detect comparison content signals"""
        url = page_data.get("url", "")
        body_content = page_data.get("body_content", "")
        h2s = page_data.get("h2", [])
        h3s = page_data.get("h3", [])

        if not body_content:
            return

        # Check for comparison keywords
        comparison_headings = []
        all_headings = h2s + h3s

        for heading in all_headings:
            heading_lower = heading.lower()
            if any(kw in heading_lower for kw in self.COMPARISON_KEYWORDS):
                comparison_headings.append(heading)

        if comparison_headings:
            strength = min(0.5 + (len(comparison_headings) * 0.15), 0.9)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="comparison_content",
                evidence=f"Found {len(comparison_headings)} comparison headings",
                signal_strength=strength,
                related_content={"headings": comparison_headings[:10]},
            ))

        # Check for comparison tables
        if "<table" in body_content.lower() and any(
            kw in body_content.lower() for kw in self.COMPARISON_KEYWORDS
        ):
            self.signals.append(GEOSignal(
                url=url,
                signal_type="comparison_content",
                evidence="Comparison table detected",
                signal_strength=0.85,
            ))

    def _detect_structured_data_signals(self, page_data: Dict[str, Any]):
        """Detect structured data growth signals"""
        url = page_data.get("url", "")
        structured_data = page_data.get("structured_data", [])

        if not structured_data:
            return

        # Count different schema types
        schema_types = set()
        for sd in structured_data:
            if isinstance(sd, dict):
                sd_type = sd.get("@type", "")
                if isinstance(sd_type, str):
                    schema_types.add(sd_type)
                elif isinstance(sd_type, list):
                    schema_types.update(sd_type)

        if len(schema_types) >= 2:
            strength = min(0.5 + (len(schema_types) * 0.1), 0.95)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="structured_data_growth",
                evidence=f"Found {len(schema_types)} different schema types",
                signal_strength=strength,
                related_content={"schema_types": list(schema_types)},
            ))

        # Check for specific GEO-relevant schemas
        geo_schemas = ["FAQPage", "HowTo", "Article", "Product", "Organization", "Person"]
        found_geo_schemas = schema_types.intersection(set(geo_schemas))

        if found_geo_schemas:
            self.signals.append(GEOSignal(
                url=url,
                signal_type="knowledge_organization",
                evidence=f"Found GEO-relevant schemas: {found_geo_schemas}",
                signal_strength=0.8,
                related_content={"geo_schemas": list(found_geo_schemas)},
            ))

    def _detect_ai_discoverability_signals(self, page_data: Dict[str, Any]):
        """Detect AI discoverability signals"""
        url = page_data.get("url", "")
        body_content = page_data.get("body_content", "")
        h2s = page_data.get("h2", [])
        h3s = page_data.get("h3", [])

        if not body_content:
            return

        # Check for well-structured content
        signals_found = []

        # 1. Clear heading hierarchy
        if h2s and len(h2s) >= 2:
            signals_found.append("Clear heading hierarchy")

        # 2. Short paragraphs (AI-friendly)
        paragraphs = [p.strip() for p in body_content.split("\n\n") if p.strip()]
        short_paragraphs = [p for p in paragraphs if len(p.split()) < 100]
        if len(short_paragraphs) / max(len(paragraphs), 1) > 0.7:
            signals_found.append("AI-friendly paragraph length")

        # 3. List usage
        if "<ul" in body_content or "<ol" in body_content:
            signals_found.append("Structured list content")

        # 4. Definition lists
        if "<dl" in body_content:
            signals_found.append("Definition list structure")

        if len(signals_found) >= 2:
            strength = min(0.4 + (len(signals_found) * 0.15), 0.85)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="ai_discoverability",
                evidence="; ".join(signals_found),
                signal_strength=strength,
            ))

    def _detect_semantic_coverage_signals(self, page_data: Dict[str, Any]):
        """Detect semantic coverage signals"""
        url = page_data.get("url", "")
        body_content = page_data.get("body_content", "")
        h2s = page_data.get("h2", [])
        h3s = page_data.get("h3", [])

        if not body_content:
            return

        # Analyze topic coverage
        word_count = len(body_content.split())

        # Comprehensive content (1000+ words)
        if word_count >= 1000:
            strength = min(0.5 + ((word_count - 1000) / 5000), 0.85)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="semantic_coverage",
                evidence=f"Comprehensive content with {word_count} words",
                signal_strength=strength,
            ))

        # Multiple subtopics (many H2/H3)
        total_headings = len(h2s) + len(h3s)
        if total_headings >= 5:
            self.signals.append(GEOSignal(
                url=url,
                signal_type="semantic_coverage",
                evidence=f"Multiple subtopics covered ({total_headings} headings)",
                signal_strength=min(0.4 + (total_headings * 0.05), 0.75),
            ))

    def _detect_llm_citation_signals(self, page_data: Dict[str, Any]):
        """Detect LLM citation optimization signals"""
        url = page_data.get("url", "")
        body_content = page_data.get("body_content", "")
        structured_data = page_data.get("structured_data", [])

        if not body_content:
            return

        signals_found = []

        # 1. Clear source attribution
        if any(kw in body_content.lower() for kw in ["according to", "source:", "reference", "study shows"]):
            signals_found.append("Source attribution")

        # 2. Statistics and data
        import re
        stats_pattern = r"\d+(?:\.\d+)?(?:%|percent|million|billion|times)"
        if re.findall(stats_pattern, body_content, re.IGNORECASE):
            signals_found.append("Statistical data")

        # 3. Quotes
        if body_content.count('"') >= 4:
            signals_found.append("Direct quotes")

        # 4. Author information
        if any(kw in body_content.lower() for kw in ["author", "written by", "by "]):
            signals_found.append("Author attribution")

        # 5. Publication date
        if any(kw in body_content.lower() for kw in ["published", "updated", "last modified"]):
            signals_found.append("Publication date")

        if len(signals_found) >= 2:
            strength = min(0.4 + (len(signals_found) * 0.12), 0.85)
            self.signals.append(GEOSignal(
                url=url,
                signal_type="llm_citation_optimization",
                evidence="; ".join(signals_found),
                signal_strength=strength,
            ))

    def analyze_multiple_pages(self, pages_data: List[Dict[str, Any]]) -> Dict[str, List[GEOSignal]]:
        """
        Analyze multiple pages and aggregate signals.

        Args:
            pages_data: List of page data dictionaries

        Returns:
            Dictionary mapping URLs to their signals
        """
        results = {}
        for page_data in pages_data:
            url = page_data.get("url", "")
            signals = self.analyze_page(page_data)
            if signals:
                results[url] = signals
        return results

    def get_aggregate_signals(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get aggregate GEO/AEO signals across all pages.

        Returns:
            Summary of signals by type
        """
        all_signals = []
        for page_data in pages_data:
            all_signals.extend(self.analyze_page(page_data))

        # Group by signal type
        by_type = {}
        for signal in all_signals:
            if signal.signal_type not in by_type:
                by_type[signal.signal_type] = []
            by_type[signal.signal_type].append(signal)

        # Calculate averages
        summary = {
            "total_signals": len(all_signals),
            "by_type": {},
            "average_strength": 0.0,
            "strongest_signals": [],
        }

        if all_signals:
            summary["average_strength"] = sum(s.signal_strength for s in all_signals) / len(all_signals)

        for signal_type, signals in by_type.items():
            summary["by_type"][signal_type] = {
                "count": len(signals),
                "average_strength": sum(s.signal_strength for s in signals) / len(signals),
                "urls": [s.url for s in signals],
            }

        # Get strongest signals
        sorted_signals = sorted(all_signals, key=lambda s: s.signal_strength, reverse=True)
        summary["strongest_signals"] = [
            {
                "url": s.url,
                "type": s.signal_type,
                "strength": s.signal_strength,
                "evidence": s.evidence,
            }
            for s in sorted_signals[:10]
        ]

        return summary

    def compare_sites(self, apple_signals: Dict, samsung_signals: Dict) -> Dict[str, Any]:
        """
        Compare GEO/AEO signals between Apple and Samsung.

        Args:
            apple_signals: Aggregate signals for Apple
            samsung_signals: Aggregate signals for Samsung

        Returns:
            Comparison analysis
        """
        comparison = {
            "apple_total": apple_signals.get("total_signals", 0),
            "samsung_total": samsung_signals.get("total_signals", 0),
            "apple_avg_strength": apple_signals.get("average_strength", 0),
            "samsung_avg_strength": samsung_signals.get("average_strength", 0),
            "by_type": {},
        }

        all_types = set(apple_signals.get("by_type", {}).keys()) | set(samsung_signals.get("by_type", {}).keys())

        for signal_type in all_types:
            apple_data = apple_signals.get("by_type", {}).get(signal_type, {})
            samsung_data = samsung_signals.get("by_type", {}).get(signal_type, {})

            comparison["by_type"][signal_type] = {
                "apple_count": apple_data.get("count", 0),
                "samsung_count": samsung_data.get("count", 0),
                "apple_strength": apple_data.get("average_strength", 0),
                "samsung_strength": samsung_data.get("average_strength", 0),
            }

        return comparison

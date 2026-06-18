"""
Gemini Integration Engine
Uses Google Gemini 2.5 Flash for AI-powered analysis and insights.
Model: gemini-2.5-flash-preview-05-20
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiEngine:
    """
    AI-powered analysis using Google Gemini 2.5 Flash.
    Provides intelligent insights beyond rule-based analysis.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
        self.model = None
        self.is_configured = False

        if GEMINI_AVAILABLE and self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.is_configured = True
            except Exception as e:
                print(f"Gemini configuration error: {e}")
                self.is_configured = False

    def analyze_changes(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use Gemini to analyze changes and provide strategic insights.

        Args:
            changes: List of change dictionaries

        Returns:
            AI-powered analysis summary
        """
        if not self.is_configured:
            return self._fallback_analysis(changes)

        try:
            # Prepare changes for analysis
            changes_summary = self._format_changes_for_prompt(changes)

            prompt = f"""
Analyze these website changes for Apple.com and provide strategic insights:

{changes_summary}

Provide analysis in JSON format:
{{
    "key_findings": ["top 3-5 findings"],
    "strategic_intent": "What is Apple trying to achieve?",
    "competitive_threats": ["potential threats to Samsung"],
    "recommended_focus_areas": ["where Samsung should focus"],
    "confidence_score": 0.0-1.0
}}
"""

            response = self.model.generate_content(prompt)
            return self._parse_gemini_response(response.text)

        except Exception as e:
            print(f"Gemini analysis error: {e}")
            return self._fallback_analysis(changes)

    def generate_competitive_insights(
        self,
        apple_data: Dict[str, Any],
        samsung_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate competitive insights comparing Apple and Samsung.

        Args:
            apple_data: Apple crawl data summary
            samsung_data: Samsung crawl data summary

        Returns:
            Competitive insights
        """
        if not self.is_configured:
            return self._fallback_competitive_insights(apple_data, samsung_data)

        try:
            prompt = f"""
Compare Apple.com and Samsung.com/sg based on this data:

Apple:
- URLs: {apple_data.get('url_count', 0)}
- FAQs: {apple_data.get('faq_count', 0)}
- Structured Data Types: {apple_data.get('schema_types', [])}
- Key Content Areas: {apple_data.get('content_areas', [])}

Samsung:
- URLs: {samsung_data.get('url_count', 0)}
- FAQs: {samsung_data.get('faq_count', 0)}
- Structured Data Types: {samsung_data.get('schema_types', [])}
- Key Content Areas: {samsung_data.get('content_areas', [])}

Provide competitive analysis in JSON format:
{{
    "apple_advantages": ["where Apple is stronger"],
    "samsung_advantages": ["where Samsung is stronger"],
    "gaps_to_address": ["gaps Samsung should address"],
    "differentiation_opportunities": ["how Samsung can differentiate"],
    "geo_aeo_comparison": {{
        "apple_score": 0-10,
        "samsung_score": 0-10,
        "recommendations": ["GEO/AEO improvements for Samsung"]
    }}
}}
"""

            response = self.model.generate_content(prompt)
            return self._parse_gemini_response(response.text)

        except Exception as e:
            print(f"Gemini competitive insights error: {e}")
            return self._fallback_competitive_insights(apple_data, samsung_data)

    def summarize_page_changes(self, page_url: str, before: Dict, after: Dict) -> str:
        """
        Generate a natural language summary of page changes.

        Args:
            page_url: URL of the changed page
            before: Previous page data
            after: Current page data

        Returns:
            Natural language summary
        """
        if not self.is_configured:
            return self._fallback_page_summary(page_url, before, after)

        try:
            prompt = f"""
Summarize the changes to this page in 2-3 sentences:

URL: {page_url}

Before:
- Title: {before.get('title', 'N/A')}
- H1: {before.get('h1', 'N/A')}
- Key Sections: {before.get('h2', [])[:5]}

After:
- Title: {after.get('title', 'N/A')}
- H1: {after.get('h1', 'N/A')}
- Key Sections: {after.get('h2', [])[:5]}

Provide a concise summary of what changed and why it might matter.
"""

            response = self.model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            print(f"Gemini page summary error: {e}")
            return self._fallback_page_summary(page_url, before, after)

    def extract_actionable_insights(self, pov_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Refine Samsung POV recommendations with AI insights.

        Args:
            pov_data: List of POV dictionaries

        Returns:
            Enhanced POV recommendations
        """
        if not self.is_configured:
            return pov_data

        try:
            pov_text = "\n".join([
                f"- {p.get('observation', '')}"
                for p in pov_data[:10]
            ])

            prompt = f"""
Review these Samsung POV observations and enhance with specific actions:

{pov_text}

For each observation, suggest:
1. A specific, measurable action
2. Expected impact
3. Effort level (low/medium/high)
4. Timeline recommendation

Return as JSON array.
"""

            response = self.model.generate_content(prompt)
            enhanced = self._parse_gemini_response(response.text)
            return enhanced.get("actions", pov_data)

        except Exception as e:
            print(f"Gemini insight enhancement error: {e}")
            return pov_data

    def _format_changes_for_prompt(self, changes: List[Dict]) -> str:
        """Format changes list for Gemini prompt"""
        lines = []
        for change in changes[:20]:  # Limit to 20 changes
            lines.append(f"- {change.get('change_type', 'unknown')}: {change.get('change_category', '')}")
            if change.get('field_name'):
                lines.append(f"  Field: {change.get('field_name')}")
            if change.get('severity'):
                lines.append(f"  Severity: {change.get('severity')}")
        return "\n".join(lines)

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini response as JSON"""
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: return raw text in standard format
        return {
            "raw_analysis": response_text,
            "key_findings": [response_text[:200]],
            "strategic_intent": "Analysis available in raw format",
            "competitive_threats": [],
            "recommended_focus_areas": [],
            "confidence_score": 0.5,
        }

    def _fallback_analysis(self, changes: List[Dict]) -> Dict[str, Any]:
        """Fallback analysis when Gemini is not available"""
        # Count changes by type
        by_type = {}
        by_severity = {}

        for change in changes:
            change_type = change.get("change_type", "unknown")
            severity = change.get("severity", "medium")

            by_type[change_type] = by_type.get(change_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # Generate basic insights
        key_findings = []
        if by_type.get("url", 0) > 5:
            key_findings.append("Significant URL structure changes detected")
        if by_type.get("content", 0) > 10:
            key_findings.append("Major content updates across multiple pages")
        if by_severity.get("critical", 0) > 0:
            key_findings.append("Critical changes requiring immediate attention")

        return {
            "key_findings": key_findings or ["Standard changes detected"],
            "strategic_intent": "Rule-based analysis: Changes appear to be routine updates",
            "competitive_threats": [],
            "recommended_focus_areas": ["Monitor high-severity changes"],
            "confidence_score": 0.6,
            "change_summary": {
                "by_type": by_type,
                "by_severity": by_severity,
            }
        }

    def _fallback_competitive_insights(
        self,
        apple_data: Dict[str, Any],
        samsung_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback competitive insights when Gemini is not available"""
        apple_faqs = apple_data.get("faq_count", 0)
        samsung_faqs = samsung_data.get("faq_count", 0)

        apple_schemas = len(apple_data.get("schema_types", []))
        samsung_schemas = len(samsung_data.get("schema_types", []))

        return {
            "apple_advantages": [
                "Strong brand consistency" if apple_faqs > samsung_faqs else "",
                "More structured data" if apple_schemas > samsung_schemas else "",
            ],
            "samsung_advantages": [
                "More FAQ content" if samsung_faqs > apple_faqs else "",
                "Better schema coverage" if samsung_schemas > apple_schemas else "",
            ],
            "gaps_to_address": [
                "Increase FAQ coverage" if samsung_faqs < apple_faqs else "",
                "Add more structured data types" if samsung_schemas < apple_schemas else "",
            ],
            "differentiation_opportunities": [
                "Focus on Galaxy AI unique features",
                "Emphasize Samsung ecosystem integration",
            ],
            "geo_aeo_comparison": {
                "apple_score": min(10, 5 + (apple_faqs / 10) + (apple_schemas / 5)),
                "samsung_score": min(10, 5 + (samsung_faqs / 10) + (samsung_schemas / 5)),
                "recommendations": [
                    "Add FAQPage schema to product pages",
                    "Increase definition-style content",
                ],
            },
        }

    def _fallback_page_summary(
        self,
        page_url: str,
        before: Dict,
        after: Dict,
    ) -> str:
        """Fallback page summary when Gemini is not available"""
        changes = []

        if before.get("title") != after.get("title"):
            changes.append("title updated")
        if before.get("h1") != after.get("h1"):
            changes.append("main headline changed")

        before_h2 = set(before.get("h2", []))
        after_h2 = set(after.get("h2", []))

        if after_h2 - before_h2:
            changes.append(f"{len(after_h2 - before_h2)} new sections added")
        if before_h2 - after_h2:
            changes.append(f"{len(before_h2 - after_h2)} sections removed")

        if changes:
            return f"Page updates detected: {', '.join(changes)}. Monitor for impact."
        return "Minor or no significant changes detected on this page."

    def is_available(self) -> bool:
        """Check if Gemini is configured and available"""
        return self.is_configured

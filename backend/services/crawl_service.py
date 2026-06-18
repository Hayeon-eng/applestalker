"""
Crawl Service
Orchestrates the complete crawl pipeline:
Fixed 45 URLs → Crawl → Change Detection → GEO Analysis → Samsung POV → Storage

🔒 HALUCINATION PREVENTION:
- Uses hardcoded 45 URLs (no URL discovery)
- All data is extracted from actual HTML content
- No AI-generated content in crawl results
- Gemini AI only used for analysis/insights (not data extraction)
"""

import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import (
    CrawlRun, DiscoveredURL, CrawledPage, DetectedChange,
    GEOSignal, SamsungPOV, TrendData, Screenshot, SiteName
)
from database.database import SessionLocal
from crawler.playwright_crawler import PlaywrightCrawler
from engines.change_detection import ChangeDetectionEngine
from engines.geo_aeo_engine import GEOAEOEngine
from engines.samsung_pov_engine import SamsungPOVEngine
from engines.gemini_engine import GeminiEngine

# Import fixed URLs config
from config.urls import get_apple_urls, get_samsung_urls, get_tier_for_url

from loguru import logger


class CrawlService:
    """
    Main crawl orchestration service.
    Executes the complete crawl pipeline for a site.
    
    🔒 HALUCINATION PREVENTION:
    - Uses fixed 45 URLs (no URL discovery)
    - All content extracted from real HTML
    - No AI in data extraction (only analysis)
    """

    # Site configurations
    SITE_CONFIG = {
        "apple": {
            "urls": get_apple_urls(),
            "name": "apple",
        },
        "samsung": {
            "urls": get_samsung_urls(),
            "name": "samsung",
        },
    }

    def __init__(self):
        self.crawler = PlaywrightCrawler(
            screenshots_dir=os.getenv("SCREENSHOTS_DIR", "./screenshots"),
            snapshots_dir=os.getenv("SNAPSHOTS_DIR", "./snapshots"),
        )
        self.gemini = GeminiEngine()

    async def execute_crawl(self, site_name: str) -> Dict[str, Any]:
        """
        Execute complete crawl pipeline for a site.

        Pipeline:
        1. Fixed URLs (45 hardcoded - no discovery)
        2. Page Crawling
        3. Change Detection
        4. GEO/AEO Analysis
        5. Samsung POV Generation
        6. Historical Storage

        🔒 HALUCINATION PREVENTION:
        - All 45 URLs are hardcoded in config/urls.py
        - No URL discovery or AI-generated URLs
        - All content extracted from actual HTML
        - Gemini AI only used for insights (not data)

        Args:
            site_name: 'apple' or 'samsung'

        Returns:
            Crawl result summary
        """
        config = self.SITE_CONFIG.get(site_name)
        if not config:
            raise ValueError(f"Unknown site: {site_name}")

        urls = config["urls"]
        crawl_run_id = f"{site_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        logger.info(f"Starting crawl for {site_name}.com (Run ID: {crawl_run_id})")
        logger.info(f"Crawling {len(urls)} fixed URLs")

        # Initialize database session
        db = SessionLocal()

        try:
            # Create crawl run record
            crawl_run = CrawlRun(
                crawl_run_id=crawl_run_id,
                site_name=site_name,
                started_at=datetime.utcnow(),
                status="running",
            )
            db.add(crawl_run)
            db.commit()

            # Initialize browser
            await self.crawler.start()

            # Step 1: Prepare fixed URLs (no discovery)
            logger.info("Step 1: Using fixed URLs (no discovery)")
            fixed_urls = []
            for url in urls:
                tier = get_tier_for_url(url)
                fixed_urls.append({
                    "url": url,
                    "tier_level": int(tier.replace("Tier ", "")) if tier.startswith("Tier") else 3,
                })

            # Save URLs to database
            for url_data in fixed_urls:
                db_url = DiscoveredURL(
                    crawl_run_id=crawl_run_id,
                    url=url_data["url"],
                    tier_level=url_data["tier_level"],
                    page_type="fixed",
                    is_new=False,  # Fixed URLs are never "new"
                )
                db.add(db_url)
            db.commit()

            crawl_run.total_urls_discovered = len(fixed_urls)

            # Step 2: Crawl all fixed URLs
            logger.info("Step 2: Page Crawling")
            crawled_pages = await self._crawl_pages(fixed_urls, crawl_run_id)

            # Save crawled pages
            for page_data in crawled_pages:
                db_page = CrawledPage(
                    crawl_run_id=crawl_run_id,
                    url=page_data.get("url", ""),
                    title=page_data.get("title"),
                    meta_description=page_data.get("meta_description"),
                    canonical_url=page_data.get("canonical_url"),
                    h1=page_data.get("h1"),
                    h2=json.dumps(page_data.get("h2", [])),
                    h3=json.dumps(page_data.get("h3", [])),
                    body_content=page_data.get("body_content", "")[:100000],  # Limit size
                    ctas=json.dumps(page_data.get("ctas", [])),
                    faqs=json.dumps(page_data.get("faqs", [])),
                    structured_data=json.dumps(page_data.get("structured_data", [])),
                    navigation=json.dumps(page_data.get("navigation", {})),
                    internal_links=json.dumps(page_data.get("internal_links", [])),
                    images=json.dumps(page_data.get("images", [])),
                    screenshot_path=page_data.get("screenshot_path"),
                    html_snapshot_path=page_data.get("html_snapshot_path"),
                    status_code=page_data.get("status_code", 200),
                    load_time_ms=page_data.get("load_time_ms"),
                    word_count=page_data.get("word_count", 0),
                )
                db.add(db_page)
            db.commit()

            crawl_run.total_urls_crawled = len(crawled_pages)

            # Step 3: Change Detection
            logger.info("Step 3: Change Detection")
            changes = await self._detect_changes(site_name, crawled_pages)

            # Save detected changes
            for change in changes:
                db_change = DetectedChange(
                    crawl_run_id=crawl_run_id,
                    url=change.url,
                    change_type=change.change_type,
                    change_category=change.change_category,
                    field_name=change.field_name,
                    before_value=str(change.before_value)[:1000] if change.before_value else None,
                    after_value=str(change.after_value)[:1000] if change.after_value else None,
                    severity=change.severity,
                    severity_reason=change.severity_reason,
                    tier_level=change.tier_level,
                )
                db.add(db_change)
            db.commit()

            crawl_run.total_changes_detected = len(changes)

            # Step 4: GEO/AEO Analysis
            logger.info("Step 4: GEO/AEO Analysis")
            geo_signals = self._analyze_geo(crawled_pages)

            # Save GEO signals
            for signal in geo_signals:
                db_signal = GEOSignal(
                    url=signal.url,
                    signal_type=signal.signal_type,
                    evidence=signal.evidence,
                    signal_strength=signal.signal_strength,
                )
                db.add(db_signal)
            db.commit()

            # Step 5: Samsung POV Generation
            logger.info("Step 5: Samsung POV Generation")
            povs = self._generate_povs(changes, site_name)

            # Save Samsung POVs
            pov_run_id = f"pov_{crawl_run_id}"
            for pov in povs:
                db_pov = SamsungPOV(
                    pov_run_id=f"{pov_run_id}_{uuid.uuid4().hex[:8]}",
                    related_crawl_run_id=crawl_run_id,
                    observation=pov.observation,
                    evidence=pov.evidence,
                    hypothesis=pov.hypothesis,
                    opportunity=pov.opportunity,
                    recommended_action=pov.recommended_action,
                    priority=pov.priority,
                    functional_area=pov.functional_area,
                )
                db.add(db_pov)
            db.commit()

            # Step 6: Save Trend Data
            logger.info("Step 6: Saving Trend Data")
            self._save_trend_data(site_name, crawled_pages, geo_signals, db)

            # Update crawl run status
            crawl_run.completed_at = datetime.utcnow()
            crawl_run.status = "completed"
            db.commit()

            logger.info(f"Crawl completed for {site_name}.com")

            return {
                "crawl_run_id": crawl_run_id,
                "site_name": site_name,
                "status": "completed",
                "urls_discovered": len(fixed_urls),
                "urls_crawled": len(crawled_pages),
                "changes_detected": len(changes),
                "geo_signals": len(geo_signals),
                "povs_generated": len(povs),
            }

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            crawl_run.status = "failed"
            crawl_run.error_message = str(e)
            db.commit()

            return {
                "crawl_run_id": crawl_run_id,
                "site_name": site_name,
                "status": "failed",
                "error": str(e),
            }

        finally:
            await self.crawler.close()
            db.close()

    async def _discover_urls(self, base_url: str, site_name: str) -> List[DiscoveredURLData]:
        """Discover URLs from site navigation"""
        discovery_engine = URLDiscoveryEngine(base_url, site_name)

        # Get previous URLs for comparison
        db = SessionLocal()
        try:
            # Get previous URLs from the same site via CrawlRun join
            result = db.execute(
                select(DiscoveredURL.url)
                .join(CrawlRun)
                .where(CrawlRun.site_name == site_name)
                .limit(1000)
            )
            previous_urls = set(row[0] for row in result.fetchall())
            discovery_engine.set_previous_urls(previous_urls)
        finally:
            db.close()

        # Discover URLs
        async def get_html(url: str) -> str:
            try:
                result = await self.crawler.quick_crawl(url)
                return result.get("html", "")
            except Exception:
                return ""

        discovered = await discovery_engine.discover_full_site(get_html, base_url)

        # Mark new URLs
        for url_data in discovered:
            if url_data.url not in previous_urls:
                url_data.is_new = True

        return discovered

    async def _crawl_pages(self, urls: List[DiscoveredURLData], crawl_run_id: str) -> List[Dict[str, Any]]:
        """Crawl multiple pages"""
        crawled = []

        for url_data in urls:
            try:
                page_data = await self.crawler.crawl_page(url_data.url)
                if page_data.get("error") is None:
                    crawled.append(page_data)
            except Exception as e:
                logger.warning(f"Failed to crawl {url_data.url}: {e}")

        return crawled

    async def _detect_changes(self, site_name: str, current_pages: List[Dict]) -> List:
        """Detect changes compared to previous crawl"""
        db = SessionLocal()
        try:
            # Get previous crawl data
            result = db.execute(
                select(CrawledPage).where(
                    CrawledPage.crawl_run_id.like(f"{site_name}_%")
                ).order_by(CrawledPage.crawled_at.desc()).limit(100)
            )
            previous_pages_data = result.fetchall()

            previous_pages = {}
            for row in previous_pages_data:
                page = row[0]
                previous_pages[page.url] = {
                    "title": page.title,
                    "h1": page.h1,
                    "h2": json.loads(page.h2) if page.h2 else [],
                    "h3": json.loads(page.h3) if page.h3 else [],
                    "body_content": page.body_content,
                    "ctas": json.loads(page.ctas) if page.ctas else [],
                    "faqs": json.loads(page.faqs) if page.faqs else [],
                    "structured_data": json.loads(page.structured_data) if page.structured_data else [],
                    "navigation": json.loads(page.navigation) if page.navigation else {},
                    "internal_links": json.loads(page.internal_links) if page.internal_links else [],
                }
        finally:
            db.close()

        # Prepare current data
        current_data = {
            "urls": {p.get("url") for p in current_pages},
            "pages": {p.get("url"): p for p in current_pages},
            "navigation": current_pages[0].get("navigation", {}) if current_pages else {},
        }

        previous_data = {
            "urls": set(previous_pages.keys()),
            "pages": previous_pages,
            "navigation": list(previous_pages.values())[0].get("navigation", {}) if previous_pages else {},
        }

        # Detect changes
        detector = ChangeDetectionEngine()
        return detector.detect_all_changes(current_data, previous_data, site_name)

    def _analyze_geo(self, crawled_pages: List[Dict]) -> List:
        """Analyze GEO/AEO signals"""
        geo_engine = GEOAEOEngine()
        signals = []

        for page_data in crawled_pages:
            page_signals = geo_engine.analyze_page(page_data)
            signals.extend(page_signals)

        return signals

    def _generate_povs(self, changes: List, site_name: str) -> List:
        """Generate Samsung POV recommendations"""
        pov_engine = SamsungPOVEngine()

        if not changes:
            return [pov_engine.generate_no_changes_pov(site_name)]

        # Generate POVs
        apple_data = {}
        samsung_data = {}

        if site_name == "apple":
            apple_data = {"changes": changes}
        else:
            samsung_data = {"changes": changes}

        return pov_engine.generate_povs(changes, apple_data, samsung_data)

    def _save_trend_data(self, site_name: str, pages: List[Dict], geo_signals: List, db):
        """Save trend data for historical analysis"""
        now = datetime.utcnow()

        # URL count trend
        db.add(TrendData(
            site_name=site_name,
            metric_type="url_count",
            recorded_at=now,
            value=len(pages),
        ))

        # FAQ count trend
        total_faqs = sum(len(json.loads(p.get("faqs", "[]"))) for p in pages if p.get("faqs"))
        db.add(TrendData(
            site_name=site_name,
            metric_type="faq_count",
            recorded_at=now,
            value=total_faqs,
        ))

        # GEO signal trend
        db.add(TrendData(
            site_name=site_name,
            metric_type="geo_signal_count",
            recorded_at=now,
            value=len(geo_signals),
        ))

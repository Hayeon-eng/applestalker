"""
Crawl Service - Improved
Pipeline: Fixed 45 URLs → Playwright Crawl (JS) → Change Detection → Gemini Analysis → Storage
"""

import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from sqlalchemy import select

from database.models import (
    CrawlRun, DiscoveredURL, CrawledPage, DetectedChange,
    GEOSignal, SamsungPOV, TrendData
)
from database.database import SessionLocal
from crawler.playwright_crawler import PlaywrightCrawler
from engines.change_detection import ChangeDetectionEngine
from engines.geo_aeo_engine import GEOAEOEngine
from engines.samsung_pov_engine import SamsungPOVEngine
from engines.gemini_engine import GeminiEngine
from config.urls import get_apple_urls, get_samsung_urls, get_tier_for_url

from loguru import logger


class CrawlService:
    SITE_CONFIG = {
        "apple":   {"urls": get_apple_urls(),   "name": "apple"},
        "samsung": {"urls": get_samsung_urls(),  "name": "samsung"},
    }

    def __init__(self):
        self.crawler = PlaywrightCrawler(
            screenshots_dir=os.getenv("SCREENSHOTS_DIR", "./screenshots"),
            snapshots_dir=os.getenv("SNAPSHOTS_DIR", "./snapshots"),
        )
        self.gemini = GeminiEngine()

    # ─────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────

    async def execute_crawl(self, site_name: str) -> Dict[str, Any]:
        config = self.SITE_CONFIG.get(site_name)
        if not config:
            raise ValueError(f"Unknown site: {site_name}")

        urls = config["urls"]
        crawl_run_id = f"{site_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting crawl: {site_name} ({len(urls)} URLs) — Run {crawl_run_id}")

        db = SessionLocal()
        try:
            # Create run record
            crawl_run = CrawlRun(
                crawl_run_id=crawl_run_id,
                site_name=site_name,
                started_at=datetime.utcnow(),
                status="running",
            )
            db.add(crawl_run)
            db.commit()

            await self.crawler.start()

            # ── Step 1: Build fixed URL list ──
            fixed_urls = []
            for url in urls:
                tier = get_tier_for_url(url)
                fixed_urls.append({
                    "url": url,
                    "tier_level": int(tier.replace("Tier ", "")) if tier.startswith("Tier") else 3,
                })

            for u in fixed_urls:
                db.add(DiscoveredURL(
                    crawl_run_id=crawl_run_id,
                    url=u["url"],
                    tier_level=u["tier_level"],
                    page_type="fixed",
                    is_new=False,
                ))
            db.commit()
            crawl_run.total_urls_discovered = len(fixed_urls)

            # ── Step 2: Crawl pages (Playwright → JS rendered) ──
            logger.info("Step 2: Crawling pages with Playwright")
            crawled_pages = await self._crawl_pages(fixed_urls)

            for page_data in crawled_pages:
                db.add(CrawledPage(
                    crawl_run_id=crawl_run_id,
                    url=page_data.get("url", ""),
                    title=page_data.get("title"),
                    meta_description=page_data.get("meta_description"),
                    canonical_url=page_data.get("canonical_url"),
                    h1=page_data.get("h1"),
                    h2=json.dumps(page_data.get("h2", []), ensure_ascii=False),
                    h3=json.dumps(page_data.get("h3", []), ensure_ascii=False),
                    body_content=(page_data.get("body_content") or "")[:100000],
                    ctas=json.dumps(page_data.get("ctas", []), ensure_ascii=False),
                    faqs=json.dumps(page_data.get("faqs", []), ensure_ascii=False),
                    structured_data=json.dumps(page_data.get("structured_data", []), ensure_ascii=False),
                    navigation=json.dumps(page_data.get("navigation", {}), ensure_ascii=False),
                    internal_links=json.dumps(page_data.get("internal_links", []), ensure_ascii=False),
                    images=json.dumps(page_data.get("images", []), ensure_ascii=False),
                    screenshot_path=page_data.get("screenshot_path"),
                    status_code=page_data.get("status_code", 200),
                    load_time_ms=page_data.get("load_time_ms"),
                    word_count=page_data.get("word_count", 0),
                ))
            db.commit()
            crawl_run.total_urls_crawled = len(crawled_pages)

            # ── Step 3: Change detection ──
            logger.info("Step 3: Change detection")
            changes = await self._detect_changes(site_name, crawled_pages, db)

            for change in changes:
                db.add(DetectedChange(
                    crawl_run_id=crawl_run_id,
                    url=change.url,
                    change_type=change.change_type,
                    change_category=change.change_category,
                    field_name=change.field_name,
                    before_value=str(change.before_value or "")[:1000],
                    after_value=str(change.after_value or "")[:1000],
                    severity=change.severity,
                    severity_reason=change.severity_reason,
                    tier_level=change.tier_level,
                ))
            db.commit()
            crawl_run.total_changes_detected = len(changes)

            # ── Step 4: GEO/AEO signals ──
            logger.info("Step 4: GEO/AEO analysis")
            # Build url → page_id map (GEOSignal FK is page_id, not crawl_run_id)
            url_to_page_id = {}
            for page_data in crawled_pages:
                row = db.execute(
                    select(CrawledPage.id).where(
                        CrawledPage.crawl_run_id == crawl_run_id,
                        CrawledPage.url == page_data.get("url")
                    )
                ).first()
                if row:
                    url_to_page_id[page_data.get("url")] = row[0]

            geo_engine_inst = GEOAEOEngine()
            geo_signal_count = 0
            for page_data in crawled_pages:
                page_id = url_to_page_id.get(page_data.get("url"))
                if not page_id:
                    continue
                for sig in geo_engine_inst.analyze_page(page_data):
                    db.add(GEOSignal(
                        page_id=page_id,
                        url=sig.url,
                        signal_type=sig.signal_type,
                        evidence=sig.evidence,
                        signal_strength=getattr(sig, "signal_strength", 0.0) or 0.0,
                        related_content=getattr(sig, "related_content", None),
                    ))
                    geo_signal_count += 1
            db.commit()

            # ── Step 5: Samsung POV / Gemini insights ──
            logger.info("Step 5: Gemini insights")

            # Aggregate schema types from ALL pages for platform-wide analysis
            all_schema_types = self._aggregate_schema_types(crawled_pages)

            if changes:
                povs = self._generate_povs(changes, site_name)
            else:
                # No changes → run current-state Gemini analysis instead
                logger.info("No changes detected — running current-state Gemini snapshot analysis")
                snapshot_analysis = self.gemini.analyze_snapshot(crawled_pages, site_name, all_schema_types)
                pov_engine = SamsungPOVEngine()
                povs = [pov_engine.generate_no_changes_pov(site_name)]
                # Store snapshot analysis in the pov observation
                if snapshot_analysis and povs:
                    povs[0].observation = snapshot_analysis.get("summary", povs[0].observation)
                    povs[0].hypothesis = snapshot_analysis.get("samsung_comparison", "")

            for pov in povs:
                db.add(SamsungPOV(
                    related_crawl_run_id=crawl_run_id,
                    site_name=site_name,
                    observation=pov.observation,
                    hypothesis=pov.hypothesis,
                    recommended_action=pov.recommended_action,
                    priority=pov.priority,
                    functional_area=pov.functional_area,
                ))
            db.commit()

            # ── Step 6: Trend data ──
            self._save_trend_data(site_name, crawled_pages, geo_signal_count, all_schema_types, db)

            crawl_run.completed_at = datetime.utcnow()
            crawl_run.status = "completed"
            db.commit()

            logger.info(f"Crawl complete: {site_name} | {len(crawled_pages)} pages | {len(changes)} changes")
            return {
                "crawl_run_id": crawl_run_id,
                "site_name": site_name,
                "status": "completed",
                "urls_crawled": len(crawled_pages),
                "changes_detected": len(changes),
                "schema_types_found": all_schema_types,
                "geo_signals": geo_signal_count,
            }

        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
            crawl_run.status = "failed"
            crawl_run.error_message = str(e)
            db.commit()
            return {"crawl_run_id": crawl_run_id, "status": "failed", "error": str(e)}

        finally:
            await self.crawler.close()
            db.close()

    # ─────────────────────────────────────────────
    # CRAWL PAGES
    # ─────────────────────────────────────────────

    async def _crawl_pages(self, urls: List[Dict]) -> List[Dict[str, Any]]:
        """Crawl pages — handles dict input {url, tier_level}"""
        crawled = []
        for url_data in urls:
            url = url_data["url"] if isinstance(url_data, dict) else url_data.url
            try:
                page_data = await self.crawler.crawl_page(url)
                if not page_data.get("error"):
                    crawled.append(page_data)
                else:
                    logger.warning(f"Crawl error {url}: {page_data['error']}")
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")
        return crawled

    # ─────────────────────────────────────────────
    # CHANGE DETECTION
    # ─────────────────────────────────────────────

    async def _detect_changes(self, site_name: str, current_pages: List[Dict], db) -> List:
        # Get previous crawl pages from DB
        result = db.execute(
            select(CrawledPage)
            .join(CrawlRun, CrawledPage.crawl_run_id == CrawlRun.crawl_run_id)
            .where(CrawlRun.site_name == site_name)
            .where(CrawlRun.status == "completed")
            .order_by(CrawledPage.crawled_at.desc())
            .limit(200)
        )
        previous_rows = result.fetchall()

        previous_pages = {}
        for row in previous_rows:
            page = row[0]
            if page.url not in previous_pages:  # Keep most recent per URL
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
                }

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

        detector = ChangeDetectionEngine()
        return detector.detect_all_changes(current_data, previous_data, site_name)

    # ─────────────────────────────────────────────
    # SCHEMA AGGREGATION (platform-wide)
    # ─────────────────────────────────────────────

    def _aggregate_schema_types(self, crawled_pages: List[Dict]) -> List[str]:
        """Collect all unique JSON-LD @type values across ALL pages"""
        schema_types = set()
        for page in crawled_pages:
            for schema in page.get("structured_data", []):
                if isinstance(schema, dict):
                    t = schema.get("@type")
                    if t:
                        schema_types.add(t if isinstance(t, str) else str(t))
                    # Handle @graph pattern
                    for item in schema.get("@graph", []):
                        if isinstance(item, dict):
                            gt = item.get("@type")
                            if gt:
                                schema_types.add(gt if isinstance(gt, str) else str(gt))
        return sorted(schema_types)

    # ─────────────────────────────────────────────
    # GEO / POV
    # ─────────────────────────────────────────────

    def _analyze_geo(self, crawled_pages: List[Dict]) -> List:
        geo_engine = GEOAEOEngine()
        signals = []
        for page_data in crawled_pages:
            signals.extend(geo_engine.analyze_page(page_data))
        return signals

    def _generate_povs(self, changes: List, site_name: str) -> List:
        pov_engine = SamsungPOVEngine()
        apple_data = {"changes": changes} if site_name == "apple" else {}
        samsung_data = {"changes": changes} if site_name == "samsung" else {}
        return pov_engine.generate_povs(changes, apple_data, samsung_data)

    # ─────────────────────────────────────────────
    # TREND DATA
    # ─────────────────────────────────────────────

    def _save_trend_data(self, site_name: str, pages: List[Dict],
                          geo_signal_count: int, schema_types: List[str], db):
        now = datetime.utcnow()
        total_faqs = sum(len(p.get("faqs", [])) for p in pages)
        for metric, val in [
            ("url_count", len(pages)),
            ("faq_count", total_faqs),
            ("geo_signal_count", geo_signal_count),
            ("schema_type_count", len(schema_types)),
        ]:
            db.add(TrendData(site_name=site_name, metric_type=metric, recorded_at=now, value=val))
        db.commit()

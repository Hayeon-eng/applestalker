"""
Crawl Service — Production-hardened
Pipeline: Fixed 45 URLs → Playwright (JS) → Change Detection → Gemini → DB

모든 단계가 try/except로 감싸져 있어서 한 페이지 실패해도 전체 크롤이 멈추지 않음.
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


def _s(val) -> str:
    """None-safe string — prevents .lower() / .strip() on None"""
    return str(val) if val is not None else ""


def _js(val) -> str:
    """Safe JSON dump"""
    try:
        return json.dumps(val, ensure_ascii=False) if val else "[]"
    except Exception:
        return "[]"


class CrawlService:
    SITE_CONFIG = {
        "apple":   get_apple_urls,
        "samsung": get_samsung_urls,
    }

    def __init__(self):
        self.crawler = PlaywrightCrawler(
            screenshots_dir=os.getenv("SCREENSHOTS_DIR", "./screenshots"),
            snapshots_dir=os.getenv("SNAPSHOTS_DIR", "./snapshots"),
        )
        self.gemini = GeminiEngine()

    # ──────────────────────────────────────────
    # MAIN ENTRY POINT
    # ──────────────────────────────────────────

    async def execute_crawl(self, site_name: str) -> Dict[str, Any]:
        url_fn = self.SITE_CONFIG.get(site_name)
        if not url_fn:
            raise ValueError(f"Unknown site: {site_name}")

        urls = url_fn()
        crawl_run_id = (
            f"{site_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            f"_{uuid.uuid4().hex[:8]}"
        )
        logger.info(f"[{crawl_run_id}] Starting crawl: {site_name} ({len(urls)} URLs)")

        db = SessionLocal()
        crawl_run = None

        try:
            # ── Create run record ──
            crawl_run = CrawlRun(
                crawl_run_id=crawl_run_id,
                site_name=site_name,
                started_at=datetime.utcnow(),
                status="running",
            )
            db.add(crawl_run)
            db.commit()

            await self.crawler.start()

            # ── Step 1: Build URL list ──
            fixed_urls = []
            for url in urls:
                try:
                    tier = get_tier_for_url(url)
                    tier_num = int(_s(tier).replace("Tier ", "") or "3")
                except Exception:
                    tier_num = 3
                fixed_urls.append({"url": url, "tier_level": tier_num})
                try:
                    db.add(DiscoveredURL(
                        crawl_run_id=crawl_run_id,
                        url=url,
                        tier_level=tier_num,
                        page_type="fixed",
                        is_new=False,
                    ))
                except Exception as e:
                    logger.warning(f"DiscoveredURL save failed for {url}: {e}")
            try:
                db.commit()
                crawl_run.total_urls_discovered = len(fixed_urls)
                db.commit()
            except Exception:
                db.rollback()

            # ── Step 2: Crawl pages ──
            logger.info(f"[{crawl_run_id}] Step 2: Crawling {len(fixed_urls)} pages")
            crawled_pages = await self._crawl_pages(fixed_urls)
            logger.info(f"[{crawl_run_id}] Crawled {len(crawled_pages)} pages successfully")

            # Build url → page_id map for GEO signals
            url_to_page_id: Dict[str, int] = {}

            for page_data in crawled_pages:
                try:
                    page = CrawledPage(
                        crawl_run_id=crawl_run_id,
                        url=_s(page_data.get("url")),
                        title=_s(page_data.get("title"))[:500] or None,
                        meta_description=_s(page_data.get("meta_description"))[:1000] or None,
                        canonical_url=_s(page_data.get("canonical_url"))[:500] or None,
                        h1=_s(page_data.get("h1"))[:500] or None,
                        h2=_js(page_data.get("h2", [])),
                        h3=_js(page_data.get("h3", [])),
                        body_content=_s(page_data.get("body_content"))[:100000] or None,
                        ctas=_js(page_data.get("ctas", [])),
                        faqs=_js(page_data.get("faqs", [])),
                        structured_data=_js(page_data.get("structured_data", [])),
                        navigation=_js(page_data.get("navigation", {})),
                        internal_links=_js(page_data.get("internal_links", [])),
                        images=_js(page_data.get("images", [])),
                        screenshot_path=_s(page_data.get("screenshot_path")) or None,
                        status_code=int(page_data.get("status_code") or 200),
                        load_time_ms=page_data.get("load_time_ms"),
                        word_count=int(page_data.get("word_count") or 0),
                    )
                    db.add(page)
                    db.flush()  # get page.id before commit
                    url_to_page_id[_s(page_data.get("url"))] = page.id
                except Exception as e:
                    logger.warning(f"Page save failed for {page_data.get('url')}: {e}")
                    db.rollback()

            try:
                db.commit()
                crawl_run.total_urls_crawled = len(crawled_pages)
                db.commit()
            except Exception:
                db.rollback()

            # ── Step 3: Change detection ──
            logger.info(f"[{crawl_run_id}] Step 3: Change detection")
            changes = []
            try:
                changes = await self._detect_changes(site_name, crawled_pages, db)
            except Exception as e:
                logger.warning(f"Change detection failed: {e}")

            for change in changes:
                try:
                    db.add(DetectedChange(
                        crawl_run_id=crawl_run_id,
                        url=_s(getattr(change, "url", "")),
                        change_type=_s(getattr(change, "change_type", "content")),
                        change_category=_s(getattr(change, "change_category", "modified")),
                        field_name=_s(getattr(change, "field_name", "")) or None,
                        before_value=_s(getattr(change, "before_value", ""))[:1000] or None,
                        after_value=_s(getattr(change, "after_value", ""))[:1000] or None,
                        severity=_s(getattr(change, "severity", "medium")).lower() or "medium",
                        severity_reason=_s(getattr(change, "severity_reason", "")) or None,
                        tier_level=int(getattr(change, "tier_level", 3) or 3),
                    ))
                except Exception as e:
                    logger.warning(f"Change save failed: {e}")
            try:
                db.commit()
                crawl_run.total_changes_detected = len(changes)
                db.commit()
            except Exception:
                db.rollback()

            # ── Step 4: GEO/AEO signals ──
            logger.info(f"[{crawl_run_id}] Step 4: GEO/AEO signals")
            geo_signal_count = 0
            try:
                geo_engine = GEOAEOEngine()
                for page_data in crawled_pages:
                    page_id = url_to_page_id.get(_s(page_data.get("url")))
                    if not page_id:
                        continue
                    try:
                        sigs = geo_engine.analyze_page(page_data)
                        for sig in (sigs or []):
                            try:
                                db.add(GEOSignal(
                                    page_id=page_id,
                                    url=_s(getattr(sig, "url", "")),
                                    signal_type=_s(getattr(sig, "signal_type", "unknown")),
                                    evidence=_s(getattr(sig, "evidence", "")) or None,
                                    signal_strength=float(getattr(sig, "signal_strength", 0.0) or 0.0),
                                    related_content=getattr(sig, "related_content", None),
                                ))
                                geo_signal_count += 1
                            except Exception as e:
                                logger.warning(f"GEOSignal save failed: {e}")
                    except Exception as e:
                        logger.warning(f"GEO analysis failed for {page_data.get('url')}: {e}")
                db.commit()
            except Exception as e:
                logger.warning(f"GEO step failed: {e}")
                db.rollback()

            # ── Step 5: Schema aggregation (platform-wide) ──
            logger.info(f"[{crawl_run_id}] Step 5: Schema aggregation")
            all_schema_types = self._aggregate_schema_types(crawled_pages)
            logger.info(f"[{crawl_run_id}] Schema types found: {all_schema_types}")

            # ── Step 6: Gemini / POV analysis ──
            logger.info(f"[{crawl_run_id}] Step 6: Gemini analysis")
            povs = []
            snapshot_analysis = {}

            try:
                pov_engine = SamsungPOVEngine()
                if changes:
                    apple_d = {"changes": changes} if site_name == "apple" else {}
                    samsung_d = {"changes": changes} if site_name == "samsung" else {}
                    povs = pov_engine.generate_povs(changes, apple_d, samsung_d) or []
                else:
                    # No changes → snapshot analysis
                    no_change_pov = pov_engine.generate_no_changes_pov(site_name)
                    if no_change_pov:
                        povs = [no_change_pov]
                    try:
                        pages_summary = self._build_pages_summary(crawled_pages)
                        snapshot_analysis = self.gemini.analyze_snapshot(
                            pages_summary, site_name, all_schema_types
                        ) or {}
                        if snapshot_analysis and no_change_pov:
                            no_change_pov.observation = (
                                snapshot_analysis.get("summary") or no_change_pov.observation
                            )
                            no_change_pov.hypothesis = (
                                snapshot_analysis.get("samsung_comparison") or no_change_pov.hypothesis
                            )
                    except Exception as e:
                        logger.warning(f"Gemini snapshot failed: {e}")
            except Exception as e:
                logger.warning(f"POV generation failed: {e}")

            for i, pov in enumerate(povs or []):
                try:
                    db.add(SamsungPOV(
                        pov_run_id=f"pov_{crawl_run_id}_{i}",
                        related_crawl_run_id=crawl_run_id,
                        observation=_s(getattr(pov, "observation", ""))[:2000] or "분석 완료",
                        evidence=_s(getattr(pov, "evidence", ""))[:2000] or None,
                        hypothesis=_s(getattr(pov, "hypothesis", ""))[:2000] or None,
                        opportunity=_s(getattr(pov, "opportunity", ""))[:1000] or None,
                        recommended_action=_s(getattr(pov, "recommended_action", ""))[:1000] or None,
                        priority=(_s(getattr(pov, "priority", "medium")) or "medium").lower(),
                        functional_area=_s(getattr(pov, "functional_area", ""))[:100] or None,
                    ))
                except Exception as e:
                    logger.warning(f"POV save failed (pov {i}): {e}")
            try:
                db.commit()
            except Exception:
                db.rollback()

            # ── Step 7: Trend data ──
            try:
                self._save_trend_data(site_name, crawled_pages, geo_signal_count, all_schema_types, db)
            except Exception as e:
                logger.warning(f"Trend data save failed: {e}")

            crawl_run.completed_at = datetime.utcnow()
            crawl_run.status = "completed"
            try:
                db.commit()
            except Exception:
                db.rollback()

            logger.info(
                f"[{crawl_run_id}] ✅ Complete: {len(crawled_pages)} pages, "
                f"{len(changes)} changes, {len(all_schema_types)} schema types"
            )
            return {
                "crawl_run_id": crawl_run_id,
                "site_name": site_name,
                "status": "completed",
                "urls_crawled": len(crawled_pages),
                "changes_detected": len(changes),
                "schema_types": all_schema_types,
                "geo_signals": geo_signal_count,
            }

        except Exception as e:
            logger.error(f"[{crawl_run_id}] Crawl failed: {e}", exc_info=True)
            if crawl_run:
                try:
                    crawl_run.status = "failed"
                    crawl_run.error_message = _s(e)[:500]
                    db.commit()
                except Exception:
                    db.rollback()
            return {"crawl_run_id": crawl_run_id, "status": "failed", "error": _s(e)}

        finally:
            try:
                await self.crawler.close()
            except Exception:
                pass
            try:
                db.close()
            except Exception:
                pass

    # ──────────────────────────────────────────
    # CRAWL PAGES
    # ──────────────────────────────────────────

    async def _crawl_pages(self, urls: List[Dict]) -> List[Dict[str, Any]]:
        crawled = []
        for url_entry in urls:
            # Handle both dict {"url": "..."} and object with .url
            if isinstance(url_entry, dict):
                url = url_entry.get("url", "")
            else:
                url = _s(getattr(url_entry, "url", ""))

            if not url:
                continue
            try:
                page_data = await self.crawler.crawl_page(url)
                if page_data and not page_data.get("error"):
                    crawled.append(page_data)
                elif page_data and page_data.get("error"):
                    logger.warning(f"Crawl error {url}: {page_data['error']}")
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")
        return crawled

    # ──────────────────────────────────────────
    # CHANGE DETECTION
    # ──────────────────────────────────────────

    async def _detect_changes(
        self, site_name: str, current_pages: List[Dict], db
    ) -> List:
        try:
            result = db.execute(
                select(CrawledPage)
                .join(CrawlRun, CrawledPage.crawl_run_id == CrawlRun.crawl_run_id)
                .where(CrawlRun.site_name == site_name)
                .where(CrawlRun.status == "completed")
                .order_by(CrawledPage.crawled_at.desc())
                .limit(200)
            )
            rows = result.fetchall()
        except Exception as e:
            logger.warning(f"Previous pages query failed: {e}")
            return []

        previous_pages: Dict[str, Dict] = {}
        for row in rows:
            try:
                p = row[0]
                if p.url and p.url not in previous_pages:
                    previous_pages[p.url] = {
                        "title": _s(p.title),
                        "h1": _s(p.h1),
                        "h2": json.loads(p.h2) if p.h2 else [],
                        "h3": json.loads(p.h3) if p.h3 else [],
                        "body_content": _s(p.body_content),
                        "ctas": json.loads(p.ctas) if p.ctas else [],
                        "faqs": json.loads(p.faqs) if p.faqs else [],
                        "structured_data": json.loads(p.structured_data) if p.structured_data else [],
                        "navigation": json.loads(p.navigation) if p.navigation else {},
                        "canonical_url": _s(p.canonical_url),
                        "meta_description": _s(p.meta_description),
                    }
            except Exception as e:
                logger.warning(f"Previous page parse failed: {e}")

        if not previous_pages:
            logger.info("No previous crawl data — skipping change detection")
            return []

        current_data = {
            "urls": {p.get("url", "") for p in current_pages},
            "pages": {p.get("url", ""): p for p in current_pages},
            "navigation": current_pages[0].get("navigation", {}) if current_pages else {},
        }
        previous_data = {
            "urls": set(previous_pages.keys()),
            "pages": previous_pages,
            "navigation": next(iter(previous_pages.values()), {}).get("navigation", {}),
        }

        try:
            detector = ChangeDetectionEngine()
            return detector.detect_all_changes(current_data, previous_data, site_name) or []
        except Exception as e:
            logger.warning(f"ChangeDetectionEngine failed: {e}")
            return []

    # ──────────────────────────────────────────
    # SCHEMA AGGREGATION
    # ──────────────────────────────────────────

    def _aggregate_schema_types(self, pages: List[Dict]) -> List[str]:
        """Collect all unique @type values across ALL pages (platform-wide view)"""
        types: set = set()
        for page in pages:
            try:
                for schema in page.get("structured_data") or []:
                    if not isinstance(schema, dict):
                        continue
                    t = schema.get("@type")
                    if t:
                        types.add(_s(t))
                    # Handle @graph pattern (common in Samsung/Apple)
                    for item in schema.get("@graph") or []:
                        if isinstance(item, dict):
                            gt = item.get("@type")
                            if gt:
                                types.add(_s(gt))
            except Exception:
                pass
        return sorted(types)

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _build_pages_summary(self, pages: List[Dict]) -> List[Dict]:
        """Compact page summaries for Gemini prompt"""
        summary = []
        for p in pages[:20]:
            try:
                summary.append({
                    "url": _s(p.get("url")),
                    "title": _s(p.get("title")),
                    "h1": _s(p.get("h1")),
                    "h2": (p.get("h2") or [])[:4],
                    "meta_description": _s(p.get("meta_description")),
                    "faq_count": len(p.get("faqs") or []),
                    "cta_count": len(p.get("ctas") or []),
                    "schema_types": [
                        _s(s.get("@type")) for s in (p.get("structured_data") or [])
                        if isinstance(s, dict) and s.get("@type")
                    ],
                    "word_count": int(p.get("word_count") or 0),
                })
            except Exception:
                pass
        return summary

    def _save_trend_data(
        self,
        site_name: str,
        pages: List[Dict],
        geo_count: int,
        schema_types: List[str],
        db,
    ):
        now = datetime.utcnow()
        faq_total = sum(len(p.get("faqs") or []) for p in pages)
        for metric, val in [
            ("url_count", len(pages)),
            ("faq_count", faq_total),
            ("geo_signal_count", geo_count),
            ("schema_type_count", len(schema_types)),
        ]:
            try:
                db.add(TrendData(
                    site_name=site_name,
                    metric_type=metric,
                    recorded_at=now,
                    value=val,
                ))
            except Exception as e:
                logger.warning(f"TrendData save failed ({metric}): {e}")
        try:
            db.commit()
        except Exception:
            db.rollback()

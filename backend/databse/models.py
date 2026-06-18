"""
PostgreSQL Database Models for Apple Tracker
Historical Intelligence Database - Append Only
Designed for Render PostgreSQL (Free 10GB)
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float, Enum
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class SiteName(str, enum.Enum):
    APPLE = "apple"
    SAMSUNG = "samsung"


class SeverityLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TierLevel(int, enum.Enum):
    TIER_0 = 0  # Homepage
    TIER_1 = 1  # Global Navigation
    TIER_2 = 2  # Sub Navigation
    TIER_3 = 3  # Product/Solution Pages
    TIER_4 = 4  # Commerce Pages
    TIER_5 = 5  # Support Pages
    TIER_6 = 6  # Internal Linked Pages


class CrawlRun(Base):
    """
    Each crawl run creates an independent historical record.
    Append Only - Never Update, Overwrite, or Delete.
    """
    __tablename__ = "crawl_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), unique=True, nullable=False, index=True)
    site_name = Column(String(50), nullable=False)  # apple, samsung
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")  # running, completed, failed
    total_urls_discovered = Column(Integer, default=0)
    total_urls_crawled = Column(Integer, default=0)
    total_changes_detected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Relationships
    urls = relationship("DiscoveredURL", back_populates="crawl_run", cascade="all, delete-orphan")
    pages = relationship("CrawledPage", back_populates="crawl_run", cascade="all, delete-orphan")
    changes = relationship("DetectedChange", back_populates="crawl_run", cascade="all, delete-orphan")


class DiscoveredURL(Base):
    """
    URLs discovered during URL Discovery Engine phase.
    Tracks new URLs, removed URLs, redirects, navigation changes.
    """
    __tablename__ = "discovered_urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), ForeignKey("crawl_runs.crawl_run_id"), nullable=False)
    url = Column(String(2048), nullable=False, index=True)
    tier_level = Column(Integer, default=3)  # Tier 0-6
    page_type = Column(String(50), nullable=True)  # product, commerce, support, etc.
    discovered_at = Column(DateTime, default=datetime.utcnow)
    is_new = Column(Boolean, default=False)  # Newly discovered URL
    is_removed = Column(Boolean, default=False)  # URL no longer found
    redirect_url = Column(String(2048), nullable=True)  # If redirected

    # Relationships
    crawl_run = relationship("CrawlRun", back_populates="urls")


class CrawledPage(Base):
    """
    Complete page data collected during crawling.
    All fields are stored for historical comparison.
    """
    __tablename__ = "crawled_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), ForeignKey("crawl_runs.crawl_run_id"), nullable=False)
    url = Column(String(2048), nullable=False, index=True)
    crawled_at = Column(DateTime, default=datetime.utcnow)

    # Page Content
    title = Column(String(1000), nullable=True)
    meta_description = Column(Text, nullable=True)
    canonical_url = Column(String(2048), nullable=True)
    h1 = Column(Text, nullable=True)
    h2 = Column(JSON, nullable=True)  # Array of H2 headings
    h3 = Column(JSON, nullable=True)  # Array of H3 headings
    body_content = Column(Text, nullable=True)

    # Commerce & CTA
    ctas = Column(JSON, nullable=True)  # Array of CTA buttons {text, href}

    # FAQ & Support
    faqs = Column(JSON, nullable=True)  # Array of FAQ items {question, answer}

    # Technical SEO
    structured_data = Column(JSON, nullable=True)  # JSON-LD structured data
    navigation = Column(JSON, nullable=True)  # Navigation structure
    internal_links = Column(JSON, nullable=True)  # Array of internal links
    images = Column(JSON, nullable=True)  # Array of image info {src, alt}
    videos = Column(JSON, nullable=True)  # Array of video info

    # Snapshots
    screenshot_path = Column(String(500), nullable=True)
    html_snapshot_path = Column(String(500), nullable=True)

    # Metadata
    status_code = Column(Integer, default=200)
    load_time_ms = Column(Integer, nullable=True)
    word_count = Column(Integer, default=0)

    # Relationships
    crawl_run = relationship("CrawlRun", back_populates="pages")
    changes = relationship("DetectedChange", back_populates="page", cascade="all, delete-orphan")
    geo_signals = relationship("GEOSignal", back_populates="page", cascade="all, delete-orphan")


class DetectedChange(Base):
    """
    Changes detected between crawl runs.
    Includes navigation, content, commerce, technical changes.
    """
    __tablename__ = "detected_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), ForeignKey("crawl_runs.crawl_run_id"), nullable=False)
    page_id = Column(Integer, ForeignKey("crawled_pages.id"), nullable=True)
    url = Column(String(2048), nullable=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow)

    # Change Type
    change_type = Column(String(50), nullable=False)  # navigation, content, commerce, technical, url
    change_category = Column(String(50), nullable=True)  # added, removed, reordered, modified

    # Change Details
    field_name = Column(String(100), nullable=True)  # Specific field that changed
    before_value = Column(Text, nullable=True)  # Previous value (truncated)
    after_value = Column(Text, nullable=True)  # New value (truncated)

    # Severity
    severity = Column(String(20), default="medium")  # critical, high, medium, low
    severity_reason = Column(Text, nullable=True)

    # Tier Level Impact
    tier_level = Column(Integer, default=3)

    # Relationships
    crawl_run = relationship("CrawlRun", back_populates="changes")
    page = relationship("CrawledPage", back_populates="changes")


class GEOSignal(Base):
    """
    GEO/AEO signals detected on pages.
    FAQ Expansion, Schema, LLM Discoverability signals.
    """
    __tablename__ = "geo_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(Integer, ForeignKey("crawled_pages.id"), nullable=False)
    url = Column(String(2048), nullable=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow)

    # Signal Type
    signal_type = Column(String(50), nullable=False)
    # faq_expansion, faq_schema, definition_content, comparison_content,
    # entity_expansion, structured_data_growth, knowledge_organization,
    # ai_discoverability, llm_citation_optimization, semantic_coverage

    # Signal Details
    evidence = Column(Text, nullable=True)  # Actual content evidence
    signal_strength = Column(Float, default=0.0)  # 0.0 - 1.0
    related_content = Column(JSON, nullable=True)  # Related content snippets

    # Relationships
    page = relationship("CrawledPage", back_populates="geo_signals")


class CompetitiveAnalysis(Base):
    """
    Competitive analysis comparing Apple vs Samsung.
    Strategic change pattern analysis.
    """
    __tablename__ = "competitive_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Analysis Areas
    apple_intelligence_analysis = Column(JSON, nullable=True)
    galaxy_ai_analysis = Column(JSON, nullable=True)
    faq_comparison = Column(JSON, nullable=True)
    schema_comparison = Column(JSON, nullable=True)
    compare_feature_comparison = Column(JSON, nullable=True)
    commerce_comparison = Column(JSON, nullable=True)
    navigation_comparison = Column(JSON, nullable=True)

    # Overall Insights
    key_findings = Column(JSON, nullable=True)
    strategic_shifts = Column(JSON, nullable=True)


class SamsungPOV(Base):
    """
    Samsung Point of View - Actionable recommendations.
    Observation → Evidence → Hypothesis → Opportunity → Action
    """
    __tablename__ = "samsung_povs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pov_run_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    related_crawl_run_id = Column(String(100), nullable=True)

    # POV Components
    observation = Column(Text, nullable=False)  # Actual change observed
    evidence = Column(Text, nullable=True)  # Evidence supporting observation
    hypothesis = Column(Text, nullable=True)  # Possible intent behind change
    opportunity = Column(Text, nullable=True)  # Samsung opportunity area
    recommended_action = Column(Text, nullable=True)  # Actionable recommendation

    # Classification
    priority = Column(String(20), default="medium")  # critical, high, medium, low
    functional_area = Column(String(50), nullable=True)
    # content, seo, geo, ux, commerce, schema, analytics

    # Status
    is_validated = Column(Boolean, default=False)


class TrendData(Base):
    """
    Historical trend data for analysis.
    Aggregated metrics over time.
    """
    __tablename__ = "trend_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_name = Column(String(50), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False, index=True)
    # faq_count, schema_count, url_count, ai_content_count, etc.
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    value = Column(Float, nullable=False)
    metric_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved word)


class Screenshot(Base):
    """
    Screenshot metadata and storage info.
    Desktop, Mobile, Full Page screenshots.
    """
    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), ForeignKey("crawl_runs.crawl_run_id"), nullable=False)
    page_id = Column(Integer, ForeignKey("crawled_pages.id"), nullable=True)
    url = Column(String(2048), nullable=False)
    screenshot_type = Column(String(20), nullable=False)  # desktop, mobile, full_page
    file_path = Column(String(500), nullable=False)
    thumbnail_path = Column(String(500), nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)
    viewport_width = Column(Integer, default=1920)
    viewport_height = Column(Integer, default=1080)

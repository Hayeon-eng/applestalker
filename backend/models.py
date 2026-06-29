"""
models.py — DB 테이블 (단순화, crawl_service/main 이 쓰는 컬럼과 1:1)
테이블: crawl_runs, page_snapshots, detected_changes, monitored_urls, povs
"""
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, DateTime, Boolean, Float, Index)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), unique=True, index=True, nullable=False)
    site_name = Column(String(50), index=True)                 # samsung / apple
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")             # running/completed/failed
    total_urls_discovered = Column(Integer, default=0)
    total_urls_crawled = Column(Integer, default=0)
    total_changes_detected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


class PageSnapshot(Base):
    """변화 감지의 '이전 상태'. 원본 이미지 대신 썸네일+phash만 보관(무료 DB 보호)."""
    __tablename__ = "page_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), index=True)
    url = Column(String(2048), index=True)
    site_key = Column(String(50), index=True)
    title = Column(Text); h1 = Column(Text)
    meta_description = Column(Text); canonical_url = Column(Text)
    body_content = Column(Text)
    structural_signature = Column(Text)        # diff_engine.structural_signature(JSON)
    screenshot_phash = Column(String(64))      # 이미지 변화 지문
    screenshot_thumb = Column(Text)            # ~10KB base64 썸네일(비교샷용)
    content_hash = Column(String(64), index=True)
    word_count = Column(Integer, default=0)
    crawled_at = Column(DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (Index("ix_snap_url_time", "url", "crawled_at"),)


class DetectedChange(Base):
    """변화 이벤트. severity_level(L0~L5) 보관, UI는 High/Med/Low로 표시."""
    __tablename__ = "detected_changes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), index=True)
    url = Column(String(2048), index=True)
    site_key = Column(String(50), index=True)
    change_type = Column(String(50))           # content/navigation/commerce/technical/visual
    change_category = Column(String(50))
    field_name = Column(String(100))
    before_value = Column(Text); after_value = Column(Text)
    severity = Column(String(20))              # low/medium/high/critical (호환)
    severity_level = Column(String(4), index=True)  # L0~L5
    severity_reason = Column(Text)
    summary = Column(Text)
    char_added = Column(Integer, default=0); char_removed = Column(Integer, default=0)
    diff_ratio = Column(Float, default=0.0)
    evidence = Column(Text)                    # JSON
    tier_level = Column(Integer, default=3)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)


class MonitoredURL(Base):
    """런타임 추가 가능한 모니터링 URL (시드 외 추가분)."""
    __tablename__ = "monitored_urls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    site_key = Column(String(50), index=True)
    url = Column(String(2048), unique=True)
    tier_level = Column(Integer, default=3)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class POV(Base):
    """근거기반 분석 결과 1행(크롤당). UI 현황/이메일에서 사용."""
    __tablename__ = "povs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pov_run_id = Column(String(100), unique=True)
    related_crawl_run_id = Column(String(100), index=True)
    observation = Column(Text)                 # summary
    hypothesis = Column(Text)                  # aeo implications
    opportunity = Column(Text)                 # insights(JSON)
    recommended_action = Column(Text)          # actions(JSON)
    priority = Column(String(20), default="medium")
    functional_area = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

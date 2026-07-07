"""
models.py — DB 테이블
테이블: crawl_runs, page_snapshots, detected_changes, monitored_urls, povs

[PHASE1 변경]
- PageSnapshot: 분석에 필요한 원본 추출물(JSON-LD, h2/h3, 이미지, FAQ, 내비, CTA)을
  컬럼으로 영구 저장. 기존엔 이 데이터가 크롤 도중 메모리에서만 쓰이고 버려져서,
  크롤 끝난 뒤 "페이지 클릭 → 상세 보기"가 불가능했음.
- POV: DATA/COPY/VISUAL 3개 분석 결과를 분리된 컬럼(JSON)으로 저장.
  기존엔 observation/hypothesis/opportunity 4개 텍스트 필드에 모든 걸 욱여넣어서
  카테고리 구분이 불가능했음.
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
    session_id = Column(String(100), index=True)                # 같은 수집 배치(samsung+apple)를 묶는 키
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")             # running/completed/failed
    total_urls_discovered = Column(Integer, default=0)
    total_urls_crawled = Column(Integer, default=0)
    total_changes_detected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


class PageSnapshot(Base):
    """변화 감지의 '이전 상태' + DATA/COPY/VISUAL 분석의 원본 데이터."""
    __tablename__ = "page_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(String(100), index=True)
    url = Column(String(2048), index=True)
    site_key = Column(String(50), index=True)
    title = Column(Text); h1 = Column(Text)
    meta_description = Column(Text); canonical_url = Column(Text)
    body_content = Column(Text)
    structural_signature = Column(Text)        # diff_engine.structural_signature(JSON, 카운트 요약)
    screenshot_phash = Column(String(64))      # 이미지 변화 지문
    screenshot_thumb = Column(Text)            # ~10KB base64 썸네일(비교샷용)
    content_hash = Column(String(64), index=True)
    word_count = Column(Integer, default=0)
    page_height_px = Column(Integer, nullable=True)   # [S8] Playwright 렌더 페이지의 픽셀 높이 (httpx-only = None)
    rendered_by = Column(String(20))            # [FIX] "httpx" | "playwright" — 스냅샷 간 렌더링 방식이
                                                 # 바뀌면 body_content/DOM이 실제 사이트 변경 없이도
                                                 # 크게 달라 보일 수 있어 원인 추적용으로 저장

    # [PHASE1 신규] DATA/COPY/VISUAL 상세 분석을 위한 원본 보존
    raw_h2 = Column(Text)                       # JSON list[str]
    raw_h3 = Column(Text)                       # JSON list[str]
    raw_structured_data = Column(Text)          # JSON: JSON-LD 전체(원본 노드)
    raw_faqs = Column(Text)                     # JSON: FAQPage 노드 리스트
    raw_images = Column(Text)                   # JSON: [{src,alt}]
    raw_navigation = Column(Text)               # JSON
    raw_ctas = Column(Text)                     # JSON: [{text,href}]

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

    # [PHASE1 신규] 변경사항을 DATA/COPY/VISUAL 3분류 중 하나로 귀속 (요구사항 1.5 — 중복 귀속 금지)
    analysis_bucket = Column(String(10), default="DATA")   # DATA | COPY | VISUAL

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


class QbHistory(Base):
    """큐비(닷컴 QA 검수) 이력. [FIX] 기존엔 dotcom_qa/qb_history/*.json 로컬 파일로 저장했으나,
    Render 무료 플랜은 idle 슬립 후 재시작(또는 재배포) 시 로컬 디스크가 초기화되어
    저장된 검수 이력이 전부 유실됐음 → DB(영구 저장소)로 이전."""
    __tablename__ = "qb_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(30), unique=True, index=True, nullable=False)
    at = Column(String(30))
    product = Column(String(20))
    scope = Column(String(50))
    pages = Column(Integer, default=0)
    fail = Column(Integer, default=0)
    warn = Column(Integer, default=0)
    results = Column(Text)                     # JSON: 검수 결과 배열 전체
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class POV(Base):
    """근거기반 분석 결과 1행(크롤당). UI 현황/이메일에서 사용.

    [PHASE1 변경] DATA/COPY/VISUAL 을 분리된 컬럼으로 저장.
    기존 observation/hypothesis/opportunity/recommended_action 은 이메일 등
    하위호환용으로 유지하되, 신규 UI는 data_analysis/copy_analysis/visual_analysis 를 사용.
    """
    __tablename__ = "povs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pov_run_id = Column(String(100), unique=True)
    related_crawl_run_id = Column(String(100), index=True)
    observation = Column(Text)                 # summary (하위호환)
    hypothesis = Column(Text)                  # aeo implications (하위호환)
    opportunity = Column(Text)                 # insights(JSON, 하위호환)
    recommended_action = Column(Text)          # actions(JSON, 하위호환)
    priority = Column(String(20), default="medium")
    functional_area = Column(String(50))

    # [PHASE1 신규]
    data_analysis = Column(Text)                # JSON: DATA 카테고리 전체 분석
    copy_analysis = Column(Text)                # JSON: COPY 카테고리 전체 분석
    visual_analysis = Column(Text)               # JSON: VISUAL 카테고리 전체 분석

    created_at = Column(DateTime, default=datetime.utcnow)

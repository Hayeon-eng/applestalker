"""
database.py — DB 엔진/세션/초기화 (단순 sync 구조)
- DATABASE_URL 형식이 +asyncpg 든 아니든 자동 정규화 (psycopg2 sync 사용)
- init_db(): 테이블 생성 (models.py 의 Base)
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base


def _normalize(url: str) -> str:
    if not url:
        return url
    # asyncpg/async 표기를 sync(psycopg2)로 통일
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):  # Render 구형 표기 대응
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize(os.getenv("DATABASE_URL", ""))
if not DATABASE_URL:
    # 로컬 개발 fallback: sqlite (Playwright/크롤은 되지만 PG 미설정 경고)
    DATABASE_URL = "sqlite:///./local.db"
    print("[db] DATABASE_URL 미설정 → 로컬 sqlite 사용 (운영은 PostgreSQL 권장)")

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
    pool_pre_ping=True,
    pool_size=5, max_overflow=10,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
sync_engine = engine  # 별칭 (crawl_service 호환)


def init_db():
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[db] initialized:", DATABASE_URL.split("@")[-1])


def ensure_schema():
    """이전 배포로 이미 만들어진 테이블에 누락 컬럼을 보강 (PostgreSQL).
    create_all 은 신규 테이블만 만들고 기존 테이블 컬럼은 안 고치므로 필요."""
    if DATABASE_URL.startswith("sqlite"):
        return  # sqlite 는 매번 새로 만들어 보강 불필요
    stmts = [
        # crawl_runs
        "ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS total_urls_discovered INTEGER DEFAULT 0",
        "ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS session_id VARCHAR(100)",
        "ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS total_urls_crawled INTEGER DEFAULT 0",
        "ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS total_changes_detected INTEGER DEFAULT 0",
        "ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP",
        "ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS error_message TEXT",
        # detected_changes
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS site_key VARCHAR(50)",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS change_category VARCHAR(50)",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS severity_level VARCHAR(4)",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS severity_reason TEXT",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS summary TEXT",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS char_added INTEGER DEFAULT 0",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS char_removed INTEGER DEFAULT 0",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS diff_ratio DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS evidence TEXT",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS tier_level INTEGER DEFAULT 3",
        "ALTER TABLE detected_changes ADD COLUMN IF NOT EXISTS analysis_bucket VARCHAR(10) DEFAULT 'DATA'",
        # page_snapshots
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS structural_signature TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS screenshot_phash VARCHAR(64)",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS screenshot_thumb TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)",
        # [PHASE1 신규] page_snapshots 원본 보존 컬럼
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_h2 TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_h3 TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_structured_data TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_faqs TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_images TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_navigation TEXT",
        "ALTER TABLE page_snapshots ADD COLUMN IF NOT EXISTS raw_ctas TEXT",
        # povs
        "ALTER TABLE povs ADD COLUMN IF NOT EXISTS functional_area VARCHAR(50)",
        # [PHASE1 신규] povs DATA/COPY/VISUAL 분리 컬럼
        "ALTER TABLE povs ADD COLUMN IF NOT EXISTS data_analysis TEXT",
        "ALTER TABLE povs ADD COLUMN IF NOT EXISTS copy_analysis TEXT",
        "ALTER TABLE povs ADD COLUMN IF NOT EXISTS visual_analysis TEXT",
    ]
    with engine.connect() as conn:
        for st in stmts:
            try:
                conn.execute(text(st)); conn.commit()
            except Exception as e:
                conn.rollback()
                print("[db] ensure skip:", e)


def prune_old_snapshots(keep_per_url: int = 5):
    """URL당 최근 keep_per_url개 스냅샷만 유지 (무료 DB 용량 보호)."""
    if DATABASE_URL.startswith("sqlite"):
        return
    sql = text("""
        DELETE FROM page_snapshots WHERE id NOT IN (
          SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY url ORDER BY crawled_at DESC) rn
            FROM page_snapshots) t WHERE t.rn <= :keep)
    """)
    try:
        with engine.connect() as conn:
            conn.execute(sql, {"keep": keep_per_url}); conn.commit()
    except Exception as e:
        print("[db] prune skip:", e)

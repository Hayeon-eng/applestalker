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
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[db] initialized:", DATABASE_URL.split("@")[-1])


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

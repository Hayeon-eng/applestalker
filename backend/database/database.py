"""
Database Configuration and Session Management
PostgreSQL for Render (Free 10GB)
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

# Database URL from environment (PostgreSQL only - Render Free 10GB)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL is required. Set it in Render Environment variables.\n"
        "Format: postgresql+asyncpg://user:password@host:port/dbname"
    )

# Detect if using PostgreSQL
IS_POSTGRESQL = "postgresql+asyncpg" in DATABASE_URL

# For sync operations (initialization)
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "+psycopg2")

# Async engine for runtime operations
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Connection health check
)

# Sync engine for initialization
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync session factory
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


def init_db():
    """
    Initialize database tables.
    Creates all tables defined in models.py.
    """
    try:
        Base.metadata.create_all(bind=sync_engine)
        print("Database initialized successfully.")
        
        # Verify PostgreSQL connection
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL connection verified.")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise


async def get_db():
    """
    Dependency for FastAPI routes.
    Yields async database session.
    """
    async with AsyncSessionLocal() as db:
        yield db


def get_sync_db():
    """
    Get synchronous database session.
    Used for initialization and background tasks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_session() -> AsyncSession:
    """
    Get async database session for dependency injection.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

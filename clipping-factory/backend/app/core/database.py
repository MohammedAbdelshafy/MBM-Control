"""
Async SQLAlchemy engine and session factory.
Import `async_session` for DB access inside async FastAPI endpoints.
Import `sync_session` for Celery workers (sync context).
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


# Async engine for FastAPI
async_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    connect_args={"statement_cache_size": 0, "timeout": settings.database_statement_timeout},
    echo=not settings.is_production,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Sync engine for Celery workers — built lazily so that missing psycopg2
# doesn't crash the entire app on import when only the async path is used.
_sync_engine = None
_SyncSession = None


def _get_sync_engine():
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        # Strip asyncpg driver and normalize SSL param for psycopg2 compatibility
        _sync_url = (
            settings.database_url
            .replace("+asyncpg", "")
            .replace("?ssl=require", "?sslmode=require")
            .replace("&ssl=require", "&sslmode=require")
        )
        _sync_engine = create_engine(
            _sync_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=False,
            future=True,
        )
        _SyncSession = sessionmaker(
            bind=_sync_engine,
            autoflush=False,
            autocommit=False,
        )
    return _sync_engine, _SyncSession


# Keep backwards-compatible attribute — resolves on first access
class _LazySyncEngine:
    def __getattr__(self, name):
        engine, _ = _get_sync_engine()
        return getattr(engine, name)


sync_engine = _LazySyncEngine()  # type: ignore[assignment]


class _LazySyncSession:
    def __call__(self, *args, **kwargs):
        _, Session = _get_sync_engine()
        return Session(*args, **kwargs)

    def __getattr__(self, name):
        _, Session = _get_sync_engine()
        return getattr(Session, name)


SyncSessionLocal = _LazySyncSession()  # type: ignore[assignment]


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def init_db() -> None:
    """Create all tables. Called once at startup."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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


try:
    _async_url = settings.database_url
    if _async_url.startswith("sqlite://"):
        _async_url = _async_url.replace("sqlite://", "sqlite+aiosqlite://")

    _connect_args = {}
    if "postgresql" in settings.database_url:
        _connect_args = {"statement_cache_size": 0, "timeout": settings.database_statement_timeout}

    async_engine = create_async_engine(
        _async_url,
        connect_args=_connect_args,
        echo=not settings.is_production,
        future=True,
    )
except Exception:
    # Safe fallback if async driver is not installed locally
    async_engine = None  # type: ignore

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
        try:
            _sync_engine = create_engine(
                _sync_url,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                echo=False,
                future=True,
            )
        except Exception:
            # Fallback to local SQLite DB when postgres driver or DB is not reachable
            sqlite_url = "sqlite:///./clipping_factory.db"
            _sync_engine = create_engine(
                sqlite_url,
                connect_args={"timeout": 30.0, "check_same_thread": False},
                echo=False,
                future=True,
            )
            from sqlalchemy import event
            @event.listens_for(_sync_engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=30000;")
                cursor.close()

            from app.models import campaign, clip, deliverable, social_post, source_content, transcript, analytics  # noqa: F401
            Base.metadata.create_all(_sync_engine)

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

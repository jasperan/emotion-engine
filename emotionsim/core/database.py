"""Database connection and session management (Oracle DB 26ai Free / SQLite fallback)."""
import json
import logging
import oracledb
from sqlalchemy import TypeDecorator, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from emotionsim.core.config import get_settings

logger = logging.getLogger(__name__)


class OracleJSON(TypeDecorator):
    """JSON type that stores as CLOB text in Oracle (which lacks native JSON column support in SQLAlchemy)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None

# Enable oracledb thin mode (no Oracle Client required)
oracledb.defaults.fetch_lobs = False

settings = get_settings()

# The engine is created lazily: ``resolve_database_url`` runs auto-detection
# (Oracle → SQLite) exactly once, and ``configure_engine`` rebuilds the engine
# if the resolved URL differs from the configured default.
_engine_url: str = settings.database_url
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models"""
    pass


def get_engine_url() -> str:
    """Return the URL the module-level engine is currently bound to."""
    return _engine_url or settings.database_url


def configure_engine(url: str | None = None) -> str:
    """Rebind the module-level engine to *url* (or the auto-detected URL).

    With no argument, auto-detection runs: Oracle when reachable, otherwise
    SQLite. Idempotent — the engine is only rebuilt when the URL actually
    changes. Returns the URL in effect.
    """
    global engine, async_session_maker, _engine_url
    if url is None:
        from emotionsim.core.runtime import detect_database_url

        target = detect_database_url()
    else:
        target = url
    if _engine_url == target:
        return target
    logger.info("Database engine → %s", target)
    engine = create_async_engine(
        target,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    _engine_url = target
    return target


def detect_and_configure() -> str:
    """Run database auto-detection and rebind the engine if needed.

    Called once at application startup (lifespan) and by CLI entry points
    that talk to the database. Returns the URL in effect.
    """
    return configure_engine()


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables in Oracle"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

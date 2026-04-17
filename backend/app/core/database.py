"""Database connection and session management (Oracle DB 26ai Free)."""
import json
import oracledb
from sqlalchemy import TypeDecorator, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


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

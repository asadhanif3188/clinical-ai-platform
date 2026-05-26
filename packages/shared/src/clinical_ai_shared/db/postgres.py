import structlog
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

class Base(DeclarativeBase):
    pass

# Global engine and session factory
_engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        logger.info("creating_postgres_engine", url=settings.database_url)
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        engine = get_engine()
        AsyncSessionLocal = async_sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return AsyncSessionLocal

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator for FastAPI Depends()"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda retry_state: logger.info(
        "retrying_postgres_operation", 
        attempt=retry_state.attempt_number
    ),
)
async def init_db() -> None:
    """Initialize the database by creating all tables."""
    engine = get_engine()
    logger.info("initializing_database_tables")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise

async def close_db() -> None:
    """Close the database engine."""
    global _engine
    if _engine:
        logger.info("closing_postgres_engine")
        await _engine.dispose()
        _engine = None
        logger.info("postgres_engine_closed")

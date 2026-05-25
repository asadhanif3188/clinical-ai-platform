from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from tenacity import retry, stop_after_attempt, wait_exponential
from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

class Base(DeclarativeBase):
    pass

engine = create_async_engine(
    settings.database.url,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def init_db() -> None:
    logger.info("initializing_database")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def close_postgres() -> None:
    logger.info("closing_postgres_engine")
    await engine.dispose()
    logger.info("postgres_engine_closed")

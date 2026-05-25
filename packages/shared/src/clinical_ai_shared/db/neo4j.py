from typing import Any, Optional, AsyncGenerator
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential
from contextlib import asynccontextmanager
from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

_driver: Optional[AsyncDriver] = None

def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        logger.info("initializing_neo4j_driver", uri=settings.neo4j.uri)
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password)
        )
    return _driver

async def close_driver() -> None:
    global _driver
    if _driver:
        logger.info("closing_neo4j_driver")
        await _driver.close()
        _driver = None
        logger.info("neo4j_driver_closed")

@asynccontextmanager
async def neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    driver = get_driver()
    async with driver.session() as session:
        yield session

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def execute_query(cypher: str, params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    logger.info("executing_neo4j_query", cypher=cypher)
    async with neo4j_session() as session:
        result = await session.run(cypher, params or {})
        records = await result.data()
        logger.info("neo4j_query_completed", records_count=len(records))
        return records

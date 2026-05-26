from typing import Optional, Any, List, Dict, AsyncIterator, cast
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from contextlib import asynccontextmanager
from tenacity import retry, stop_after_attempt, wait_exponential

from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

_driver: Optional[AsyncDriver] = None

def get_driver() -> AsyncDriver:
    """Get or create the Neo4j async driver singleton."""
    global _driver
    if _driver is None:
        logger.info("creating_neo4j_driver", uri=settings.neo4j.uri)
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
    return _driver

@asynccontextmanager
async def neo4j_session() -> AsyncIterator[AsyncSession]:
    """Context manager for Neo4j async sessions."""
    driver = get_driver()
    session: AsyncSession = driver.session()
    try:
        yield session
    finally:
        await session.close()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda retry_state: logger.info(
        "retrying_neo4j_operation", 
        attempt=retry_state.attempt_number
    ),
)
async def execute_query(cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Execute a Cypher query and return the results as a list of dictionaries."""
    async with neo4j_session() as session:
        try:
            result = await session.run(cypher, params or {})
            records = await result.data()
            return cast(List[Dict[str, Any]], records)
        except Exception as e:
            logger.error("neo4j_query_failed", cypher=cypher, error=str(e))
            raise

async def close_driver() -> None:
    """Close the Neo4j driver."""
    global _driver
    if _driver:
        logger.info("closing_neo4j_driver")
        await _driver.close()
        _driver = None
        logger.info("neo4j_driver_closed")

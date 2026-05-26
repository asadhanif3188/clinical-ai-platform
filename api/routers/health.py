from typing import Any

from clinical_ai_shared.db.neo4j import execute_query
from clinical_ai_shared.db.postgres import get_session_factory
from clinical_ai_shared.db.redis import get_redis
from fastapi import APIRouter, Response, status
from sqlalchemy import text

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe - always returns 200."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/ready")
async def readiness_check(response: Response) -> dict[str, Any]:
    """Readiness probe - checks all backing services."""
    status_code = status.HTTP_200_OK
    health = {
        "postgres": "healthy",
        "neo4j": "healthy",
        "redis": "healthy",
    }

    # Check Postgres
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        health["postgres"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check Neo4j
    try:
        await execute_query("RETURN 1 AS one")
    except Exception:
        health["neo4j"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check Redis
    try:
        client = get_redis()
        # redis-py's ping() returns an Awaitable[bool] when using async client
        # We ensure it's awaited correctly for mypy
        res = client.ping()
        if hasattr(res, "__await__"):
            await res
    except Exception:
        health["redis"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    response.status_code = status_code
    return {
        "status": "ready" if status_code == status.HTTP_200_OK else "not_ready",
        "services": health,
    }

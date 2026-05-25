import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from clinical_ai_shared.db.postgres import get_async_session
from clinical_ai_shared.db.pgvector import embed_and_store

@pytest.mark.asyncio
async def test_postgres_get_session():
    mock_session = AsyncMock()
    # AsyncSessionLocal is used as a context manager: async with AsyncSessionLocal() as session:
    # So AsyncSessionLocal() returns an object that has __aenter__ returning the session.
    with patch("clinical_ai_shared.db.postgres.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        async for session in get_async_session():
            assert session == mock_session
        
        mock_session.close.assert_called_once()

@pytest.mark.asyncio
async def test_pgvector_embed_and_store():
    with patch("clinical_ai_shared.db.pgvector.embedding_model") as mock_model, \
         patch("clinical_ai_shared.db.pgvector.AsyncSessionLocal") as mock_session_factory:
        
        mock_model.encode.return_value = [0.1, 0.2]
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_execute_result
        
        entry_id = await embed_and_store("test content", {"meta": "data"})
        assert entry_id == "1"
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_neo4j_execute_query():
    from clinical_ai_shared.db.neo4j import execute_query
    with patch("clinical_ai_shared.db.neo4j.AsyncGraphDatabase.driver") as mock_driver_factory:
        mock_driver = MagicMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        
        mock_driver_factory.return_value = mock_driver
        mock_driver.session.return_value.__aenter__.return_value = mock_session
        mock_session.run.return_value = mock_result
        mock_result.data.return_value = [{"name": "test"}]
        
        results = await execute_query("MATCH (n) RETURN n")
        assert results == [{"name": "test"}]
        mock_session.run.assert_called_once()

@pytest.mark.asyncio
async def test_redis_cache_ops():
    from clinical_ai_shared.db.redis import cache_set, cache_get
    with patch("clinical_ai_shared.db.redis.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        
        await cache_set("key", "value", 10)
        mock_client.set.assert_called_with("key", "value", ex=10)
        
        mock_client.get.return_value = "value"
        val = await cache_get("key")
        assert val == "value"

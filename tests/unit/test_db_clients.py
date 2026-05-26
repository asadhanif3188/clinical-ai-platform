import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from clinical_ai_shared.db.neo4j import execute_query
from clinical_ai_shared.db.pgvector import (
    embed_and_store,
    search,
)
from clinical_ai_shared.db.postgres import get_async_session, init_db
from clinical_ai_shared.db.redis import cache_get, cache_set, publish


@pytest.mark.asyncio
async def test_postgres_get_session():
    mock_session = AsyncMock()
    # Mocking the factory
    with patch("clinical_ai_shared.db.postgres.get_session_factory") as mock_factory_getter:
        mock_factory = MagicMock()
        mock_factory_getter.return_value = mock_factory
        mock_factory.return_value.__aenter__.return_value = mock_session

        async for session in get_async_session():
            assert session == mock_session

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_postgres_init_db():
    with patch("clinical_ai_shared.db.postgres.get_engine") as mock_get_engine:
        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine

        await init_db()
        mock_engine.begin.assert_called_once()


@pytest.mark.asyncio
async def test_pgvector_embed_and_store():
    with (
        patch("clinical_ai_shared.db.pgvector.get_embedding_model") as mock_get_model,
        patch("clinical_ai_shared.db.pgvector.get_vector_session_factory") as mock_factory_getter,
    ):
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2])

        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory_getter.return_value = mock_factory
        mock_factory.return_value.__aenter__.return_value = mock_session

        # Mock entry with ID
        mock_id = uuid.uuid4()

        def side_effect(obj):
            obj.id = mock_id

        mock_session.refresh.side_effect = side_effect

        entry_id = await embed_and_store("test content", {"meta": "data"})
        assert entry_id == str(mock_id)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_pgvector_search():
    with (
        patch("clinical_ai_shared.db.pgvector.get_embedding_model") as mock_get_model,
        patch("clinical_ai_shared.db.pgvector.get_vector_session_factory") as mock_factory_getter,
    ):
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2])

        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory_getter.return_value = mock_factory
        mock_factory.return_value.__aenter__.return_value = mock_session

        mock_entry = MagicMock()
        mock_entry.id = uuid.uuid4()
        mock_entry.content = "test content"
        mock_entry.metadata_json = {"meta": "data"}

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_entry, 0.5)]
        mock_session.execute.return_value = mock_result

        results = await search("query")
        assert len(results) == 1
        assert results[0].content == "test content"
        assert results[0].score == 0.5


@pytest.mark.asyncio
async def test_neo4j_execute_query():
    with patch("clinical_ai_shared.db.neo4j.get_driver") as mock_get_driver:
        mock_driver = MagicMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        mock_get_driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session
        mock_session.run.return_value = mock_result
        mock_result.data.return_value = [{"name": "test"}]

        results = await execute_query("MATCH (n) RETURN n")
        assert results == [{"name": "test"}]
        mock_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_redis_cache_ops():
    with patch("clinical_ai_shared.db.redis.get_redis") as mock_get_redis:
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await cache_set("key", "value", 10)
        mock_client.set.assert_called_with("key", "value", ex=10)

        mock_client.get.return_value = "value"
        val = await cache_get("key")
        assert val == "value"


@pytest.mark.asyncio
async def test_redis_publish():
    with patch("clinical_ai_shared.db.redis.get_redis") as mock_get_redis:
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client
        mock_client.publish.return_value = 1

        res = await publish("channel", "message")
        assert res == 1
        mock_client.publish.assert_called_with("channel", "message")

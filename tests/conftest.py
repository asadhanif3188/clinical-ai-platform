from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from clinical_ai_shared.config import Settings
from clinical_ai_shared.db.postgres import Base
from clinical_ai_shared.schemas import MedicationInput
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(scope="session")
def event_loop() -> Generator[Any, None, None]:
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class InMemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        return True

    async def publish(self, channel: str, message: str) -> int:
        return 1

    async def ping(self) -> bool:
        return True


@pytest.fixture(scope="session")
def mock_settings():
    return Settings(
        ANTHROPIC_API_KEY="test-key",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        PGVECTOR_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        REDIS_URL="redis://localhost:6379/0",
        LANGFUSE_PUBLIC_KEY="pk",
        LANGFUSE_SECRET_KEY="sk",
        LANGFUSE_HOST="http://localhost:3000",
        OLLAMA_BASE_URL="http://localhost:11434",
    )


@pytest.fixture
def mock_anthropic(mocker):
    mock = mocker.patch("anthropic.AsyncAnthropic")
    return mock


def build_mock_tool_response(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "tool_use",
                "id": "test-id",
                "name": tool_name,
                "input": tool_input,
            }
        ]
    }


@pytest_asyncio.fixture(scope="session")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def redis_mock() -> InMemoryRedis:
    return InMemoryRedis()


@pytest.fixture
def sample_lab_report_state():
    return {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "document_type": "lab_report",
        "retry_count": 0,
        "messages": [],
    }


@pytest.fixture
def sample_medication_list():
    return [
        MedicationInput(name="Warfarin", dose="5mg", frequency="Once daily"),
        MedicationInput(name="Aspirin", dose="81mg", frequency="Once daily"),
    ]

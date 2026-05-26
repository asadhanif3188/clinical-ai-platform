import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from clinical_ai_shared.db.postgres import Base
from clinical_ai_shared.config import Settings

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
        OLLAMA_BASE_URL="http://localhost:11434"
    )

@pytest.fixture
def mock_anthropic(mocker):
    mock = mocker.patch("anthropic.AsyncAnthropic")
    return mock

def build_mock_tool_response(tool_name: str, tool_input: dict):
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
def redis_mock(mocker):
    return mocker.patch("redis.asyncio.from_url")

@pytest.fixture
def sample_lab_report_state():
    return {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "document_type": "lab_report",
        "retry_count": 0,
        "messages": []
    }

@pytest.fixture
def sample_medication_list():
    return [
        {"name": "Warfarin", "dose": "5mg", "frequency": "Once daily"},
        {"name": "Aspirin", "dose": "81mg", "frequency": "Once daily"}
    ]

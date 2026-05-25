import os
import pytest

# Set dummy environment variables so that clinical_ai_shared.config can be imported
# without failing the module-level singleton initialization.
@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    os.environ["ANTHROPIC_API_KEY"] = "sk-dummy"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://dummy"
    os.environ["PGVECTOR_DATABASE_URL"] = "postgresql+asyncpg://dummy"
    os.environ["NEO4J_URI"] = "bolt://dummy"
    os.environ["NEO4J_USER"] = "dummy"
    os.environ["NEO4J_PASSWORD"] = "dummy"
    os.environ["REDIS_URL"] = "redis://dummy"
    os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-dummy"
    os.environ["LANGFUSE_SECRET_KEY"] = "sk-dummy"
    os.environ["LANGFUSE_HOST"] = "http://dummy"
    os.environ["OLLAMA_BASE_URL"] = "http://dummy"

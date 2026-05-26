import pytest
from clinical_ai_shared.config import Settings, get_settings
from pydantic import ValidationError


@pytest.fixture
def base_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai"
    )
    monkeypatch.setenv(
        "PGVECTOR_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai"
    )
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("PHI_MODEL", "phi3:mini")
    return monkeypatch


def test_settings_missing_required_fields(monkeypatch):
    # Ensure a required env var is missing
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_is_phi_safe_configured(base_env):
    s = Settings()
    assert s.is_phi_safe_configured is True

    base_env.setenv("PHI_MODEL", "")
    s = Settings()
    assert s.is_phi_safe_configured is False

    base_env.setenv("PHI_MODEL", "phi3:mini")
    base_env.setenv("OLLAMA_BASE_URL", "")
    s = Settings()
    assert s.is_phi_safe_configured is False


def test_database_url_validator(base_env):
    base_env.setenv("DATABASE_URL", "postgresql://localhost:5432/db")
    with pytest.raises(
        ValidationError, match=r"DATABASE_URL must start with 'postgresql\+asyncpg://'"
    ):
        Settings()


def test_redis_url_validator(base_env):
    base_env.setenv("REDIS_URL", "http://localhost:6379")
    with pytest.raises(ValidationError, match="REDIS_URL must start with 'redis://'"):
        Settings()


def test_logical_grouping(base_env):
    s = Settings()
    assert s.anthropic.api_key == "sk-ant-test"
    assert s.database.url == "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai"
    assert s.neo4j.uri == "bolt://localhost:7687"
    assert s.redis.url == "redis://localhost:6379/0"
    assert s.langfuse.host == "http://localhost:3000"
    assert s.local_model.phi_model == "phi3:mini"
    assert s.local_model.ollama_base_url == "http://localhost:11434"


def test_get_settings(base_env):
    s = get_settings()
    assert isinstance(s, Settings)

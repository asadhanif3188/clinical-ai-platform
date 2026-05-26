from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dataclasses import dataclass

@dataclass(frozen=True)
class AnthropicSettings:
    api_key: str

@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    pgvector_url: str

@dataclass(frozen=True)
class Neo4jSettings:
    uri: str
    user: str
    password: str

@dataclass(frozen=True)
class RedisSettings:
    url: str

@dataclass(frozen=True)
class LangfuseSettings:
    public_key: str
    secret_key: str
    host: str

@dataclass(frozen=True)
class LocalModelSettings:
    phi_model: str
    ollama_base_url: str

@dataclass(frozen=True)
class NotificationSettings:
    slack_webhook_url: Optional[str]
    notification_email: Optional[str]

class Settings(BaseSettings):
    # System
    debug: bool = Field(alias="DEBUG", default=False)
    log_level: str = Field(alias="LOG_LEVEL", default="INFO")

    # LLM
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")

    # Database
    database_url: str = Field(alias="DATABASE_URL")
    pgvector_database_url: str = Field(alias="PGVECTOR_DATABASE_URL")

    # Neo4j
    neo4j_uri: str = Field(alias="NEO4J_URI")
    neo4j_user: str = Field(alias="NEO4J_USER")
    neo4j_password: str = Field(alias="NEO4J_PASSWORD")

    # Redis
    redis_url: str = Field(alias="REDIS_URL")

    # Observability
    langfuse_public_key: str = Field(alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(alias="LANGFUSE_HOST")

    # Local model (PHI routing)
    phi_model: str = Field(alias="PHI_MODEL", default="phi3:mini")
    ollama_base_url: str = Field(alias="OLLAMA_BASE_URL")

    # Notifications (Optional)
    slack_webhook_url: Optional[str] = Field(alias="SLACK_WEBHOOK_URL", default=None)
    notification_email: Optional[str] = Field(alias="NOTIFICATION_EMAIL", default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def anthropic(self) -> AnthropicSettings:
        return AnthropicSettings(api_key=self.anthropic_api_key)

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(
            url=self.database_url,
            pgvector_url=self.pgvector_database_url
        )

    @property
    def neo4j(self) -> Neo4jSettings:
        return Neo4jSettings(
            uri=self.neo4j_uri,
            user=self.neo4j_user,
            password=self.neo4j_password
        )

    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(url=self.redis_url)

    @property
    def langfuse(self) -> LangfuseSettings:
        return LangfuseSettings(
            public_key=self.langfuse_public_key,
            secret_key=self.langfuse_secret_key,
            host=self.langfuse_host
        )

    @property
    def local_model(self) -> LocalModelSettings:
        return LocalModelSettings(
            phi_model=self.phi_model,
            ollama_base_url=self.ollama_base_url
        )

    @property
    def notifications(self) -> NotificationSettings:
        return NotificationSettings(
            slack_webhook_url=self.slack_webhook_url,
            notification_email=self.notification_email
        )

    @property
    def is_phi_safe_configured(self) -> bool:
        return bool(self.phi_model and self.ollama_base_url)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with 'postgresql+asyncpg://'")
        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must start with 'redis://'")
        return v

def get_settings() -> Settings:
    return Settings()

try:
    settings = get_settings()
except Exception as e:
    print(f"Configuration Error: Could not load settings. Check your .env file. Error: {e}")
    # We allow it to fail here, but the error message is printed.
    # In some test environments, this might be problematic if we don't mock env vars before import.
    # But we will handle that in tests.
    raise

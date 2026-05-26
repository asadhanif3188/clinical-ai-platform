from collections.abc import AsyncGenerator

from clinical_ai_shared.config import Settings
from clinical_ai_shared.config import get_settings as _get_settings
from clinical_ai_shared.db.postgres import get_async_session
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database sessions."""
    async for session in get_async_session():
        yield session


def get_settings() -> Settings:
    """Dependency for application settings."""
    return _get_settings()


class PageParams(BaseModel):
    page: int = Query(1, ge=1)
    page_size: int = Query(20, ge=1, le=100)

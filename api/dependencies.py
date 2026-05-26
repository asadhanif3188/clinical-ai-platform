from typing import AsyncGenerator
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from clinical_ai_shared.config import Settings, get_settings as _get_settings
from clinical_ai_shared.db.postgres import get_async_session

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

from typing import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clinical_ai_shared.config import settings
from clinical_ai_shared.db.postgres import close_db
from clinical_ai_shared.db.neo4j import close_driver
from clinical_ai_shared.db.redis import close_redis
from api.middleware import CorrelationIdMiddleware, RequestLoggingMiddleware
from api.routers import health

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup logic
    # (Tables are handled by Alembic migrations, but we could call init_db() here if needed)
    yield
    # Shutdown logic
    await close_db()
    await close_driver()
    await close_redis()

app = FastAPI(
    title="Clinical AI Platform API",
    description="Agentic AI System for Clinical & Life-Sciences Workflows",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure from settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

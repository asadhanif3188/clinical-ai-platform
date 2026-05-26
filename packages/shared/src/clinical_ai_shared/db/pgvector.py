import uuid
from dataclasses import dataclass
from typing import Any, cast

from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger
from pgvector.sqlalchemy import Vector  # type: ignore
from sentence_transformers import SentenceTransformer
from sqlalchemy import JSON, UUID, Column, String, select, text
from sqlalchemy import delete as sqlalchemy_delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from tenacity import retry, stop_after_attempt, wait_exponential

logger = get_logger(__name__)

# Model for local embeddings
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global embedding_model
    if embedding_model is None:
        logger.info("loading_embedding_model", model=EMBEDDING_MODEL_NAME)
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return embedding_model


@dataclass
class VectorSearchResult:
    entry_id: str
    content: str
    score: float
    metadata: dict[str, Any]


class VectorBase(DeclarativeBase):
    pass


class VectorStoreEntry(VectorBase):
    __tablename__ = "vector_store"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=False, default={})
    embedding = Column(Vector(384))  # all-MiniLM-L6-v2 produces 384-dimensional vectors


_vector_engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_vector_engine() -> AsyncEngine:
    global _vector_engine
    if _vector_engine is None:
        logger.info("creating_pgvector_engine", url=settings.pgvector_database_url)
        _vector_engine = create_async_engine(
            settings.pgvector_database_url,
            pool_pre_ping=True,
            echo=False,
        )
    return _vector_engine


def get_vector_session_factory() -> async_sessionmaker[AsyncSession]:
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        engine = get_vector_engine()
        AsyncSessionLocal = async_sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return AsyncSessionLocal


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda retry_state: logger.info(
        "retrying_pgvector_operation", attempt=retry_state.attempt_number
    ),
)
async def init_vector_db() -> None:
    """Initialize the vector database, enabling pgvector extension."""
    engine = get_vector_engine()
    logger.info("initializing_vector_database")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(VectorBase.metadata.create_all)
    logger.info("vector_database_initialized")


async def embed_and_store(text: str, metadata: dict[str, Any]) -> str:
    """Embed text and store it in the vector database."""
    model = get_embedding_model()
    embedding = model.encode(text).tolist()

    factory = get_vector_session_factory()
    async with factory() as session:
        entry = VectorStoreEntry(content=text, metadata_json=metadata, embedding=embedding)
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        entry_id = str(entry.id)
        logger.info("stored_vector_entry", entry_id=entry_id)
        return entry_id


async def search(
    query_text: str, top_k: int = 5, filter_metadata: dict[str, Any] | None = None
) -> list[VectorSearchResult]:
    """Search for similar content in the vector database."""
    model = get_embedding_model()
    query_embedding = model.encode(query_text).tolist()

    factory = get_vector_session_factory()
    async with factory() as session:
        # L2 distance search
        query = (
            select(
                VectorStoreEntry,
                VectorStoreEntry.embedding.l2_distance(query_embedding).label("distance"),
            )
            .order_by("distance")
            .limit(top_k)
        )

        # Note: metadata filtering could be added here using JSONB operators if needed
        # For now, we'll stick to basic search as requested.

        result = await session.execute(query)
        rows = result.all()

        search_results = [
            VectorSearchResult(
                entry_id=str(row[0].id),
                content=row[0].content,
                score=float(row[1]),  # In L2, lower is better, but this is the "distance"
                metadata=row[0].metadata_json,
            )
            for row in rows
        ]
        return search_results


async def delete(entry_id: str) -> bool:
    """Delete an entry from the vector database."""
    factory = get_vector_session_factory()
    async with factory() as session:
        try:
            stmt = sqlalchemy_delete(VectorStoreEntry).where(
                VectorStoreEntry.id == uuid.UUID(entry_id)
            )
            result = await session.execute(stmt)
            await session.commit()
            success = cast("int", result.rowcount) > 0
            logger.info("deleted_vector_entry", entry_id=entry_id, success=success)
            return success
        except Exception as e:
            logger.error("delete_vector_entry_failed", entry_id=entry_id, error=str(e))
            return False


async def close_vector_db() -> None:
    """Close the vector database engine."""
    global _vector_engine
    if _vector_engine:
        logger.info("closing_pgvector_engine")
        await _vector_engine.dispose()
        _vector_engine = None
        logger.info("pgvector_engine_closed")

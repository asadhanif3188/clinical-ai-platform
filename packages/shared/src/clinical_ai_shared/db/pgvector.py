from typing import Any, Optional
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential
from clinical_ai_shared.db.postgres import AsyncSessionLocal
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

# Use a local model as mandated by D-1 and PRD
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

class VectorSearchResult(BaseModel):
    entry_id: str
    content: str
    score: float
    metadata: dict[str, Any]

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def embed_and_store(content: str, metadata: dict[str, Any]) -> str:
    logger.info("embedding_and_storing_vector", content_length=len(content))
    embedding_raw = embedding_model.encode(content)
    embedding = embedding_raw.tolist() if hasattr(embedding_raw, "tolist") else list(embedding_raw)
    
    async with AsyncSessionLocal() as session:
        query = text("""
            INSERT INTO vector_entries (content, metadata, embedding)
            VALUES (:content, :metadata, :embedding)
            RETURNING id
        """)
        result = await session.execute(
            query,
            {"content": content, "metadata": metadata, "embedding": embedding}
        )
        entry_id = str(result.scalar_one())
        await session.commit()
        logger.info("vector_stored", entry_id=entry_id)
        return entry_id

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def search(
    query_text: str, 
    top_k: int = 5, 
    filter_metadata: Optional[dict[str, Any]] = None
) -> list[VectorSearchResult]:
    logger.info("searching_vectors", query=query_text, top_k=top_k)
    query_embedding_raw = embedding_model.encode(query_text)
    query_embedding = query_embedding_raw.tolist() if hasattr(query_embedding_raw, "tolist") else list(query_embedding_raw)
    
    async with AsyncSessionLocal() as session:
        # Assuming pgvector extension is installed and <=> is cosine distance
        # Metadata filtering would be more complex in real SQL, here simplified
        sql = """
            SELECT id, content, metadata, 1 - (embedding <=> :embedding) as score
            FROM vector_entries
            ORDER BY embedding <=> :embedding
            LIMIT :top_k
        """
        result = await session.execute(
            text(sql),
            {"embedding": query_embedding, "top_k": top_k}
        )
        
        search_results = [
            VectorSearchResult(
                entry_id=str(row[0]),
                content=row[1],
                metadata=row[2],
                score=float(row[3])
            )
            for row in result.all()
        ]
        logger.info("vector_search_completed", results_count=len(search_results))
        return search_results

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def delete(entry_id: str) -> bool:
    logger.info("deleting_vector", entry_id=entry_id)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("DELETE FROM vector_entries WHERE id = :id"),
            {"id": entry_id}
        )
        await session.commit()
        from typing import Any as typing_Any, cast
        rowcount = int(cast(typing_Any, result).rowcount)
        success = rowcount > 0
        logger.info("vector_deletion_completed", entry_id=entry_id, success=success)
        return success

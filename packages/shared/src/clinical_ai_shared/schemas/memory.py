from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clinical_ai_shared.schemas.documents import DocumentType


class EpisodicEntry(BaseModel):
    session_id: UUID
    timestamp: datetime = Field(default_factory=datetime.now)
    agent: str
    action: str
    input_summary: str
    output_summary: str
    outcome: str = Field(..., description="'success', 'failure', or 'human_review'")
    confidence: float | None = Field(None, ge=0.0, le=1.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-05-26T10:00:00Z",
                "agent": "intake_agent",
                "action": "classify",
                "input_summary": "Document upload: report.pdf",
                "output_summary": "Classified as lab_report",
                "outcome": "success",
                "confidence": 0.95,
            }
        }
    )


class LongTermEntry(BaseModel):
    entry_id: UUID
    content: str
    embedding: list[float] = Field(..., description="Vector embedding (pgvector)")
    importance_score: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    source_episodes: list[UUID] = Field(
        default_factory=list, description="IDs of source episodic logs"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entry_id": "550e8400-e29b-41d4-a716-446655440001",
                "content": "Patient has high sensitivity to penicillin",
                "embedding": [0.1, 0.2, 0.3],
                "importance_score": 0.85,
                "created_at": "2026-05-26T10:00:00Z",
                "last_accessed": "2026-05-26T10:00:00Z",
                "access_count": 1,
                "source_episodes": ["550e8400-e29b-41d4-a716-446655440000"],
            }
        }
    )


class ProceduralTemplate(BaseModel):
    template_id: UUID
    document_type: DocumentType
    format_fingerprint: str = Field(..., description="Hash of document structure pattern")
    extraction_hints: dict[str, Any] = Field(
        default_factory=dict, description="Field mapping/hints"
    )
    success_rate: float = Field(0.0, ge=0.0, le=1.0)
    last_updated: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "550e8400-e29b-41d4-a716-446655440002",
                "document_type": "lab_report",
                "format_fingerprint": "a1b2c3d4",
                "extraction_hints": {"glucose": "table_cell_1_2"},
                "success_rate": 0.99,
                "last_updated": "2026-05-26T10:00:00Z",
            }
        }
    )


class ConsolidationStats(BaseModel):
    scanned: int
    deduplicated: int
    reflected: int
    promoted: int
    decayed: int
    run_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scanned": 100,
                "deduplicated": 80,
                "reflected": 10,
                "promoted": 5,
                "decayed": 2,
                "run_at": "2026-05-26T02:00:00Z",
            }
        }
    )


class MemorySearchResult(BaseModel):
    entry_id: UUID
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entry_id": "550e8400-e29b-41d4-a716-446655440001",
                "content": "Penicillin sensitivity noted",
                "score": 0.92,
                "metadata": {"type": "long_term"},
            }
        }
    )

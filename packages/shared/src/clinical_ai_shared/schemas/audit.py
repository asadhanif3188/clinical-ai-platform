from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class AuditLogEntry(BaseModel):
    entry_id: UUID = Field(..., description="Immutable UUID")
    run_id: UUID
    agent: str
    node: str
    input_hash: str = Field(..., description="SHA-256 of input (not stored raw — privacy)")
    output_summary: str
    model_used: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    human_decision: Optional[str] = Field(None, description="If HITL node")
    human_reviewer: Optional[str] = Field(None, description="If HITL node")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entry_id": "550e8400-e29b-41d4-a716-446655440003",
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent": "intake_agent",
                "node": "classify",
                "input_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "output_summary": "Classified as lab_report",
                "model_used": "claude-3-haiku",
                "tokens_used": 500,
                "cost_usd": 0.0005,
                "duration_ms": 800,
                "timestamp": "2026-05-26T10:00:00Z"
            }
        }
    )

class AuditQuery(BaseModel):
    run_id: Optional[UUID] = None
    agent: Optional[str] = None
    node: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent": "intake_agent",
                "page": 1,
                "page_size": 20
            }
        }
    )

class AuditExportRequest(BaseModel):
    run_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    format: str = "csv"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "csv",
                "start_date": "2026-05-01T00:00:00Z"
            }
        }
    )

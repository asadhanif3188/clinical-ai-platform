import uuid
from datetime import datetime, UTC
from typing import Any, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Float,
    ARRAY,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from clinical_ai_shared.db.postgres import Base

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    current_node: Mapped[Optional[str]] = mapped_column(String(255))
    checkpoint: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    audit_logs: Mapped[list["AuditLogEntry"]] = relationship("AuditLogEntry", back_populates="workflow_run")

    __table_args__ = (
        Index("ix_workflow_runs_status", "status"),
        Index("ix_workflow_runs_workflow_name", "workflow_name"),
    )

class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False)
    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    node: Mapped[str] = mapped_column(String(255), nullable=False)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64))
    output_summary: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    human_decision: Mapped[Optional[str]] = mapped_column(String(50))
    human_reviewer: Mapped[Optional[str]] = mapped_column(String(255))

    workflow_run: Mapped["WorkflowRun"] = relationship("WorkflowRun", back_populates="audit_logs")

class LongTermMemoryEntry(Base):
    __tablename__ = "long_term_memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(384))
    importance_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_accessed: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    source_sessions: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))

    __table_args__ = (
        Index(
            "ix_long_term_memory_entries_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

class ProceduralTemplate(Base):
    __tablename__ = "procedural_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    format_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction_hints: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

"""Audit trail writer for ClinFlow AI workflow engine.

Provides:
- AuditTrailWriter: class with write(), query(), export_csv() methods
- write_audit_entry(): standalone convenience coroutine for agent nodes
- hash_input(): SHA-256 helper for privacy-safe input hashing
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import datetime
from typing import Any

from clinical_ai_shared.db.models import AuditLogEntry as AuditLogEntryORM
from clinical_ai_shared.db.postgres import get_session_factory
from clinical_ai_shared.observability.logging import get_logger
from clinical_ai_shared.schemas.audit import AuditLogEntry, AuditQuery
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger(__name__)


class PaginatedResponse(BaseModel):
    """Paginated wrapper for audit log query results."""

    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    pages: int


class AuditTrailWriter:
    """Append-only writer for the audit_log_entries table.

    Only INSERT operations are issued — no UPDATE or DELETE ever.
    If a write fails, CRITICAL is logged and the exception is re-raised
    so the failure is never silently swallowed.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write(self, entry: AuditLogEntry) -> None:
        """INSERT a single audit entry.  Never issues UPDATE or DELETE."""
        try:
            async with self._session_factory() as session:
                db_entry = AuditLogEntryORM(
                    id=entry.entry_id,
                    run_id=entry.run_id,
                    agent=entry.agent,
                    node=entry.node,
                    input_hash=entry.input_hash,
                    output_summary=entry.output_summary,
                    model_used=entry.model_used,
                    tokens_used=entry.tokens_used,
                    cost_usd=entry.cost_usd,
                    duration_ms=entry.duration_ms,
                    timestamp=entry.timestamp,
                    human_decision=entry.human_decision,
                    human_reviewer=entry.human_reviewer,
                )
                session.add(db_entry)
                await session.commit()
        except Exception as exc:
            logger.critical(
                "audit_write_failed",
                entry_id=str(entry.entry_id),
                run_id=str(entry.run_id),
                agent=entry.agent,
                node=entry.node,
                error=str(exc),
            )
            raise

    async def query(
        self,
        run_id: uuid.UUID | None = None,
        agent: str | None = None,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse:
        """Return a paginated list of audit entries matching the supplied filters."""
        async with self._session_factory() as session:
            stmt = select(AuditLogEntryORM)
            if run_id is not None:
                stmt = stmt.where(AuditLogEntryORM.run_id == run_id)
            if agent is not None:
                stmt = stmt.where(AuditLogEntryORM.agent == agent)
            if start_dt is not None:
                stmt = stmt.where(AuditLogEntryORM.timestamp >= start_dt)
            if end_dt is not None:
                stmt = stmt.where(AuditLogEntryORM.timestamp <= end_dt)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total: int = (await session.execute(count_stmt)).scalar_one()

            offset = (page - 1) * page_size
            rows = (
                await session.execute(
                    stmt.order_by(AuditLogEntryORM.timestamp.desc())
                    .offset(offset)
                    .limit(page_size)
                )
            ).scalars().all()

        items = [_orm_to_schema(row) for row in rows]
        pages = max(1, (total + page_size - 1) // page_size)
        return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, pages=pages)

    async def export_csv(self, query_params: AuditQuery) -> io.StringIO:
        """Return all matching entries serialised as CSV in an in-memory buffer."""
        async with self._session_factory() as session:
            stmt = select(AuditLogEntryORM)
            if query_params.run_id is not None:
                stmt = stmt.where(AuditLogEntryORM.run_id == query_params.run_id)
            if query_params.agent is not None:
                stmt = stmt.where(AuditLogEntryORM.agent == query_params.agent)
            if query_params.start_date is not None:
                stmt = stmt.where(AuditLogEntryORM.timestamp >= query_params.start_date)
            if query_params.end_date is not None:
                stmt = stmt.where(AuditLogEntryORM.timestamp <= query_params.end_date)
            stmt = stmt.order_by(AuditLogEntryORM.timestamp.asc())
            rows = (await session.execute(stmt)).scalars().all()

        fieldnames = [
            "entry_id",
            "run_id",
            "agent",
            "node",
            "input_hash",
            "output_summary",
            "model_used",
            "tokens_used",
            "cost_usd",
            "duration_ms",
            "timestamp",
            "human_decision",
            "human_reviewer",
        ]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "entry_id": str(row.id),
                    "run_id": str(row.run_id),
                    "agent": row.agent,
                    "node": row.node,
                    "input_hash": row.input_hash or "",
                    "output_summary": row.output_summary or "",
                    "model_used": row.model_used or "",
                    "tokens_used": row.tokens_used if row.tokens_used is not None else 0,
                    "cost_usd": row.cost_usd if row.cost_usd is not None else 0.0,
                    "duration_ms": row.duration_ms if row.duration_ms is not None else 0,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else "",
                    "human_decision": row.human_decision or "",
                    "human_reviewer": row.human_reviewer or "",
                }
            )
        buffer.seek(0)
        return buffer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hash_input(data: Any) -> str:
    """Return the SHA-256 hex digest of the serialised *data* (privacy-safe)."""
    serialised = str(data).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


def _orm_to_schema(row: AuditLogEntryORM) -> AuditLogEntry:
    return AuditLogEntry(
        entry_id=row.id,
        run_id=row.run_id,
        agent=row.agent,
        node=row.node,
        input_hash=row.input_hash or "",
        output_summary=row.output_summary or "",
        model_used=row.model_used,
        tokens_used=row.tokens_used if row.tokens_used is not None else 0,
        cost_usd=row.cost_usd if row.cost_usd is not None else 0.0,
        duration_ms=row.duration_ms if row.duration_ms is not None else 0,
        timestamp=row.timestamp,
        human_decision=row.human_decision,
        human_reviewer=row.human_reviewer,
    )


# ---------------------------------------------------------------------------
# Module-level singleton (uses the global Postgres session factory)
# ---------------------------------------------------------------------------

_writer: AuditTrailWriter | None = None


def _get_writer() -> AuditTrailWriter:
    global _writer
    if _writer is None:
        _writer = AuditTrailWriter(get_session_factory())
    return _writer


# ---------------------------------------------------------------------------
# Public convenience coroutine — call this from every agent node
# ---------------------------------------------------------------------------


async def write_audit_entry(
    *,
    run_id: uuid.UUID | str,
    agent: str,
    node: str,
    input_hash: str,
    output_summary: str,
    model_used: str | None = None,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    human_decision: str | None = None,
    human_reviewer: str | None = None,
) -> None:
    """Write a single audit entry from an agent node.

    Example::

        await write_audit_entry(
            run_id=state["run_id"],
            agent="intake_agent",
            node="classify",
            input_hash=hash_input(state["document_id"]),
            output_summary=f"Classified as {result.document_type}",
            model_used=result.model_used,
            tokens_used=result.tokens,
            cost_usd=result.cost,
            duration_ms=result.duration_ms,
        )
    """
    entry = AuditLogEntry(
        entry_id=uuid.uuid4(),
        run_id=uuid.UUID(str(run_id)),
        agent=agent,
        node=node,
        input_hash=input_hash,
        output_summary=output_summary,
        model_used=model_used,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        human_decision=human_decision,
        human_reviewer=human_reviewer,
    )
    await _get_writer().write(entry)

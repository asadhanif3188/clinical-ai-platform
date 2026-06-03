"""Audit log endpoints.

Routes:
    GET /api/v1/audit              — paginated query with optional filters
    GET /api/v1/audit/export       — CSV download
    GET /api/v1/audit/{entry_id}   — single entry by ID
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from clinical_ai_clinflow.audit import AuditTrailWriter, PaginatedResponse, _orm_to_schema
from clinical_ai_shared.db.models import AuditLogEntry as AuditLogEntryORM
from clinical_ai_shared.db.postgres import get_session_factory
from clinical_ai_shared.schemas.audit import AuditLogEntry, AuditQuery
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.dependencies import get_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


def get_audit_writer() -> AuditTrailWriter:
    """FastAPI dependency that returns the shared AuditTrailWriter."""
    return AuditTrailWriter(get_session_factory())


# ---------------------------------------------------------------------------
# Routes — /export must be declared BEFORE /{entry_id} to avoid shadowing
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse, status_code=status.HTTP_200_OK)
async def query_audit_log(
    run_id: uuid.UUID | None = Query(None, description="Filter by workflow run ID"),
    agent: str | None = Query(None, description="Filter by agent name"),
    start_dt: datetime | None = Query(None, description="Inclusive lower bound on timestamp"),
    end_dt: datetime | None = Query(None, description="Inclusive upper bound on timestamp"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Entries per page"),
    writer: AuditTrailWriter = Depends(get_audit_writer),  # noqa: B008
) -> PaginatedResponse:
    """Query audit log entries with optional filters (FR-7.3)."""
    return await writer.query(
        run_id=run_id,
        agent=agent,
        start_dt=start_dt,
        end_dt=end_dt,
        page=page,
        page_size=page_size,
    )


@router.get("/export", status_code=status.HTTP_200_OK)
async def export_audit_csv(
    run_id: uuid.UUID | None = Query(None),
    agent: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    writer: AuditTrailWriter = Depends(get_audit_writer),  # noqa: B008
) -> StreamingResponse:
    """Export matching audit entries as a CSV file download (FR-7.4)."""
    params = AuditQuery(
        run_id=run_id,
        agent=agent,
        start_date=start_date,
        end_date=end_date,
    )
    buffer = await writer.export_csv(params)
    csv_content = buffer.read()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


@router.get("/{entry_id}", response_model=AuditLogEntry, status_code=status.HTTP_200_OK)
async def get_audit_entry(
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AuditLogEntry:
    """Fetch a single audit log entry by its ID."""
    result = await session.execute(
        select(AuditLogEntryORM).where(AuditLogEntryORM.id == entry_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit entry {entry_id} not found",
        )
    return _orm_to_schema(row)

"""Approval endpoints for human-in-the-loop workflow gates.

Routes:
    POST /api/v1/approvals/{run_id}/approve
    POST /api/v1/approvals/{run_id}/reject
    GET  /api/v1/approvals/pending
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from clinical_ai_clinflow.engine import HumanDecision
from clinical_ai_shared.db.models import HumanReview
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.dependencies import get_gateway_service, get_session

if TYPE_CHECKING:
    from clinical_ai_clinflow.human_gateway import HumanGatewayService
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ApproveRequest(BaseModel):
    reviewer_id: str
    edits: dict[str, Any] | None = None


class RejectRequest(BaseModel):
    reviewer_id: str
    reason: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/{run_id}/approve", status_code=status.HTTP_200_OK)
async def approve(
    run_id: str,
    body: ApproveRequest,
    gateway: HumanGatewayService = Depends(get_gateway_service),  # noqa: B008
) -> dict[str, str]:
    """Approve a paused workflow at its current human gateway node."""
    decision = HumanDecision(
        decision="approved",
        reviewer_id=body.reviewer_id,
        edits=body.edits or {},
    )
    try:
        await gateway.submit_decision(run_id, decision)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "approved", "run_id": run_id}


@router.post("/{run_id}/reject", status_code=status.HTTP_200_OK)
async def reject(
    run_id: str,
    body: RejectRequest,
    gateway: HumanGatewayService = Depends(get_gateway_service),  # noqa: B008
) -> dict[str, str]:
    """Reject a paused workflow at its current human gateway node."""
    decision = HumanDecision(
        decision="rejected",
        reviewer_id=body.reviewer_id,
        edits={"reason": body.reason},
    )
    try:
        await gateway.submit_decision(run_id, decision)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "rejected", "run_id": run_id}


@router.get("/pending", status_code=status.HTTP_200_OK)
async def list_pending(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[dict[str, Any]]:
    """Return all workflow runs currently awaiting human review."""
    result = await session.execute(select(HumanReview).where(HumanReview.status == "pending"))
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "run_id": str(row.run_id),
            "node_id": row.node_id,
            "workflow_name": row.workflow_name,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]

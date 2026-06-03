"""ClinFlow workflow endpoints.

Routes:
    GET  /api/v1/workflows                    — list all workflow definitions
    GET  /api/v1/workflows/runs               — list active & recent runs (paginated)
    GET  /api/v1/workflows/runs/{run_id}      — single run status + checkpoint summary
    POST /api/v1/workflows/runs/{run_id}/resume — resume a paused HITL workflow
    GET  /api/v1/workflows/{name}             — full definition + JSON schema

NOTE: /runs and /runs/{run_id} are declared BEFORE /{name} so FastAPI matches
the static prefixes before the parameterised catch-all.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import clinical_ai_clinflow
from clinical_ai_clinflow.definitions import WorkflowDefinition
from clinical_ai_clinflow.engine import HumanDecision
from clinical_ai_clinflow.loader import list_workflows, load_workflow
from clinical_ai_shared.db.models import WorkflowRun
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from api.dependencies import PageParams, get_gateway_service, get_session

if TYPE_CHECKING:
    from clinical_ai_clinflow.human_gateway import HumanGatewayService
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])

# Directory that contains the workflow YAML files shipped with the clinflow package.
_WORKFLOWS_DIR: Path = Path(clinical_ai_clinflow.__file__).parent / "workflows"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class WorkflowSummary(BaseModel):
    name: str
    version: str
    description: str | None = None


class WorkflowDefinitionResponse(BaseModel):
    name: str
    version: str
    description: str | None = None
    state_schema: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    json_schema: dict[str, Any]


class RunSummary(BaseModel):
    run_id: str
    workflow_name: str
    status: str
    current_node: str | None
    started_at: datetime
    updated_at: datetime
    elapsed_seconds: float


class PaginatedRuns(BaseModel):
    items: list[RunSummary]
    total: int
    page: int
    page_size: int


class ResumeRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    reviewer_id: str
    edits: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _def_to_response(wd: WorkflowDefinition) -> WorkflowDefinitionResponse:
    return WorkflowDefinitionResponse(
        name=wd.name,
        version=wd.version,
        description=wd.description,
        state_schema=[f.model_dump() for f in wd.state_schema],
        nodes=[n.model_dump() for n in wd.nodes],
        edges=[e.model_dump() for e in wd.edges],
        json_schema=wd.model_json_schema(),
    )


def _run_to_summary(row: WorkflowRun) -> RunSummary:
    now = datetime.now(timezone.utc)
    started = row.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed = (now - started).total_seconds()
    return RunSummary(
        run_id=str(row.id),
        workflow_name=row.workflow_name,
        status=row.status,
        current_node=row.current_node,
        started_at=row.started_at,
        updated_at=row.updated_at,
        elapsed_seconds=round(elapsed, 1),
    )


# ---------------------------------------------------------------------------
# Routes — static paths BEFORE /{name}
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WorkflowSummary], status_code=status.HTTP_200_OK)
async def list_workflow_definitions() -> list[WorkflowSummary]:
    """Return a summary (name, version, description) for every workflow definition."""
    if not _WORKFLOWS_DIR.exists():
        return []
    return [
        WorkflowSummary(name=wd.name, version=wd.version, description=wd.description)
        for wd in list_workflows(_WORKFLOWS_DIR)
    ]


@router.get("/runs", response_model=PaginatedRuns, status_code=status.HTTP_200_OK)
async def list_runs(
    workflow_name: str | None = Query(None, description="Filter by workflow name"),
    run_status: str | None = Query(None, alias="status", description="Filter by status"),
    page_params: PageParams = Depends(),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PaginatedRuns:
    """List active and recent workflow runs with optional filters."""
    stmt = select(WorkflowRun)
    if workflow_name is not None:
        stmt = stmt.where(WorkflowRun.workflow_name == workflow_name)
    if run_status is not None:
        stmt = stmt.where(WorkflowRun.status == run_status)

    from sqlalchemy import func

    total: int = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    offset = (page_params.page - 1) * page_params.page_size
    rows = (
        await session.execute(
            stmt.order_by(WorkflowRun.started_at.desc())
            .offset(offset)
            .limit(page_params.page_size)
        )
    ).scalars().all()

    return PaginatedRuns(
        items=[_run_to_summary(r) for r in rows],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.get("/runs/{run_id}", response_model=RunSummary, status_code=status.HTTP_200_OK)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> RunSummary:
    """Return status, current_node, checkpoint summary, and elapsed time for a run."""
    row = (
        await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run {run_id} not found",
        )
    return _run_to_summary(row)


@router.post("/runs/{run_id}/resume", status_code=status.HTTP_200_OK)
async def resume_run(
    run_id: str,
    body: ResumeRequest,
    gateway: HumanGatewayService = Depends(get_gateway_service),  # noqa: B008
) -> dict[str, str]:
    """Resume a workflow paused at a human gateway node."""
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="decision must be 'approved' or 'rejected'",
        )
    decision = HumanDecision(
        decision=body.decision,
        reviewer_id=body.reviewer_id,
        edits=body.edits or {},
    )
    try:
        await gateway.submit_decision(run_id, decision)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": body.decision, "run_id": run_id}


@router.get("/{name}", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_200_OK)
async def get_workflow_definition(name: str) -> WorkflowDefinitionResponse:
    """Return the full workflow definition and JSON schema for *name*."""
    if not _WORKFLOWS_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{name}' not found",
        )
    # Workflows are stored as {name}.yml (name field inside may differ slightly,
    # so we first try an exact filename match, then scan loaded definitions).
    candidate = _WORKFLOWS_DIR / f"{name}.yml"
    if candidate.exists():
        try:
            wd = load_workflow(candidate)
            return _def_to_response(wd)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse workflow '{name}': {exc}",
            ) from exc

    # Fallback: scan all definitions for a name match.
    for wd in list_workflows(_WORKFLOWS_DIR):
        if wd.name == name:
            return _def_to_response(wd)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Workflow '{name}' not found",
    )

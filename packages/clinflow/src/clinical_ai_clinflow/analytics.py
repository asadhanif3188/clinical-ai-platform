"""Workflow analytics for ClinFlow AI.

Provides:
- WorkflowAnalytics: read-only aggregations over audit_log_entries and workflow_runs.
- get_analytics(): module-level singleton factory.
"""

from __future__ import annotations

import uuid
from typing import Any

from clinical_ai_shared.db.models import AuditLogEntry as AuditLogEntryORM
from clinical_ai_shared.db.models import WorkflowRun
from clinical_ai_shared.db.postgres import get_session_factory
from clinical_ai_shared.observability.logging import get_logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger(__name__)


class WorkflowAnalytics:
    """Read-only aggregations over audit_log_entries and workflow_runs.

    All methods issue only SELECT queries — never INSERT, UPDATE, or DELETE.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_workflow_stats(self, workflow_name: str) -> dict[str, Any]:
        """Return aggregated execution statistics for all runs of *workflow_name*.

        Returns a dict with the following keys:

        - ``workflow_name``: echoed back for convenience.
        - ``total_runs``: total number of workflow runs with this name.
        - ``success_count``: runs whose status is ``"success"``.
        - ``failure_count``: runs whose status is ``"failed"``.
        - ``human_review_count``: runs that contain at least one audit entry
          with a non-null ``human_decision`` (i.e. passed through HITL).
        - ``success_ratio``, ``failure_ratio``, ``human_review_ratio``: counts
          divided by ``total_runs`` (0.0 when there are no runs).
        - ``avg_duration_ms_by_node``: ``{node_name: avg_duration_float}``
          computed across all audit entries for all runs of this workflow.
        - ``slowest_node``: node with the highest average duration (``None``
          if no audit entries exist).
        - ``slowest_node_avg_ms``: the average duration of ``slowest_node``.
        """
        async with self._session_factory() as session:
            # ---- run-level counts grouped by status ----
            run_status_stmt = (
                select(WorkflowRun.status, func.count(WorkflowRun.id).label("cnt"))
                .where(WorkflowRun.workflow_name == workflow_name)
                .group_by(WorkflowRun.status)
            )
            run_status_rows = (await session.execute(run_status_stmt)).all()

            total_runs: int = sum(row.cnt for row in run_status_rows)
            success_count: int = next(
                (row.cnt for row in run_status_rows if row.status == "success"), 0
            )
            failure_count: int = next(
                (row.cnt for row in run_status_rows if row.status == "failed"), 0
            )

            # ---- human-review runs: distinct run_ids with a human_decision ----
            human_review_stmt = (
                select(func.count(func.distinct(AuditLogEntryORM.run_id)))
                .join(WorkflowRun, AuditLogEntryORM.run_id == WorkflowRun.id)
                .where(WorkflowRun.workflow_name == workflow_name)
                .where(AuditLogEntryORM.human_decision.is_not(None))
            )
            human_review_count: int = (await session.execute(human_review_stmt)).scalar_one()

            # ---- per-node average duration across all runs ----
            node_duration_stmt = (
                select(
                    AuditLogEntryORM.node,
                    func.avg(AuditLogEntryORM.duration_ms).label("avg_ms"),
                )
                .join(WorkflowRun, AuditLogEntryORM.run_id == WorkflowRun.id)
                .where(WorkflowRun.workflow_name == workflow_name)
                .where(AuditLogEntryORM.duration_ms.is_not(None))
                .group_by(AuditLogEntryORM.node)
                .order_by(func.avg(AuditLogEntryORM.duration_ms).desc())
            )
            node_duration_rows = (await session.execute(node_duration_stmt)).all()

        avg_duration_ms_by_node: dict[str, float] = {
            row.node: float(row.avg_ms) for row in node_duration_rows
        }

        slowest_node: str | None = None
        slowest_node_avg_ms: float = 0.0
        if node_duration_rows:
            slowest_node = node_duration_rows[0].node
            slowest_node_avg_ms = float(node_duration_rows[0].avg_ms)

        return {
            "workflow_name": workflow_name,
            "total_runs": total_runs,
            "success_count": success_count,
            "failure_count": failure_count,
            "human_review_count": human_review_count,
            "success_ratio": success_count / total_runs if total_runs else 0.0,
            "failure_ratio": failure_count / total_runs if total_runs else 0.0,
            "human_review_ratio": human_review_count / total_runs if total_runs else 0.0,
            "avg_duration_ms_by_node": avg_duration_ms_by_node,
            "slowest_node": slowest_node,
            "slowest_node_avg_ms": slowest_node_avg_ms,
        }

    async def get_cost_summary(self, run_id: str | uuid.UUID) -> dict[str, Any]:
        """Return total token usage and cost for a single workflow run.

        Returns a dict with:

        - ``run_id``: stringified UUID.
        - ``total_tokens``: sum of ``tokens_used`` across all audit entries.
        - ``total_cost_usd``: sum of ``cost_usd`` across all audit entries.
        - ``entry_count``: number of audit entries for the run.
        """
        run_uuid = uuid.UUID(str(run_id))
        async with self._session_factory() as session:
            stmt = select(
                func.sum(AuditLogEntryORM.tokens_used).label("total_tokens"),
                func.sum(AuditLogEntryORM.cost_usd).label("total_cost_usd"),
                func.count(AuditLogEntryORM.id).label("entry_count"),
            ).where(AuditLogEntryORM.run_id == run_uuid)
            row = (await session.execute(stmt)).one()

        return {
            "run_id": str(run_uuid),
            "total_tokens": int(row.total_tokens or 0),
            "total_cost_usd": float(row.total_cost_usd or 0.0),
            "entry_count": int(row.entry_count),
        }


# ---------------------------------------------------------------------------
# Module-level singleton (uses the global Postgres session factory)
# ---------------------------------------------------------------------------

_analytics: WorkflowAnalytics | None = None


def get_analytics() -> WorkflowAnalytics:
    """Return the module-level WorkflowAnalytics singleton."""
    global _analytics
    if _analytics is None:
        _analytics = WorkflowAnalytics(get_session_factory())
    return _analytics

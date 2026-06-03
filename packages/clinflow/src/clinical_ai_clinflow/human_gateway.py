"""Human-in-the-loop gateway service for ClinFlow AI.

Responsibilities:
1. Persist a pending review record to PostgreSQL when a workflow pauses at a
   human_gateway node.
2. Send reviewer notifications via Slack webhook or email (fire-and-forget).
3. Record human decisions and publish to Redis so the waiting workflow resumes.
4. Wait for a decision with a configurable timeout.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
from clinical_ai_shared.db.models import HumanReview
from clinical_ai_shared.db.redis import publish, subscribe
from clinical_ai_shared.observability.logging import get_logger
from sqlalchemy import select

from clinical_ai_clinflow.engine import HumanDecision

if TYPE_CHECKING:
    from clinical_ai_shared.config import Settings
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger(__name__)

_REDIS_CHANNEL_PREFIX = "workflow"


def _decision_channel(run_id: str) -> str:
    return f"{_REDIS_CHANNEL_PREFIX}:{run_id}:decision"


class HumanGatewayService:
    """Manages human-in-the-loop review gates in ClinFlow workflows.

    Args:
        session_factory: Async session factory from ``get_session_factory()``.
        settings: Application settings (used to resolve notification config).
        api_base_url: Base URL for approve/reject action links in notifications.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        api_base_url: str = "http://localhost:8000",
    ) -> None:
        self._factory = session_factory
        self._settings = settings
        self._api_base_url = api_base_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def pause(
        self,
        run_id: str,
        node_id: str,
        context: dict[str, Any],
        workflow_name: str,
    ) -> None:
        """Persist a pending review record and dispatch a reviewer notification.

        Returns immediately — does NOT block waiting for a decision.
        """
        run_uuid = _coerce_uuid(run_id)

        review = HumanReview(
            id=uuid.uuid4(),
            run_id=run_uuid,
            node_id=node_id,
            workflow_name=workflow_name,
            context=context,
            status="pending",
        )
        async with self._factory() as session:
            session.add(review)
            await session.commit()

        logger.info(
            "human_gateway_paused",
            run_id=run_id,
            node_id=node_id,
            workflow_name=workflow_name,
        )

        approve_url = f"{self._api_base_url}/api/v1/approvals/{run_id}/approve"
        reject_url = f"{self._api_base_url}/api/v1/approvals/{run_id}/reject"
        summary = _context_summary(context)

        # Fire notification without blocking the caller.
        asyncio.create_task(
            self._send_notification(
                run_id=run_id,
                workflow_name=workflow_name,
                node_id=node_id,
                summary=summary,
                approve_url=approve_url,
                reject_url=reject_url,
            )
        )

    async def submit_decision(self, run_id: str, decision: HumanDecision) -> None:
        """Record a human decision and publish it to Redis so the workflow resumes.

        Args:
            run_id: The run identifier that is paused.
            decision: Approved/rejected decision with optional state edits.

        Raises:
            ValueError: If no pending review exists for *run_id*.
        """
        run_uuid = _coerce_uuid(run_id)

        async with self._factory() as session:
            row = await _load_pending_review(session, run_uuid)
            if row is None:
                raise ValueError(f"No pending review found for run_id={run_id}")

            row.status = decision.decision
            row.reviewer_id = decision.reviewer_id
            row.decision_at = datetime.now(UTC)
            await session.commit()

        payload = json.dumps(
            {
                "decision": decision.decision,
                "reviewer_id": decision.reviewer_id,
                "edits": decision.edits,
            }
        )
        await publish(_decision_channel(run_id), payload)
        logger.info(
            "human_decision_submitted",
            run_id=run_id,
            decision=decision.decision,
            reviewer_id=decision.reviewer_id,
        )

    async def wait_for_decision(
        self,
        run_id: str,
        timeout_seconds: int = 3600,
    ) -> HumanDecision:
        """Subscribe to the Redis decision channel and return when a decision arrives.

        Args:
            run_id: The run identifier to wait on.
            timeout_seconds: How long to wait before raising ``TimeoutError``.

        Returns:
            The ``HumanDecision`` published by ``submit_decision``.

        Raises:
            TimeoutError: If no decision arrives within *timeout_seconds*.
        """
        channel = _decision_channel(run_id)

        async def _receive() -> HumanDecision:
            async for raw in subscribe(channel):
                data: dict[str, Any] = json.loads(raw)
                return HumanDecision(
                    decision=data["decision"],
                    reviewer_id=data["reviewer_id"],
                    edits=data.get("edits", {}),
                )
            raise RuntimeError("Redis channel closed before a decision was received")

        try:
            return await asyncio.wait_for(_receive(), timeout=float(timeout_seconds))
        except TimeoutError as exc:
            raise TimeoutError(
                f"No decision received for run {run_id} within {timeout_seconds}s"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_notification(
        self,
        *,
        run_id: str,
        workflow_name: str,
        node_id: str,
        summary: str,
        approve_url: str,
        reject_url: str,
    ) -> None:
        """Send notification via Slack webhook or log an email fallback.

        Never raises — failures are logged as warnings.
        """
        message = (
            f"*[ClinFlow HITL]* Workflow `{workflow_name}` paused at node `{node_id}`.\n"
            f"Run ID: `{run_id}`\n"
            f"Context: {summary}\n"
            f"• Approve: {approve_url}\n"
            f"• Reject:  {reject_url}"
        )

        webhook_url = self._settings.slack_webhook_url
        if webhook_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(webhook_url, json={"text": message})
                logger.info("slack_notification_sent", run_id=run_id)
            except Exception as exc:
                logger.warning("slack_notification_failed", run_id=run_id, error=str(exc))
            return

        notification_email = self._settings.notification_email
        if notification_email:
            # Email transport not yet wired — log the intent so it is visible.
            logger.info(
                "email_notification_pending",
                run_id=run_id,
                recipient=notification_email,
                subject=f"[ClinFlow HITL] Action required for run {run_id}",
                body=message,
            )
            return

        logger.warning(
            "no_notification_channel_configured",
            run_id=run_id,
            hint="Set SLACK_WEBHOOK_URL or NOTIFICATION_EMAIL in your .env",
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _coerce_uuid(run_id: str) -> uuid.UUID:
    """Parse run_id as UUID; fall back to deterministic uuid5 for readable IDs."""
    try:
        return uuid.UUID(run_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, run_id)


def _context_summary(context: dict[str, Any]) -> str:
    """Return a short human-readable summary of the workflow context dict."""
    keys = list(context.keys())[:5]
    parts = [f"{k}={str(context[k])[:40]!r}" for k in keys]
    suffix = " …" if len(context) > 5 else ""
    return "{" + ", ".join(parts) + suffix + "}"


async def _load_pending_review(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> HumanReview | None:
    result = await session.execute(
        select(HumanReview)
        .where(HumanReview.run_id == run_id, HumanReview.status == "pending")
        .limit(1)
    )
    return result.scalar_one_or_none()

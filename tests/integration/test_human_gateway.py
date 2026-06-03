"""Integration tests for HumanGatewayService and the approvals API.

Requires:
    Docker Compose stack running (PostgreSQL on localhost:5432, Redis on localhost:6379).
    ``pytest -m integration`` or ``uv run pytest tests/integration/``.

Coverage:
1. pause() persists a pending review record and fires the Slack notification.
2. submit_decision() + wait_for_decision() round-trip via Redis pub/sub.
3. POST /api/v1/approvals/{run_id}/approve resumes a paused workflow.
4. POST /api/v1/approvals/{run_id}/reject routes to the rejection path.
5. GET /api/v1/approvals/pending returns all pending reviews.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from clinical_ai_clinflow.engine import (
    AgentCallable,
    HumanDecision,
    HumanGatewayPause,
    WorkflowEngine,
    WorkflowResult,
)
from clinical_ai_clinflow.human_gateway import HumanGatewayService
from clinical_ai_clinflow.loader import load_workflow_from_string
from clinical_ai_shared.config import Settings
from clinical_ai_shared.db.models import HumanReview
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.main import app

# ---------------------------------------------------------------------------
# Pytest marks
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Database / Redis URLs (Docker Compose stack)
# ---------------------------------------------------------------------------

_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai"

# ---------------------------------------------------------------------------
# Session-scoped async engine + session factory
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(_DB_URL, echo=False)
    import clinical_ai_shared.db.models  # noqa: F401, PLC0415 — registers ORM models
    from clinical_ai_shared.db.postgres import Base  # noqa: PLC0415

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def session_factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def clean_run_id(session_factory):
    """Generate a fresh run_id and clean up DB rows afterwards."""
    run_id = str(uuid.uuid4())
    yield run_id
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM human_reviews WHERE run_id = :id"),
            {"id": uuid.UUID(run_id)},
        )
        await session.execute(
            text("DELETE FROM workflow_runs WHERE id = :id"),
            {"id": uuid.UUID(run_id)},
        )
        await session.commit()


@pytest.fixture
def mock_settings(monkeypatch) -> Settings:
    """Return Settings with a fake Slack webhook URL."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.example.com/test")
    # Return a Settings-like object that exposes the necessary attributes.
    settings = MagicMock(spec=Settings)
    settings.slack_webhook_url = "https://hooks.slack.example.com/test"
    settings.notification_email = None
    return settings


def _make_gateway(session_factory, settings: Any) -> HumanGatewayService:
    return HumanGatewayService(
        session_factory=session_factory,
        settings=settings,
        api_base_url="http://localhost:8000",
    )


# ---------------------------------------------------------------------------
# Workflow YAML — single human_gateway node between two agent nodes
# ---------------------------------------------------------------------------

GATEWAY_WORKFLOW_YAML = """\
name: gateway_test
version: "1.0"
state_schema:
  input: str
  pre_done: bool | null
  post_done: bool | null

nodes:
  - id: pre_agent
    agent: pre_agent
  - id: review_gate
    type: human_gateway
  - id: post_approved
    agent: post_approved
  - id: post_rejected
    agent: post_rejected

edges:
  - from: pre_agent
    to: review_gate
  - from: review_gate
    to: post_approved
    condition: "approved"
  - from: review_gate
    to: post_rejected
    condition: "rejected"
  - from: post_approved
    to: END
  - from: post_rejected
    to: END
"""


async def _pre_agent(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "pre_done": True}


async def _post_approved(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "post_done": True, "outcome": "approved"}


async def _post_rejected(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "post_done": True, "outcome": "rejected"}


def _build_gateway_registry() -> dict[str, AgentCallable]:
    return {
        "pre_agent": _pre_agent,
        "post_approved": _post_approved,
        "post_rejected": _post_rejected,
    }


# ---------------------------------------------------------------------------
# Test 1: pause() saves pending record + fires Slack notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_creates_pending_review_and_notifies(
    clean_run_id, session_factory, mock_settings
):
    run_id = clean_run_id
    gateway = _make_gateway(session_factory, mock_settings)

    context = {"document_id": "doc-123", "confidence": 0.72}

    # Mock the httpx POST call to capture the Slack notification.
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("clinical_ai_clinflow.human_gateway.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await gateway.pause(run_id, "review_gate", context, "gateway_test")

        # Allow the fire-and-forget task to run.
        await asyncio.sleep(0.1)

    # Verify a pending review was persisted.
    async with session_factory() as session:
        row = (
            await session.execute(
                select(HumanReview).where(
                    HumanReview.run_id == uuid.UUID(run_id),
                    HumanReview.status == "pending",
                )
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.node_id == "review_gate"
    assert row.workflow_name == "gateway_test"
    assert row.status == "pending"

    # Verify the Slack notification was fired.
    mock_http.post.assert_called_once()
    call_kwargs = mock_http.post.call_args
    assert "hooks.slack.example.com" in call_kwargs.args[0]
    payload = call_kwargs.kwargs["json"]
    assert run_id in payload["text"]
    assert "approve" in payload["text"].lower() or "Approve" in payload["text"]


# ---------------------------------------------------------------------------
# Test 2: submit_decision + wait_for_decision round-trip via Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_and_wait_for_decision(clean_run_id, session_factory, mock_settings):
    run_id = clean_run_id
    gateway = _make_gateway(session_factory, mock_settings)

    # Seed a pending review (skip notification for this test).
    review = HumanReview(
        id=uuid.uuid4(),
        run_id=uuid.UUID(run_id),
        node_id="review_gate",
        workflow_name="gateway_test",
        context={"x": 1},
        status="pending",
    )
    async with session_factory() as session:
        session.add(review)
        await session.commit()

    # Start waiting for decision in background.
    wait_task = asyncio.create_task(gateway.wait_for_decision(run_id, timeout_seconds=10))

    # Give the subscriber a moment to attach before publishing.
    await asyncio.sleep(0.1)

    # Submit the decision.
    decision = HumanDecision(decision="approved", reviewer_id="dr_alice", edits={})
    await gateway.submit_decision(run_id, decision)

    received = await asyncio.wait_for(wait_task, timeout=5)

    assert received.decision == "approved"
    assert received.reviewer_id == "dr_alice"

    # Verify the DB row was updated.
    async with session_factory() as session:
        row = (
            await session.execute(
                select(HumanReview).where(HumanReview.run_id == uuid.UUID(run_id))
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.status == "approved"
    assert row.reviewer_id == "dr_alice"
    assert row.decision_at is not None


# ---------------------------------------------------------------------------
# Test 3: engine raises HumanGatewayPause, then workflow resumes via approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_pauses_at_gateway_and_resumes_on_approve(
    clean_run_id, session_factory, mock_settings
):
    run_id = clean_run_id
    wf = load_workflow_from_string(GATEWAY_WORKFLOW_YAML)

    from clinical_ai_clinflow.checkpoint import PostgresCheckpointer  # noqa: PLC0415

    checkpointer = PostgresCheckpointer(session_factory, workflow_name="gateway_test")
    engine = WorkflowEngine(wf, _build_gateway_registry(), checkpointer)
    gateway = _make_gateway(session_factory, mock_settings)

    # --- Phase 1: run until the gateway pauses. ---
    with patch("clinical_ai_clinflow.human_gateway.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HumanGatewayPause) as exc_info:
            await engine.run({"input": "test"}, run_id=run_id)

        pause = exc_info.value
        assert pause.run_id == run_id
        assert pause.node_id == "review_gate"

        # Persist the pending review.
        await gateway.pause(
            run_id=pause.run_id,
            node_id=pause.node_id,
            context=pause.context_for_reviewer,
            workflow_name="gateway_test",
        )
        await asyncio.sleep(0.1)

    # Verify the review is pending.
    async with session_factory() as session:
        row = (
            await session.execute(
                select(HumanReview).where(
                    HumanReview.run_id == uuid.UUID(run_id),
                    HumanReview.status == "pending",
                )
            )
        ).scalar_one_or_none()
    assert row is not None

    # --- Phase 2: approve and resume. ---
    decision = HumanDecision(decision="approved", reviewer_id="dr_bob", edits={})
    await gateway.submit_decision(run_id, decision)

    result = await engine.resume(run_id, decision)

    assert isinstance(result, WorkflowResult)
    assert result.final_state.get("outcome") == "approved"
    assert result.final_state.get("pre_done") is True
    assert result.final_state.get("post_done") is True


# ---------------------------------------------------------------------------
# Test 4: reject path routes to post_rejected node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_routes_to_rejection_path(clean_run_id, session_factory, mock_settings):
    run_id = clean_run_id
    wf = load_workflow_from_string(GATEWAY_WORKFLOW_YAML)

    from clinical_ai_clinflow.checkpoint import PostgresCheckpointer  # noqa: PLC0415

    checkpointer = PostgresCheckpointer(session_factory, workflow_name="gateway_test")
    engine = WorkflowEngine(wf, _build_gateway_registry(), checkpointer)
    gateway = _make_gateway(session_factory, mock_settings)

    with patch("clinical_ai_clinflow.human_gateway.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HumanGatewayPause) as exc_info:
            await engine.run({"input": "test"}, run_id=run_id)

        pause = exc_info.value
        await gateway.pause(
            run_id=pause.run_id,
            node_id=pause.node_id,
            context=pause.context_for_reviewer,
            workflow_name="gateway_test",
        )
        await asyncio.sleep(0.1)

    decision = HumanDecision(
        decision="rejected",
        reviewer_id="dr_carol",
        edits={"reason": "unclear"},
    )
    await gateway.submit_decision(run_id, decision)

    result = await engine.resume(run_id, decision)

    assert isinstance(result, WorkflowResult)
    assert result.final_state.get("outcome") == "rejected"


# ---------------------------------------------------------------------------
# Test 5: API — approve endpoint
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http_client():
    """Async HTTP client pointed at the FastAPI app under test."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_approve_endpoint(clean_run_id, session_factory, http_client):
    run_id = clean_run_id

    # Seed a pending review.
    review = HumanReview(
        id=uuid.uuid4(),
        run_id=uuid.UUID(run_id),
        node_id="review_gate",
        workflow_name="gateway_test",
        context={"x": 1},
        status="pending",
    )
    async with session_factory() as session:
        session.add(review)
        await session.commit()

    # The endpoint calls gateway.submit_decision which publishes to Redis.
    # We need to drain the Redis message — subscribe before calling the endpoint.
    from clinical_ai_shared.db.redis import subscribe  # noqa: PLC0415

    async def _drain():
        async for _ in subscribe(f"workflow:{run_id}:decision"):
            return

    drain_task = asyncio.create_task(_drain())
    await asyncio.sleep(0.05)

    response = await http_client.post(
        f"/api/v1/approvals/{run_id}/approve",
        json={"reviewer_id": "dr_dana", "edits": None},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Cancel drain task — we only needed to unblock Redis.
    drain_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await drain_task

    # Verify DB updated.
    async with session_factory() as session:
        row = (
            await session.execute(
                select(HumanReview).where(HumanReview.run_id == uuid.UUID(run_id))
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.status == "approved"
    assert row.reviewer_id == "dr_dana"


# ---------------------------------------------------------------------------
# Test 6: API — reject endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_endpoint(clean_run_id, session_factory, http_client):
    run_id = clean_run_id

    review = HumanReview(
        id=uuid.uuid4(),
        run_id=uuid.UUID(run_id),
        node_id="review_gate",
        workflow_name="gateway_test",
        context={"y": 2},
        status="pending",
    )
    async with session_factory() as session:
        session.add(review)
        await session.commit()

    from clinical_ai_shared.db.redis import subscribe  # noqa: PLC0415

    async def _drain():
        async for _ in subscribe(f"workflow:{run_id}:decision"):
            return

    drain_task = asyncio.create_task(_drain())
    await asyncio.sleep(0.05)

    response = await http_client.post(
        f"/api/v1/approvals/{run_id}/reject",
        json={"reviewer_id": "dr_eve", "reason": "missing data"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    drain_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await drain_task

    async with session_factory() as session:
        row = (
            await session.execute(
                select(HumanReview).where(HumanReview.run_id == uuid.UUID(run_id))
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.status == "rejected"


# ---------------------------------------------------------------------------
# Test 7: API — pending list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pending_endpoint(clean_run_id, session_factory, http_client):
    run_id = clean_run_id

    review = HumanReview(
        id=uuid.uuid4(),
        run_id=uuid.UUID(run_id),
        node_id="review_gate",
        workflow_name="pending_test",
        context={},
        status="pending",
    )
    async with session_factory() as session:
        session.add(review)
        await session.commit()

    response = await http_client.get("/api/v1/approvals/pending")

    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    matching = [i for i in items if i["run_id"] == run_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "pending"
    assert matching[0]["workflow_name"] == "pending_test"


# ---------------------------------------------------------------------------
# Test 8: approve endpoint returns 404 when no pending review exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_endpoint_404_when_no_pending(http_client):
    nonexistent_run_id = str(uuid.uuid4())
    response = await http_client.post(
        f"/api/v1/approvals/{nonexistent_run_id}/approve",
        json={"reviewer_id": "dr_frank"},
    )
    assert response.status_code == 404

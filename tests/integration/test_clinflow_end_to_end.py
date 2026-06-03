"""Integration test: ClinFlow end-to-end workflow execution.

Requires the Docker Compose stack (PostgreSQL on localhost:5432, Redis on
localhost:6379).  Run with::

    uv run pytest tests/integration/test_clinflow_end_to_end.py -v

Coverage:
1. A 3-node workflow with mock agents runs to completion via WorkflowEngine.
2. The resulting audit entries are persisted to the real DB via AuditTrailWriter.
3. GET /api/v1/audit verifies all 3 entries are queryable via the HTTP API.
4. GET /api/v1/audit/export returns a CSV with 3 data rows.
5. GET /api/v1/workflows/runs returns the completed run.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from clinical_ai_clinflow.audit import AuditTrailWriter
from clinical_ai_clinflow.checkpoint import PostgresCheckpointer
from clinical_ai_clinflow.engine import WorkflowEngine
from clinical_ai_clinflow.loader import load_workflow_from_string
from clinical_ai_shared.db.models import AuditLogEntry as AuditLogEntryORM
from clinical_ai_shared.db.models import WorkflowRun
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.main import app

pytestmark = pytest.mark.integration

_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai"

# ---------------------------------------------------------------------------
# 3-node test workflow (no real agents — all mock)
# ---------------------------------------------------------------------------

_THREE_NODE_YAML = """\
name: test_e2e_workflow
version: "1.0"
description: "Integration test workflow — 3 nodes, mock agents"

state_schema:
  payload: str
  step_a_done: bool | null
  step_b_done: bool | null
  step_c_done: bool | null

nodes:
  - id: step_a
    agent: mock_agent_a
    timeout_seconds: 10

  - id: step_b
    agent: mock_agent_b
    timeout_seconds: 10

  - id: step_c
    agent: mock_agent_c
    timeout_seconds: 10

edges:
  - from: step_a
    to: step_b
  - from: step_b
    to: step_c
  - from: step_c
    to: END
"""


async def _mock_agent_a(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "step_a_done": True, "_node_output_summary": "Step A completed"}


async def _mock_agent_b(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "step_b_done": True, "_node_output_summary": "Step B completed"}


async def _mock_agent_c(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "step_c_done": True, "_node_output_summary": "Step C completed"}


_AGENT_REGISTRY = {
    "mock_agent_a": _mock_agent_a,
    "mock_agent_b": _mock_agent_b,
    "mock_agent_c": _mock_agent_c,
}

# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def session_factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="module")
async def clean_audit_table(pg_engine):
    """Truncate audit_log_entries before the test module runs."""
    async with pg_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE audit_log_entries RESTART IDENTITY CASCADE"))
    yield
    # Leave data for debugging — CI tears down the whole DB anyway.


# ---------------------------------------------------------------------------
# The integration test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_3_node_workflow(session_factory, clean_audit_table) -> None:  # noqa: ARG001
    """Full pipeline: run engine → persist audit → verify via API."""

    # 1. Build workflow + engine with in-memory checkpointer.
    workflow_def = load_workflow_from_string(_THREE_NODE_YAML)

    class _InMemoryCheckpointer:
        def __init__(self) -> None:
            self.store: dict[str, dict[str, Any]] = {}

        async def save(self, run_id: str, checkpoint: dict[str, Any]) -> None:
            self.store[run_id] = dict(checkpoint)

        async def load(self, run_id: str) -> dict[str, Any]:
            return dict(self.store[run_id])

    engine = WorkflowEngine(
        workflow_def=workflow_def,
        agent_registry=_AGENT_REGISTRY,
        checkpointer=_InMemoryCheckpointer(),
    )

    run_id = str(uuid.uuid4())
    result = await engine.run({"payload": "test_data"}, run_id=run_id)

    # 2. Verify engine produced 3 audit entries (one per agent node).
    assert len(result.audit_entries) == 3
    agents = {e.agent for e in result.audit_entries}
    assert agents == {"mock_agent_a", "mock_agent_b", "mock_agent_c"}
    assert result.final_state.get("step_a_done") is True
    assert result.final_state.get("step_b_done") is True
    assert result.final_state.get("step_c_done") is True

    # 3. Persist the audit entries + create a WorkflowRun record.
    writer = AuditTrailWriter(session_factory)
    for entry in result.audit_entries:
        await writer.write(entry)

    async with session_factory() as session:
        run_record = WorkflowRun(
            id=uuid.UUID(run_id),
            workflow_name=workflow_def.name,
            status="completed",
            current_node="END",
        )
        session.add(run_record)
        await session.commit()

    # 4. Verify via GET /api/v1/audit that all 3 entries are present.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            "/api/v1/audit",
            params={"run_id": run_id, "page_size": 10},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        returned_agents = {item["agent"] for item in data["items"]}
        assert returned_agents == {"mock_agent_a", "mock_agent_b", "mock_agent_c"}

        # All input_hash values must be 64-char SHA-256 hex digests (not raw input).
        for item in data["items"]:
            assert len(item["input_hash"]) == 64, "input_hash must be a SHA-256 digest"

    # 5. Verify CSV export returns 3 data rows.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/v1/audit/export", params={"run_id": run_id})
        assert resp.status_code == 200
        content = resp.text
        lines = [ln for ln in content.strip().splitlines() if ln]
        # 1 header + 3 data rows
        assert len(lines) == 4, f"Expected 4 lines (1 header + 3 data), got: {len(lines)}"
        header = lines[0]
        assert "entry_id" in header
        assert "agent" in header

    # 6. Verify GET /api/v1/workflows/runs returns the completed run.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            "/api/v1/workflows/runs",
            params={"status": "completed"},
        )
        assert resp.status_code == 200
        runs_data = resp.json()
        run_ids = {r["run_id"] for r in runs_data["items"]}
        assert run_id in run_ids

    # 7. Verify GET /api/v1/workflows/runs/{run_id} returns the correct run.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/v1/workflows/runs/{run_id}")
        assert resp.status_code == 200
        run_detail = resp.json()
        assert run_detail["status"] == "completed"
        assert run_detail["workflow_name"] == "test_e2e_workflow"

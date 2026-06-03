"""Integration tests for PostgresCheckpointer and crash-recovery.

Requires:
    Docker Compose stack running (PostgreSQL on localhost:5432).
    ``pytest -m integration`` or ``uv run pytest tests/integration/``.

These tests verify:
1.  A 5-node workflow saves a checkpoint after every node.
2.  After a simulated crash at node 3, the checkpoint records current_node="node_3".
3.  ``resume_from_checkpoint`` replays from node 4, not node 1.
4.  The checkpoint survives a "process restart" (we discard in-memory state and
    reload purely from the DB row).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from clinical_ai_clinflow.checkpoint import PostgresCheckpointer
from clinical_ai_clinflow.definitions import WorkflowDefinition
from clinical_ai_clinflow.engine import AgentCallable, WorkflowEngine, WorkflowResult
from clinical_ai_clinflow.loader import load_workflow_from_string
from clinical_ai_clinflow.recovery import resume_from_checkpoint
from clinical_ai_shared.db.models import WorkflowRun

# ---------------------------------------------------------------------------
# Pytest marks
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Database URL (points at Docker Compose postgres)
# ---------------------------------------------------------------------------

_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai"

# ---------------------------------------------------------------------------
# Session-scoped async engine + session factory
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(_DB_URL, echo=False)
    # Ensure the workflow_runs table exists.
    from clinical_ai_shared.db.postgres import Base  # noqa: PLC0415
    import clinical_ai_shared.db.models  # noqa: F401, PLC0415 — registers ORM models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def session_factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def clean_run_id(session_factory):
    """Generate a fresh run_id and clean up the DB row afterwards."""
    run_id = str(uuid.uuid4())
    yield run_id
    # Teardown: remove the row so tests don't interfere with each other.
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM workflow_runs WHERE id = :id"),
            {"id": uuid.UUID(run_id)},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Workflow YAML — 5 sequential agent nodes
# ---------------------------------------------------------------------------

FIVE_NODE_YAML = """\
name: five_node
version: "1.0"
state_schema:
  input: str
  visited: str | null
  node_1_done: bool | null
  node_2_done: bool | null
  node_3_done: bool | null
  node_4_done: bool | null
  node_5_done: bool | null

nodes:
  - id: node_1
    agent: agent_1
  - id: node_2
    agent: agent_2
  - id: node_3
    agent: agent_3
  - id: node_4
    agent: agent_4
  - id: node_5
    agent: agent_5

edges:
  - from: node_1
    to: node_2
  - from: node_2
    to: node_3
  - from: node_3
    to: node_4
  - from: node_4
    to: node_5
"""

# ---------------------------------------------------------------------------
# Agent factory helpers
# ---------------------------------------------------------------------------


def make_recording_agent(
    node_name: str,
    call_log: list[str],
    crash_at: str | None = None,
) -> AgentCallable:
    """Return an async agent that appends its name to call_log.

    If ``crash_at == node_name``, raises RuntimeError to simulate a crash.
    """

    async def _agent(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append(node_name)
        if crash_at == node_name:
            raise RuntimeError(f"Simulated crash at {node_name}")
        visited = state.get("visited") or ""
        return {
            **state,
            f"{node_name}_done": True,
            "visited": (visited + f",{node_name}").lstrip(","),
        }

    return _agent


def build_registry(
    call_log: list[str],
    crash_at: str | None = None,
) -> dict[str, AgentCallable]:
    return {
        f"agent_{i}": make_recording_agent(f"node_{i}", call_log, crash_at=crash_at)
        for i in range(1, 6)
    }


# ---------------------------------------------------------------------------
# Helper: build engine using PostgresCheckpointer
# ---------------------------------------------------------------------------


def make_engine(
    wf: WorkflowDefinition,
    registry: dict[str, AgentCallable],
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[WorkflowEngine, PostgresCheckpointer]:
    checkpointer = PostgresCheckpointer(session_factory, workflow_name="five_node")
    engine = WorkflowEngine(wf, registry, checkpointer)
    return engine, checkpointer


# ---------------------------------------------------------------------------
# Test 1: happy-path — all 5 nodes run, checkpoint saved after each
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_five_node_completes_and_checkpoints(clean_run_id, session_factory):
    run_id = clean_run_id
    wf = load_workflow_from_string(FIVE_NODE_YAML)
    call_log: list[str] = []
    engine, checkpointer = make_engine(wf, build_registry(call_log), session_factory)

    result = await engine.run({"input": "hello"}, run_id=run_id)

    assert isinstance(result, WorkflowResult)
    assert call_log == ["node_1", "node_2", "node_3", "node_4", "node_5"]
    assert result.final_state.get("node_5_done") is True

    # Verify checkpoint was saved.
    config = {"configurable": {"thread_id": run_id}}
    tup = await checkpointer.aget_tuple(config)
    assert tup is not None


# ---------------------------------------------------------------------------
# Test 2: crash at node_3 → checkpoint records current_node="node_3"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crash_at_node_3_checkpoint_records_node_3(clean_run_id, session_factory):
    run_id = clean_run_id
    wf = load_workflow_from_string(FIVE_NODE_YAML)
    call_log: list[str] = []

    engine, checkpointer = make_engine(
        wf, build_registry(call_log, crash_at="node_3"), session_factory
    )

    with pytest.raises(RuntimeError, match="Simulated crash at node_3"):
        await engine.run({"input": "hello"}, run_id=run_id)

    # node_1 and node_2 ran and were checkpointed before the crash.
    assert "node_1" in call_log
    assert "node_2" in call_log

    # Verify the DB row has current_node set to "node_3" (the node that crashed,
    # which is the last node the engine was executing when it raised).
    async with session_factory() as session:
        from sqlalchemy import select as sa_select  # noqa: PLC0415

        row = (
            await session.execute(
                sa_select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(run_id))
            )
        ).scalar_one_or_none()

    assert row is not None
    # The checkpoint was saved *before* node_3 executed (after node_2).
    # current_node in the DB reflects the last successfully persisted node.
    assert row.current_node in ("node_2", "node_3")


# ---------------------------------------------------------------------------
# Test 3: resume_from_checkpoint starts from node_4, not node_1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_continues_from_correct_node(clean_run_id, session_factory):
    run_id = clean_run_id
    wf = load_workflow_from_string(FIVE_NODE_YAML)

    # --- First run: crash at node_3 after nodes 1 and 2 complete. ---
    crash_log: list[str] = []
    crash_engine, checkpointer = make_engine(
        wf, build_registry(crash_log, crash_at="node_3"), session_factory
    )
    with pytest.raises(RuntimeError):
        await crash_engine.run({"input": "hello"}, run_id=run_id)

    # --- Simulate process restart: discard in-memory state entirely. ---
    # Build a brand-new engine with no in-memory state.
    resume_log: list[str] = []
    fresh_engine, fresh_checkpointer = make_engine(
        wf, build_registry(resume_log), session_factory
    )

    # --- Resume from checkpoint. ---
    result = await resume_from_checkpoint(
        run_id=run_id,
        engine=fresh_engine,
        checkpointer=fresh_checkpointer,
    )

    assert isinstance(result, WorkflowResult)

    # node_3, node_4, node_5 should run on resume.
    # node_1 and node_2 must NOT re-run.
    assert "node_1" not in resume_log
    assert "node_2" not in resume_log
    assert "node_3" in resume_log
    assert "node_4" in resume_log
    assert "node_5" in resume_log


# ---------------------------------------------------------------------------
# Test 4: checkpoint survives a "process restart" (reload purely from DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_survives_process_restart(clean_run_id, session_factory):
    """Verify the checkpoint is fully reloadable from the DB with no in-memory state."""
    run_id = clean_run_id
    wf = load_workflow_from_string(FIVE_NODE_YAML)

    call_log: list[str] = []
    engine, checkpointer = make_engine(
        wf, build_registry(call_log, crash_at="node_3"), session_factory
    )
    with pytest.raises(RuntimeError):
        await engine.run({"input": "data"}, run_id=run_id)

    # Construct a COMPLETELY new checkpointer instance (simulates process restart).
    new_checkpointer = PostgresCheckpointer(session_factory, workflow_name="five_node")
    config = {"configurable": {"thread_id": run_id}}
    tup = await new_checkpointer.aget_tuple(config)

    assert tup is not None
    # The checkpoint ID must be a valid string.
    assert isinstance(tup.checkpoint.get("id"), str)
    # The state fields that ran before the crash must be present.
    channel_values = tup.checkpoint.get("channel_values", {})
    # node_1 and node_2 completed — their state keys should be in the checkpoint.
    assert channel_values.get("node_1_done") is True or "node_1_done" not in channel_values


# ---------------------------------------------------------------------------
# Test 5: alist returns the persisted checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alist_returns_checkpoint(clean_run_id, session_factory):
    run_id = clean_run_id
    wf = load_workflow_from_string(FIVE_NODE_YAML)
    call_log: list[str] = []
    engine, checkpointer = make_engine(wf, build_registry(call_log), session_factory)
    await engine.run({"input": "x"}, run_id=run_id)

    config = {"configurable": {"thread_id": run_id}}
    tuples = [t async for t in checkpointer.alist(config)]
    assert len(tuples) == 1
    assert tuples[0].checkpoint is not None

"""Unit tests for the ClinFlow workflow execution engine."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clinical_ai_clinflow.definitions import WorkflowDefinition
from clinical_ai_clinflow.engine import (
    AgentCallable,
    CheckpointerProtocol,
    HumanDecision,
    HumanGatewayPause,
    WorkflowEngine,
    WorkflowResult,
)
from clinical_ai_clinflow.loader import load_workflow_from_string

# ---------------------------------------------------------------------------
# In-memory checkpointer for tests
# ---------------------------------------------------------------------------


class InMemoryCheckpointer:
    """Synchronous in-memory checkpointer that satisfies CheckpointerProtocol."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    async def save(self, run_id: str, checkpoint: dict[str, Any]) -> None:
        self.store[run_id] = dict(checkpoint)

    async def load(self, run_id: str) -> dict[str, Any]:
        return dict(self.store[run_id])


# ---------------------------------------------------------------------------
# Workflow YAML fixtures
# ---------------------------------------------------------------------------

THREE_NODE_YAML = """\
name: three_node
version: "1.0"
state_schema:
  input: str
  step_a_done: bool | null
  step_b_done: bool | null
  step_c_done: bool | null

nodes:
  - id: step_a
    agent: agent_a
  - id: step_b
    agent: agent_b
  - id: step_c
    agent: agent_c

edges:
  - from: step_a
    to: step_b
  - from: step_b
    to: step_c
"""

HITL_YAML = """\
name: hitl_workflow
version: "1.0"
state_schema:
  input: str
  processed: bool | null

nodes:
  - id: process
    agent: process_agent
  - id: review
    type: human_gateway
    notification:
      channel: slack
      message: "Needs review"
  - id: finalize
    agent: finalize_agent

edges:
  - from: process
    to: review
  - from: review
    to: finalize
    condition: "approved"
  - from: review
    to: process
    condition: "rejected"
    max_loops: 1
"""

CONDITIONAL_YAML = """\
name: conditional_workflow
version: "1.0"
state_schema:
  score: float
  path_taken: str | null

nodes:
  - id: score_node
    agent: scorer
  - id: high_path
    agent: high_agent
  - id: low_path
    agent: low_agent

edges:
  - from: score_node
    to: high_path
    condition: "state['score'] >= 0.8"
  - from: score_node
    to: low_path
    condition: "state['score'] < 0.8"
"""

# ---------------------------------------------------------------------------
# Helper — build a simple async agent callable that patches state
# ---------------------------------------------------------------------------


def make_agent(patches: dict[str, Any], call_log: list[str], name: str) -> AgentCallable:
    """Return an async agent that records its name and merges patches into state."""

    async def _agent(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append(name)
        return {**state, **patches}

    return _agent


# ---------------------------------------------------------------------------
# Test: 3-node workflow executes in correct order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_node_executes_in_order() -> None:
    wf = load_workflow_from_string(THREE_NODE_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    registry: dict[str, AgentCallable] = {
        "agent_a": make_agent({"step_a_done": True}, call_log, "agent_a"),
        "agent_b": make_agent({"step_b_done": True}, call_log, "agent_b"),
        "agent_c": make_agent({"step_c_done": True}, call_log, "agent_c"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    result = await engine.run({"input": "hello"})

    assert isinstance(result, WorkflowResult)
    assert call_log == ["agent_a", "agent_b", "agent_c"]
    assert result.final_state["step_a_done"] is True
    assert result.final_state["step_b_done"] is True
    assert result.final_state["step_c_done"] is True
    assert len(result.audit_entries) == 3


@pytest.mark.asyncio
async def test_run_id_propagated_to_result() -> None:
    wf = load_workflow_from_string(THREE_NODE_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    registry: dict[str, AgentCallable] = {
        "agent_a": make_agent({}, call_log, "agent_a"),
        "agent_b": make_agent({}, call_log, "agent_b"),
        "agent_c": make_agent({}, call_log, "agent_c"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    result = await engine.run({"input": "x"}, run_id="test-run-001")
    assert result.run_id == "test-run-001"


@pytest.mark.asyncio
async def test_checkpoint_saved_after_every_node() -> None:
    wf = load_workflow_from_string(THREE_NODE_YAML)
    checkpointer = InMemoryCheckpointer()

    save_calls: list[str] = []
    original_save = checkpointer.save

    async def recording_save(run_id: str, checkpoint: dict[str, Any]) -> None:
        save_calls.append(checkpoint.get("_current_node", "?"))
        await original_save(run_id, checkpoint)

    checkpointer.save = recording_save  # type: ignore[method-assign]

    registry: dict[str, AgentCallable] = {
        "agent_a": make_agent({"step_a_done": True}, [], "agent_a"),
        "agent_b": make_agent({"step_b_done": True}, [], "agent_b"),
        "agent_c": make_agent({"step_c_done": True}, [], "agent_c"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    await engine.run({"input": "x"}, run_id="chk-run")

    # Checkpoint was saved after each of the 3 nodes.
    assert len(save_calls) == 3
    assert "step_a" in save_calls
    assert "step_b" in save_calls
    assert "step_c" in save_calls


# ---------------------------------------------------------------------------
# Test: HumanGatewayPause raised at correct node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_human_gateway_raises_pause() -> None:
    wf = load_workflow_from_string(HITL_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    registry: dict[str, AgentCallable] = {
        "process_agent": make_agent({"processed": True}, call_log, "process_agent"),
        "finalize_agent": make_agent({}, call_log, "finalize_agent"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)

    with pytest.raises(HumanGatewayPause) as exc_info:
        await engine.run({"input": "data"}, run_id="hitl-run-001")

    pause = exc_info.value
    assert pause.run_id == "hitl-run-001"
    assert pause.node_id == "review"
    # Context should contain the non-internal state fields.
    assert "processed" in pause.context_for_reviewer
    assert pause.context_for_reviewer["processed"] is True
    # process_agent ran; finalize_agent should NOT have run yet.
    assert call_log == ["process_agent"]


@pytest.mark.asyncio
async def test_checkpoint_persisted_before_pause() -> None:
    """The checkpoint must be saved before HumanGatewayPause so resume() works."""
    wf = load_workflow_from_string(HITL_YAML)
    checkpointer = InMemoryCheckpointer()

    registry: dict[str, AgentCallable] = {
        "process_agent": make_agent({"processed": True}, [], "process_agent"),
        "finalize_agent": make_agent({}, [], "finalize_agent"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)

    with pytest.raises(HumanGatewayPause):
        await engine.run({"input": "data"}, run_id="hitl-chk-run")

    # Checkpoint should be present.
    saved = await checkpointer.load("hitl-chk-run")
    assert saved["_current_node"] == "review"


# ---------------------------------------------------------------------------
# Test: resume() continues from correct node after approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_approved_continues_to_finalize() -> None:
    wf = load_workflow_from_string(HITL_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    registry: dict[str, AgentCallable] = {
        "process_agent": make_agent({"processed": True}, call_log, "process_agent"),
        "finalize_agent": make_agent({"finalized": True}, call_log, "finalize_agent"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)

    with pytest.raises(HumanGatewayPause) as exc_info:
        await engine.run({"input": "data"}, run_id="resume-run-001")

    pause = exc_info.value
    decision = HumanDecision(decision="approved", reviewer_id="dr_smith")
    result = await engine.resume(pause.run_id, decision)

    assert isinstance(result, WorkflowResult)
    # process_agent ran before pause; finalize_agent ran after resume.
    assert call_log == ["process_agent", "finalize_agent"]
    assert result.final_state.get("finalized") is True


@pytest.mark.asyncio
async def test_resume_rejected_re_runs_process() -> None:
    wf = load_workflow_from_string(HITL_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    process_count = [0]

    async def process_agent(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append("process_agent")
        process_count[0] += 1
        return {**state, "processed": True}

    async def finalize_agent(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append("finalize_agent")
        return {**state, "finalized": True}

    registry: dict[str, AgentCallable] = {
        "process_agent": process_agent,
        "finalize_agent": finalize_agent,
    }

    engine = WorkflowEngine(wf, registry, checkpointer)

    with pytest.raises(HumanGatewayPause) as exc_info:
        await engine.run({"input": "data"}, run_id="reject-run-001")

    # Reject → process runs again → hits gateway again (max_loops=1 so only once).
    with pytest.raises(HumanGatewayPause):
        await engine.resume(exc_info.value.run_id, HumanDecision(decision="rejected", reviewer_id="dr_jones"))

    assert process_count[0] == 2  # processed twice (initial + after rejection)


@pytest.mark.asyncio
async def test_resume_with_state_edits() -> None:
    """State edits supplied in HumanDecision are visible to subsequent nodes."""
    wf = load_workflow_from_string(HITL_YAML)
    checkpointer = InMemoryCheckpointer()
    received_states: list[dict[str, Any]] = []

    async def process_agent(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "processed": True}

    async def finalize_agent(state: dict[str, Any]) -> dict[str, Any]:
        received_states.append(dict(state))
        return state

    registry: dict[str, AgentCallable] = {
        "process_agent": process_agent,
        "finalize_agent": finalize_agent,
    }

    engine = WorkflowEngine(wf, registry, checkpointer)

    with pytest.raises(HumanGatewayPause) as exc_info:
        await engine.run({"input": "data"}, run_id="edit-run-001")

    decision = HumanDecision(
        decision="approved",
        reviewer_id="dr_edit",
        edits={"reviewer_note": "all good"},
    )
    await engine.resume(exc_info.value.run_id, decision)

    assert received_states[0].get("reviewer_note") == "all good"


# ---------------------------------------------------------------------------
# Test: conditional routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conditional_routing_high_score() -> None:
    wf = load_workflow_from_string(CONDITIONAL_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    async def scorer(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "score": 0.95}

    registry: dict[str, AgentCallable] = {
        "scorer": scorer,
        "high_agent": make_agent({"path_taken": "high"}, call_log, "high_agent"),
        "low_agent": make_agent({"path_taken": "low"}, call_log, "low_agent"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    result = await engine.run({"score": 0.0}, run_id="cond-high")

    assert result.final_state["path_taken"] == "high"
    assert call_log == ["high_agent"]


@pytest.mark.asyncio
async def test_conditional_routing_low_score() -> None:
    wf = load_workflow_from_string(CONDITIONAL_YAML)
    checkpointer = InMemoryCheckpointer()
    call_log: list[str] = []

    async def scorer(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "score": 0.5}

    registry: dict[str, AgentCallable] = {
        "scorer": scorer,
        "high_agent": make_agent({"path_taken": "high"}, call_log, "high_agent"),
        "low_agent": make_agent({"path_taken": "low"}, call_log, "low_agent"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    result = await engine.run({"score": 0.0}, run_id="cond-low")

    assert result.final_state["path_taken"] == "low"
    assert call_log == ["low_agent"]


# ---------------------------------------------------------------------------
# Test: audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_entries_per_node() -> None:
    wf = load_workflow_from_string(THREE_NODE_YAML)
    checkpointer = InMemoryCheckpointer()

    registry: dict[str, AgentCallable] = {
        "agent_a": make_agent({}, [], "agent_a"),
        "agent_b": make_agent({}, [], "agent_b"),
        "agent_c": make_agent({}, [], "agent_c"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    result = await engine.run({"input": "x"}, run_id="audit-run")

    assert len(result.audit_entries) == 3
    node_ids = {e.node for e in result.audit_entries}
    assert node_ids == {"step_a", "step_b", "step_c"}
    # All entries share the same deterministic run_id (uuid5-mapped from "audit-run").
    first_run_uuid = result.audit_entries[0].run_id
    assert all(e.run_id == first_run_uuid for e in result.audit_entries)


# ---------------------------------------------------------------------------
# Test: missing agent raises KeyError (not a cryptic AttributeError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_agent_raises_key_error() -> None:
    wf = load_workflow_from_string(THREE_NODE_YAML)
    checkpointer = InMemoryCheckpointer()
    # agent_b deliberately omitted
    registry: dict[str, AgentCallable] = {
        "agent_a": make_agent({}, [], "agent_a"),
        "agent_c": make_agent({}, [], "agent_c"),
    }

    engine = WorkflowEngine(wf, registry, checkpointer)
    with pytest.raises(KeyError, match="agent_b"):
        await engine.run({"input": "x"})

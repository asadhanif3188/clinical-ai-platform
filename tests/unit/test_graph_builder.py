"""Unit tests for the ClinFlow LangGraph graph builder and safe condition evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from clinical_ai_clinflow.graph import (
    SecurityError,
    build_graph,
    evaluate_condition,
)
from clinical_ai_clinflow.loader import load_workflow, load_workflow_from_string

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "packages"
    / "clinflow"
    / "src"
    / "clinical_ai_clinflow"
    / "workflows"
    / "_template.yml"
)

# ---------------------------------------------------------------------------
# Minimal workflow YAML fixtures
# ---------------------------------------------------------------------------

SIMPLE_YAML = """\
name: simple
version: "1.0"
state_schema:
  value: str
  alpha_done: bool | null
  beta_done: bool | null

nodes:
  - id: alpha
    agent: agent_alpha
  - id: beta
    agent: agent_beta

edges:
  - from: alpha
    to: beta
  - from: beta
    to: END
"""

CONDITIONAL_YAML = """\
name: conditional
version: "1.0"
state_schema:
  score: float
  route: str | null
  _scorer_done: bool | null

nodes:
  - id: score_node
    agent: scorer
  - id: high_node
    agent: high_handler
  - id: low_node
    agent: low_handler

edges:
  - from: score_node
    to: high_node
    condition: "state['score'] >= 0.8"
  - from: score_node
    to: low_node
    condition: "state['score'] < 0.8"
"""

HITL_YAML = """\
name: hitl
version: "1.0"
state_schema:
  data: str
  done: bool | null

nodes:
  - id: prepare
    agent: prepare_agent
  - id: review
    type: human_gateway
    notification:
      channel: slack
      message: "needs review"
  - id: finish
    agent: finish_agent

edges:
  - from: prepare
    to: review
  - from: review
    to: finish
    condition: "approved"
"""

# ---------------------------------------------------------------------------
# Dummy agent factories
# ---------------------------------------------------------------------------


def noop_agent(name: str) -> Any:
    async def _agent(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, f"_{name}_done": True}

    return _agent


# ---------------------------------------------------------------------------
# build_graph tests
# ---------------------------------------------------------------------------


def test_template_builds_compiled_graph() -> None:
    """_template.yml must compile to a CompiledStateGraph without error."""
    assert TEMPLATE_PATH.exists(), f"Template not found at {TEMPLATE_PATH}"
    wf = load_workflow(TEMPLATE_PATH)

    registry = {
        "intake_agent": noop_agent("intake"),
        "extraction_agent": noop_agent("extraction"),
        "validation_agent": noop_agent("validation"),
        "report_agent": noop_agent("report"),
    }
    checkpointer = MemorySaver()
    graph = build_graph(wf, registry, checkpointer)
    assert isinstance(graph, CompiledStateGraph)


def test_simple_workflow_builds_graph() -> None:
    wf = load_workflow_from_string(SIMPLE_YAML)
    registry = {
        "agent_alpha": noop_agent("alpha"),
        "agent_beta": noop_agent("beta"),
    }
    graph = build_graph(wf, registry, MemorySaver())
    assert isinstance(graph, CompiledStateGraph)


def test_conditional_workflow_builds_graph() -> None:
    wf = load_workflow_from_string(CONDITIONAL_YAML)
    registry = {
        "scorer": noop_agent("scorer"),
        "high_handler": noop_agent("high"),
        "low_handler": noop_agent("low"),
    }
    graph = build_graph(wf, registry, MemorySaver())
    assert isinstance(graph, CompiledStateGraph)


def test_hitl_workflow_sets_interrupt_before() -> None:
    """human_gateway nodes must be listed in interrupt_before on the compiled graph."""
    wf = load_workflow_from_string(HITL_YAML)
    registry = {
        "prepare_agent": noop_agent("prepare"),
        "finish_agent": noop_agent("finish"),
    }
    graph = build_graph(wf, registry, MemorySaver())
    assert isinstance(graph, CompiledStateGraph)
    # LangGraph exposes the interrupt nodes via interrupt_before_nodes attribute.
    assert "review" in graph.interrupt_before_nodes


def test_missing_agent_raises_key_error() -> None:
    wf = load_workflow_from_string(SIMPLE_YAML)
    registry = {"agent_alpha": noop_agent("alpha")}  # agent_beta missing

    with pytest.raises(KeyError, match="agent_beta"):
        build_graph(wf, registry, MemorySaver())


# ---------------------------------------------------------------------------
# evaluate_condition — happy-path tests
# ---------------------------------------------------------------------------


def test_condition_simple_equality() -> None:
    assert evaluate_condition("state['x'] == 'hello'", {"x": "hello"}) is True
    assert evaluate_condition("state['x'] == 'hello'", {"x": "world"}) is False


def test_condition_numeric_comparison() -> None:
    assert evaluate_condition("state['score'] >= 0.8", {"score": 0.9}) is True
    assert evaluate_condition("state['score'] >= 0.8", {"score": 0.5}) is False


def test_condition_boolean_and() -> None:
    state = {"a": True, "b": True}
    assert evaluate_condition("state['a'] and state['b']", state) is True
    state2 = {"a": True, "b": False}
    assert evaluate_condition("state['a'] and state['b']", state2) is False


def test_condition_boolean_or() -> None:
    state = {"a": False, "b": True}
    assert evaluate_condition("state['a'] or state['b']", state) is True


def test_condition_not() -> None:
    assert evaluate_condition("not state['flag']", {"flag": False}) is True
    assert evaluate_condition("not state['flag']", {"flag": True}) is False


def test_condition_approved_sentinel() -> None:
    assert evaluate_condition("approved", {}, approved=True) is True
    assert evaluate_condition("approved", {}, approved=False) is False


def test_condition_rejected_sentinel() -> None:
    assert evaluate_condition("rejected", {}, rejected=True) is True
    assert evaluate_condition("rejected", {}, rejected=False) is False


def test_condition_attribute_access() -> None:
    class Obj:
        confidence = 0.95

    assert evaluate_condition("state['obj'].confidence > 0.9", {"obj": Obj()}) is True


def test_condition_nested_subscript() -> None:
    state = {"result": {"status": "PASS"}}
    assert evaluate_condition("state['result']['status'] == 'PASS'", state) is True


def test_condition_arithmetic() -> None:
    assert evaluate_condition("state['a'] + state['b'] > 5", {"a": 3, "b": 4}) is True


def test_condition_literal_true() -> None:
    assert evaluate_condition("True", {}) is True


def test_condition_literal_false() -> None:
    assert evaluate_condition("False", {}) is False


# ---------------------------------------------------------------------------
# evaluate_condition — security tests
# ---------------------------------------------------------------------------


def test_condition_rejects_function_call() -> None:
    with pytest.raises(SecurityError):
        evaluate_condition("__import__('os')", {})


def test_condition_rejects_builtin_call() -> None:
    with pytest.raises(SecurityError):
        evaluate_condition("len(state)", {"state": {}})


def test_condition_rejects_lambda() -> None:
    with pytest.raises(SecurityError):
        evaluate_condition("(lambda: True)()", {})


def test_condition_rejects_list_comprehension() -> None:
    with pytest.raises(SecurityError):
        evaluate_condition("[x for x in range(10)]", {})


def test_condition_rejects_walrus_operator() -> None:
    with pytest.raises(SecurityError):
        evaluate_condition("(x := 5) == 5", {})


def test_condition_rejects_attribute_dunder() -> None:
    """Accessing __class__ etc. would allow type escapes — should be prevented."""
    # The evaluator allows attribute access syntactically, but dunder access on
    # the state dict itself would just return the dict's class methods. The real
    # guard is that we never pass builtins into the eval context.
    # This test ensures calls cannot be made even if an attribute is retrieved.
    with pytest.raises(SecurityError):
        # Calling the result of attribute access is a Call node — blocked.
        evaluate_condition("state.__class__()", {})


def test_condition_rejects_exec() -> None:
    with pytest.raises(SecurityError):
        evaluate_condition("exec('import os')", {})


def test_condition_rejects_semicolon_multiple_statements() -> None:
    """ast.parse in 'eval' mode already rejects multiple statements."""
    with pytest.raises(SyntaxError):
        evaluate_condition("True; False", {})


# ---------------------------------------------------------------------------
# end-to-end graph execution test (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simple_graph_runs_end_to_end() -> None:
    """The compiled graph should execute both nodes and return final state."""
    wf = load_workflow_from_string(SIMPLE_YAML)
    call_log: list[str] = []

    async def alpha(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append("alpha")
        return {**state, "alpha_done": True}

    async def beta(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append("beta")
        return {**state, "beta_done": True}

    registry = {"agent_alpha": alpha, "agent_beta": beta}
    graph = build_graph(wf, registry, MemorySaver())

    initial = {"value": "test", "alpha_done": None, "beta_done": None}
    result = await graph.ainvoke(initial, config={"configurable": {"thread_id": "t1"}})

    assert call_log == ["alpha", "beta"]
    assert result.get("alpha_done") is True
    assert result.get("beta_done") is True


@pytest.mark.asyncio
async def test_conditional_graph_routes_correctly() -> None:
    wf = load_workflow_from_string(CONDITIONAL_YAML)
    call_log: list[str] = []

    async def scorer(state: dict[str, Any]) -> dict[str, Any]:
        return state  # score is already in initial state

    async def high_handler(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append("high")
        return {**state, "route": "high"}

    async def low_handler(state: dict[str, Any]) -> dict[str, Any]:
        call_log.append("low")
        return {**state, "route": "low"}

    registry = {
        "scorer": scorer,
        "high_handler": high_handler,
        "low_handler": low_handler,
    }
    graph = build_graph(wf, registry, MemorySaver())

    result_high = await graph.ainvoke(
        {"score": 0.95, "route": None},
        config={"configurable": {"thread_id": "t-high"}},
    )
    result_low = await graph.ainvoke(
        {"score": 0.4, "route": None},
        config={"configurable": {"thread_id": "t-low"}},
    )

    assert result_high.get("route") == "high"
    assert result_low.get("route") == "low"
    assert call_log == ["high", "low"]

"""Unit tests for WorkflowAnalytics.

Coverage:
- get_workflow_stats(): correct aggregation of run counts, ratios, per-node
  average durations, and bottleneck detection.
- get_workflow_stats(): zero-runs edge case returns zero ratios without
  division-by-zero errors.
- get_cost_summary(): correct summation of tokens and cost_usd.
- get_cost_summary(): run with no entries returns zeroed dict.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clinical_ai_clinflow.analytics import WorkflowAnalytics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory(execute_side_effects: list[Any]) -> MagicMock:
    """Build a minimal async_sessionmaker mock.

    *execute_side_effects* is consumed in order: each element is returned by
    a successive call to ``session.execute()``.
    """
    execute_mock = AsyncMock(side_effect=execute_side_effects)

    session_mock = AsyncMock()
    session_mock.execute = execute_mock

    factory = MagicMock()

    @asynccontextmanager  # type: ignore[misc]
    async def _ctx() -> Any:
        yield session_mock

    factory.return_value = _ctx()
    factory.side_effect = lambda: _ctx()
    return factory


def _scalars_result(*values: Any) -> MagicMock:
    """Simulate the return value of session.execute() for scalar column results."""
    result = MagicMock()
    result.all.return_value = list(values)
    return result


def _scalar_one_result(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _one_result(**kwargs: Any) -> MagicMock:
    result = MagicMock()
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    result.one.return_value = row
    return result


def _status_row(status: str, cnt: int) -> MagicMock:
    row = MagicMock()
    row.status = status
    row.cnt = cnt
    return row


def _node_row(node: str, avg_ms: float) -> MagicMock:
    row = MagicMock()
    row.node = node
    row.avg_ms = avg_ms
    return row


# ---------------------------------------------------------------------------
# get_workflow_stats — normal case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workflow_stats_aggregates_correctly() -> None:
    """Ratios, counts, per-node averages, and slowest node are correct."""
    run_id_1 = uuid.uuid4()
    run_id_2 = uuid.uuid4()

    # Query 1: run status counts  [success×35, failed×5]
    status_result = _scalars_result(
        _status_row("success", 35),
        _status_row("failed", 5),
    )
    # Query 2: human-review count  (2 distinct run_ids had human_decision set)
    human_review_result = _scalar_one_result(2)
    # Query 3: per-node avg duration  (extract slowest, classify faster)
    node_result = _scalars_result(
        _node_row("extract", 1200.0),
        _node_row("classify", 820.5),
    )

    factory = _make_session_factory([status_result, human_review_result, node_result])
    analytics = WorkflowAnalytics(factory)

    stats = await analytics.get_workflow_stats("patient_intake")

    assert stats["workflow_name"] == "patient_intake"
    assert stats["total_runs"] == 40
    assert stats["success_count"] == 35
    assert stats["failure_count"] == 5
    assert stats["human_review_count"] == 2

    assert pytest.approx(stats["success_ratio"], rel=1e-6) == 35 / 40
    assert pytest.approx(stats["failure_ratio"], rel=1e-6) == 5 / 40
    assert pytest.approx(stats["human_review_ratio"], rel=1e-6) == 2 / 40

    assert stats["avg_duration_ms_by_node"] == {"extract": 1200.0, "classify": 820.5}
    assert stats["slowest_node"] == "extract"
    assert pytest.approx(stats["slowest_node_avg_ms"]) == 1200.0


# ---------------------------------------------------------------------------
# get_workflow_stats — bottleneck detection with multiple nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workflow_stats_identifies_slowest_node() -> None:
    """The slowest_node key must point to the node with the highest avg_ms."""
    status_result = _scalars_result(_status_row("success", 10))
    human_review_result = _scalar_one_result(0)
    node_result = _scalars_result(
        _node_row("validate", 3000.0),  # slowest
        _node_row("report", 500.0),
        _node_row("classify", 200.0),
    )

    factory = _make_session_factory([status_result, human_review_result, node_result])
    analytics = WorkflowAnalytics(factory)

    stats = await analytics.get_workflow_stats("drug_check")

    assert stats["slowest_node"] == "validate"
    assert stats["slowest_node_avg_ms"] == 3000.0


# ---------------------------------------------------------------------------
# get_workflow_stats — zero runs (no data for workflow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workflow_stats_zero_runs_no_division_error() -> None:
    """When there are no runs, all ratios must be 0.0 (not ZeroDivisionError)."""
    status_result = _scalars_result()  # empty — no runs
    human_review_result = _scalar_one_result(0)
    node_result = _scalars_result()  # no audit entries either

    factory = _make_session_factory([status_result, human_review_result, node_result])
    analytics = WorkflowAnalytics(factory)

    stats = await analytics.get_workflow_stats("new_workflow")

    assert stats["total_runs"] == 0
    assert stats["success_ratio"] == 0.0
    assert stats["failure_ratio"] == 0.0
    assert stats["human_review_ratio"] == 0.0
    assert stats["slowest_node"] is None
    assert stats["slowest_node_avg_ms"] == 0.0
    assert stats["avg_duration_ms_by_node"] == {}


# ---------------------------------------------------------------------------
# get_cost_summary — normal case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cost_summary_sums_tokens_and_cost() -> None:
    """Total tokens and cost_usd are summed correctly across audit entries."""
    run_id = uuid.uuid4()
    cost_result = _one_result(total_tokens=4200, total_cost_usd=0.0042, entry_count=6)

    factory = _make_session_factory([cost_result])
    analytics = WorkflowAnalytics(factory)

    summary = await analytics.get_cost_summary(run_id)

    assert summary["run_id"] == str(run_id)
    assert summary["total_tokens"] == 4200
    assert pytest.approx(summary["total_cost_usd"], rel=1e-9) == 0.0042
    assert summary["entry_count"] == 6


# ---------------------------------------------------------------------------
# get_cost_summary — run with no entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cost_summary_no_entries_returns_zeros() -> None:
    """When no audit entries exist for a run, totals must be 0, not None."""
    run_id = uuid.uuid4()
    cost_result = _one_result(total_tokens=None, total_cost_usd=None, entry_count=0)

    factory = _make_session_factory([cost_result])
    analytics = WorkflowAnalytics(factory)

    summary = await analytics.get_cost_summary(run_id)

    assert summary["total_tokens"] == 0
    assert summary["total_cost_usd"] == 0.0
    assert summary["entry_count"] == 0


# ---------------------------------------------------------------------------
# get_cost_summary — accepts string run_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cost_summary_accepts_string_run_id() -> None:
    """get_cost_summary() must accept a plain string UUID without raising."""
    run_id = str(uuid.uuid4())
    cost_result = _one_result(total_tokens=100, total_cost_usd=0.001, entry_count=1)

    factory = _make_session_factory([cost_result])
    analytics = WorkflowAnalytics(factory)

    summary = await analytics.get_cost_summary(run_id)

    assert summary["run_id"] == run_id
    assert summary["total_tokens"] == 100

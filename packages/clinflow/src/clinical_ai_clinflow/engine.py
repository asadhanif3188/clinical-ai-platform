"""ClinFlow workflow execution engine.

Executes YAML-defined workflows by walking nodes in topological order,
dispatching to registered agent callables, evaluating edge conditions,
persisting checkpoints, and writing an immutable audit trail.

The engine is deliberately agent-agnostic: it knows nothing about specific
clinical or pharma agents. Everything domain-specific lives in the
agent_registry supplied at construction time.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Protocol
import uuid
from uuid import UUID, uuid4

from clinical_ai_shared.schemas.audit import AuditLogEntry
from clinical_ai_clinflow.definitions import EdgeDefinition, NodeDefinition, WorkflowDefinition

# ---------------------------------------------------------------------------
# Public dataclasses / exceptions
# ---------------------------------------------------------------------------

# Type alias — agents receive and return a plain state dict.
AgentCallable = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]


@dataclass
class WorkflowResult:
    """Returned when a workflow runs to completion (no pending HITL gate)."""

    run_id: str
    final_state: dict[str, Any]
    audit_entries: list[AuditLogEntry]
    total_cost_usd: float
    duration_ms: int


@dataclass
class HumanDecision:
    """Carries the result of a human reviewer's decision at a gateway node."""

    decision: str  # "approved" | "rejected"
    reviewer_id: str
    # Optional state overrides applied before resuming — lets reviewers patch fields.
    edits: dict[str, Any] = field(default_factory=dict)


class HumanGatewayPause(Exception):
    """Raised when execution reaches a human_gateway node.

    Callers must persist run_id and later call WorkflowEngine.resume() with a
    HumanDecision to continue.
    """

    def __init__(self, run_id: str, node_id: str, context_for_reviewer: dict[str, Any]) -> None:
        super().__init__(f"Workflow {run_id} paused at human gateway '{node_id}'")
        self.run_id = run_id
        self.node_id = node_id
        self.context_for_reviewer = context_for_reviewer


# ---------------------------------------------------------------------------
# Checkpointer protocol — injected at construction time
# ---------------------------------------------------------------------------


class CheckpointerProtocol(Protocol):
    """Minimal interface the engine needs from a checkpointer."""

    async def save(self, run_id: str, checkpoint: dict[str, Any]) -> None: ...

    async def load(self, run_id: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SENTINEL_END = "END"


def _hash_state(state: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hex digest of the state dict."""
    serialized = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _eval_condition(condition: str | None, state: dict[str, Any], decision: str | None) -> bool:
    """Evaluate an edge condition string against the current state.

    The expression has access to:
      - ``state`` — the current workflow state dict
      - ``approved`` / ``rejected`` — bool shortcuts for human-gateway edges

    Conditions like ``"state['confidence'] > 0.9"`` or ``"approved"`` are
    supported.  Bare boolean literals (``None`` condition) always resolve True.
    """
    if condition is None:
        return True

    local_vars: dict[str, Any] = {
        "state": state,
        "approved": decision == "approved",
        "rejected": decision == "rejected",
    }
    try:
        # Using eval is intentional here — conditions are author-supplied YAML
        # workflow logic, not end-user input.  Production deployments should
        # further restrict the namespace if untrusted workflow authors are a
        # concern.
        result = eval(condition, {"__builtins__": {}}, local_vars)  # noqa: S307
    except Exception:
        # A malformed condition never fires, preserving fail-safe routing.
        return False
    return bool(result)


def _route(
    edges: list[EdgeDefinition],
    from_node: str,
    state: dict[str, Any],
    decision: str | None,
    loop_counts: dict[str, int],
) -> str | None:
    """Return the next node ID by evaluating outgoing edges from *from_node*.

    Returns ``None`` when no matching edge is found (treated as implicit END).
    Respects ``max_loops`` per edge by tracking a counter keyed on
    ``"{from_node}->{to_node}"``.
    """
    candidates = [e for e in edges if e.from_node == from_node]
    for edge in candidates:
        if not _eval_condition(edge.condition, state, decision):
            continue
        loop_key = f"{edge.from_node}->{edge.to_node}"
        current = loop_counts.get(loop_key, 0)
        if current >= edge.max_loops and edge.max_loops > 0:
            continue  # Safety cap exceeded — skip this edge
        loop_counts[loop_key] = current + 1
        return edge.to_node
    return None


# ---------------------------------------------------------------------------
# WorkflowEngine
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Executes a YAML-defined workflow.

    Args:
        workflow_def: Parsed and validated WorkflowDefinition.
        agent_registry: Maps agent name → async callable ``(state) → state``.
        checkpointer: Object implementing CheckpointerProtocol.
    """

    def __init__(
        self,
        workflow_def: WorkflowDefinition,
        agent_registry: dict[str, AgentCallable],
        checkpointer: CheckpointerProtocol,
    ) -> None:
        self._workflow = workflow_def
        self._agents = agent_registry
        self._checkpointer = checkpointer
        # Build a fast node lookup by id.
        self._nodes: dict[str, NodeDefinition] = {n.id: n for n in workflow_def.nodes}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        initial_state: dict[str, Any],
        run_id: str | None = None,
    ) -> WorkflowResult:
        """Execute the workflow from its entry node.

        Args:
            initial_state: Initial state dict passed to the first node.
            run_id: Optional caller-supplied run identifier (UUID string).
                    A new UUID is generated if not provided.

        Returns:
            WorkflowResult on successful completion.

        Raises:
            HumanGatewayPause: When a human_gateway node is reached.
                               Callers should persist *run_id* and call
                               ``resume()`` when the decision is available.
        """
        effective_run_id = run_id or str(uuid4())
        start_ms = int(time.monotonic() * 1000)

        # Entry node is the first node with no incoming edges.
        entry_node_id = self._find_entry_node()

        exec_state: dict[str, Any] = {
            "_run_id": effective_run_id,
            "_current_node": entry_node_id,
            "_loop_counts": {},
            "_audit_entries": [],
            "_total_cost_usd": 0.0,
            **initial_state,
        }

        return await self._execute_from(exec_state, start_ms, human_decision=None)

    async def resume(
        self,
        run_id: str,
        decision: HumanDecision,
    ) -> WorkflowResult:
        """Resume a paused workflow after a human gateway decision.

        Args:
            run_id: The run_id that was raised in HumanGatewayPause.
            decision: HumanDecision with "approved"/"rejected" and optional edits.

        Returns:
            WorkflowResult on successful completion.

        Raises:
            HumanGatewayPause: If the resumed workflow reaches another gateway.
            KeyError: If *run_id* is not found in the checkpointer.
        """
        checkpoint = await self._checkpointer.load(run_id)
        state = dict(checkpoint)

        # Apply reviewer edits to the state (excluding internal _ keys).
        for k, v in decision.edits.items():
            if not k.startswith("_"):
                state[k] = v

        # Record the human decision in the audit trail.
        gateway_node_id: str = state.get("_current_node", "unknown")
        audit_entry = _build_audit_entry(
            run_id=run_id,
            node_id=gateway_node_id,
            agent="human_gateway",
            input_hash=_hash_state(state),
            output_summary=f"Human decision: {decision.decision} by {decision.reviewer_id}",
            human_decision=decision.decision,
            human_reviewer=decision.reviewer_id,
        )
        state.setdefault("_audit_entries", [])
        state["_audit_entries"].append(audit_entry)

        # Route past the gateway using the human decision as the condition flag.
        loop_counts: dict[str, int] = state.get("_loop_counts", {})
        next_node_id = _route(
            self._workflow.edges,
            gateway_node_id,
            state,
            decision.decision,
            loop_counts,
        )
        state["_loop_counts"] = loop_counts
        state["_current_node"] = next_node_id or _SENTINEL_END

        if next_node_id is None or next_node_id == _SENTINEL_END:
            return _build_result(state)

        state["_current_node"] = next_node_id
        start_ms = int(time.monotonic() * 1000)
        return await self._execute_from(state, start_ms, human_decision=decision.decision)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_entry_node(self) -> str:
        """Return the ID of the node with no incoming edges."""
        nodes_with_incoming = {e.to_node for e in self._workflow.edges if e.to_node != _SENTINEL_END}
        for node in self._workflow.nodes:
            if node.id not in nodes_with_incoming:
                return node.id
        # Fallback — every node has incoming edges; just use the first one.
        return self._workflow.nodes[0].id

    async def _execute_from(
        self,
        state: dict[str, Any],
        start_ms: int,
        human_decision: str | None,
    ) -> WorkflowResult:
        """Walk the graph from state['_current_node'] until END or a gateway."""
        run_id: str = state["_run_id"]
        current_node_id: str = state["_current_node"]
        loop_counts: dict[str, int] = state.setdefault("_loop_counts", {})

        while current_node_id != _SENTINEL_END:
            node = self._nodes[current_node_id]

            if node.type == "human_gateway":
                # Persist before raising so resume() can load the checkpoint.
                state["_current_node"] = current_node_id
                await self._checkpointer.save(run_id, state)
                raise HumanGatewayPause(
                    run_id=run_id,
                    node_id=current_node_id,
                    context_for_reviewer={
                        k: v for k, v in state.items() if not k.startswith("_")
                    },
                )

            # --- Execute agent node ---
            node_start = int(time.monotonic() * 1000)
            input_hash = _hash_state(state)

            new_state = await self._run_node_with_retry(node, state)
            state.update(new_state)

            duration_ms = int(time.monotonic() * 1000) - node_start
            cost = float(state.pop("_node_cost_usd", 0.0))
            model = str(state.pop("_node_model_used", ""))

            audit_entry = _build_audit_entry(
                run_id=run_id,
                node_id=current_node_id,
                agent=node.agent or current_node_id,
                input_hash=input_hash,
                output_summary=state.get("_node_output_summary", f"Node {current_node_id} completed"),
                cost_usd=cost,
                duration_ms=duration_ms,
                model_used=model or None,
            )
            state.pop("_node_output_summary", None)
            state.setdefault("_audit_entries", []).append(audit_entry)
            state["_total_cost_usd"] = float(state.get("_total_cost_usd", 0.0)) + cost

            # Persist checkpoint after every node.
            state["_current_node"] = current_node_id
            await self._checkpointer.save(run_id, dict(state))

            # Route to next node.
            next_id = _route(
                self._workflow.edges, current_node_id, state, human_decision, loop_counts
            )
            state["_loop_counts"] = loop_counts
            current_node_id = next_id or _SENTINEL_END

        state["_current_node"] = _SENTINEL_END
        elapsed = int(time.monotonic() * 1000) - start_ms
        return _build_result(state, total_duration_ms=elapsed)

    async def _run_node_with_retry(
        self,
        node: NodeDefinition,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Call the agent for *node*, retrying on failure per node.retry config."""
        agent_name = node.agent  # guaranteed non-None for agent nodes by validator
        assert agent_name is not None  # for mypy
        agent_fn = self._agents.get(agent_name)
        if agent_fn is None:
            raise KeyError(
                f"Agent '{agent_name}' (node '{node.id}') not found in agent_registry. "
                f"Available: {sorted(self._agents.keys())}"
            )

        retry = node.retry
        max_attempts = retry.max_attempts if retry else 1
        backoff = retry.backoff_seconds if retry else 0
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return await agent_fn(dict(state))
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts - 1 and backoff > 0:
                    await asyncio.sleep(backoff)

        raise RuntimeError(
            f"Node '{node.id}' failed after {max_attempts} attempt(s)"
        ) from last_exc


# ---------------------------------------------------------------------------
# Private factory helpers
# ---------------------------------------------------------------------------


def _build_audit_entry(
    *,
    run_id: str,
    node_id: str,
    agent: str,
    input_hash: str,
    output_summary: str,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    model_used: str | None = None,
    human_decision: str | None = None,
    human_reviewer: str | None = None,
) -> AuditLogEntry:
    # Coerce run_id to UUID — use uuid5 for non-UUID strings so the mapping
    # stays deterministic (callers may supply readable IDs like "test-run-001").
    try:
        uuid_run_id = UUID(run_id)
    except ValueError:
        uuid_run_id = uuid.uuid5(uuid.NAMESPACE_DNS, run_id)

    return AuditLogEntry(
        entry_id=uuid4(),
        run_id=uuid_run_id,
        agent=agent,
        node=node_id,
        input_hash=input_hash,
        output_summary=output_summary,
        model_used=model_used,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        human_decision=human_decision,
        human_reviewer=human_reviewer,
    )


def _build_result(
    state: dict[str, Any],
    total_duration_ms: int = 0,
) -> WorkflowResult:
    audit_entries: list[AuditLogEntry] = state.pop("_audit_entries", [])
    total_cost = float(state.pop("_total_cost_usd", 0.0))
    state.pop("_current_node", None)
    state.pop("_loop_counts", None)
    run_id: str = state.pop("_run_id", str(uuid4()))

    return WorkflowResult(
        run_id=run_id,
        final_state=state,
        audit_entries=audit_entries,
        total_cost_usd=total_cost,
        duration_ms=total_duration_ms,
    )

"""Convert a ClinFlow WorkflowDefinition into a runnable LangGraph StateGraph.

The two public API surfaces are:

  build_graph(workflow_def, agent_registry, checkpointer) -> CompiledStateGraph
  evaluate_condition(expr, state)                         -> bool
  class SecurityError(ValueError)

Design notes
------------
* The dynamic TypedDict is built at runtime from the workflow's state_schema
  because LangGraph requires a concrete TypedDict for static/runtime typing.
  mypy cannot check the contents of a runtime-created TypedDict, but it can
  still type-check everything around it.

* Conditions use a whitelist AST evaluator — no eval(), no exec().
  Only a safe subset of Python expressions is allowed:
  comparisons, boolean ops, arithmetic, attribute/subscript access, literals,
  and the two gateway sentinels ``approved``/``rejected``.
  Anything else (calls, imports, comprehensions …) raises SecurityError.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable, Coroutine
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from clinical_ai_clinflow.definitions import WorkflowDefinition

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

AgentFn = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]

# ---------------------------------------------------------------------------
# Safe condition evaluator
# ---------------------------------------------------------------------------

_SAFE_OPERATORS: dict[type, Any] = {
    # Comparisons
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    # Boolean
    ast.And: operator.and_,
    ast.Or: operator.or_,
    ast.Not: operator.not_,
    # Arithmetic
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}

# Whitelist of AST node types that the evaluator will descend into.
# Everything NOT in this set raises SecurityError immediately.
_ALLOWED_NODE_TYPES = frozenset(
    {
        ast.Expression,
        ast.BoolOp,
        ast.Compare,
        ast.BinOp,
        ast.UnaryOp,
        ast.Attribute,
        ast.Subscript,
        ast.Index,   # Python <3.9 compat (removed in 3.9 AST but harmless to include)
        ast.Name,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Load,
        # Slice is used in subscript — e.g. state['key']
        ast.Slice,
        # Comparison operators — these are child nodes of ast.Compare
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.In, ast.NotIn, ast.Is, ast.IsNot,
        # Boolean operators — children of ast.BoolOp
        ast.And, ast.Or,
        # Unary operators — children of ast.UnaryOp
        ast.Not, ast.USub, ast.UAdd, ast.Invert,
        # Binary operators — children of ast.BinOp
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
        ast.FloorDiv, ast.Pow,
    }
)


class SecurityError(ValueError):
    """Raised when a workflow condition contains a disallowed expression."""


def _check_ast(node: ast.AST) -> None:
    """Walk *node* and raise SecurityError on any disallowed construct."""
    if type(node) not in _ALLOWED_NODE_TYPES:
        raise SecurityError(
            f"Condition contains disallowed expression type '{type(node).__name__}'. "
            "Only comparisons, boolean ops, attribute access, subscripts, and "
            "literals are allowed in workflow conditions."
        )
    for child in ast.iter_child_nodes(node):
        _check_ast(child)


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    """Recursively evaluate a safe AST node against *ctx*."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, ctx)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        try:
            return ctx[node.id]
        except KeyError:
            raise NameError(f"Name '{node.id}' is not defined in the condition context.")

    if isinstance(node, ast.Attribute):
        obj = _eval_node(node.value, ctx)
        return getattr(obj, node.attr)

    if isinstance(node, ast.Subscript):
        obj = _eval_node(node.value, ctx)
        # ast.Subscript.slice is the key expression in Python 3.9+.
        key = _eval_node(node.slice, ctx)
        return obj[key]

    if isinstance(node, ast.Index):  # Python <3.9 compatibility
        return _eval_node(node.value, ctx)  # type: ignore[attr-defined]

    if isinstance(node, ast.List):
        return [_eval_node(el, ctx) for el in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(el, ctx) for el in node.elts)

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, ctx) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, ctx)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator_node in zip(node.ops, node.comparators):
            right = _eval_node(comparator_node, ctx)
            op_fn = _SAFE_OPERATORS.get(type(op))
            if op_fn is None:
                raise SecurityError(f"Unsupported comparison operator: {type(op).__name__}")
            if not op_fn(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, ctx)
        right = _eval_node(node.right, ctx)
        op_fn = _SAFE_OPERATORS.get(type(node.op))
        if op_fn is None:
            raise SecurityError(f"Unsupported binary operator: {type(node.op).__name__}")
        return op_fn(left, right)

    raise SecurityError(f"Unexpected AST node type in condition: {type(node).__name__}")


def evaluate_condition(
    expr: str,
    state: dict[str, Any],
    *,
    approved: bool = False,
    rejected: bool = False,
) -> bool:
    """Safely evaluate a workflow edge condition string.

    The expression has access to:
    - ``state``    — the current workflow state dict
    - ``approved`` — True when a human gateway was approved
    - ``rejected`` — True when a human gateway was rejected

    Args:
        expr: Python expression string from the workflow YAML.
        state: Current workflow state.
        approved: Set True when routing from an approved gateway.
        rejected: Set True when routing from a rejected gateway.

    Returns:
        Boolean result of the expression.

    Raises:
        SecurityError: If the expression contains disallowed constructs.
    """
    tree = ast.parse(expr, mode="eval")
    _check_ast(tree)

    ctx: dict[str, Any] = {
        "state": state,
        "approved": approved,
        "rejected": rejected,
    }
    result = _eval_node(tree, ctx)
    return bool(result)


# ---------------------------------------------------------------------------
# Dynamic TypedDict builder
# ---------------------------------------------------------------------------

# Map of type_hint string fragments → Python types used for the TypedDict.
_HINT_TO_TYPE: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
}


def _python_type(type_hint: str) -> type:
    """Return a best-effort Python type for a state field type hint string.

    All nullable / Union types resolve to ``object`` (Any-equivalent) because
    the runtime TypedDict is used only for LangGraph structural purposes and
    is not type-checked at runtime.
    """
    if "null" in type_hint or "|" in type_hint:
        return object  # equivalent to Any for our purposes
    return _HINT_TO_TYPE.get(type_hint.strip(), object)


def _build_typed_dict(workflow_def: WorkflowDefinition) -> type:
    """Construct a TypedDict class at runtime from the workflow state_schema."""
    annotations: dict[str, type] = {
        field.name: _python_type(field.type_hint) for field in workflow_def.state_schema
    }
    # type() signature: (name, bases, namespace)
    # __annotations__ is what makes this a proper TypedDict from LangGraph's PoV.
    return type(
        f"{workflow_def.name.title().replace('_', '')}State",
        (dict,),
        {"__annotations__": annotations},
    )


# ---------------------------------------------------------------------------
# Entry-point finder
# ---------------------------------------------------------------------------

_SENTINEL_END = "END"


def _find_entry_node(workflow_def: WorkflowDefinition) -> str:
    nodes_with_incoming = {
        e.to_node for e in workflow_def.edges if e.to_node != _SENTINEL_END
    }
    for node in workflow_def.nodes:
        if node.id not in nodes_with_incoming:
            return node.id
    return workflow_def.nodes[0].id


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------


def build_graph(
    workflow_def: WorkflowDefinition,
    agent_registry: dict[str, AgentFn],
    checkpointer: Any,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Convert a WorkflowDefinition into a compiled LangGraph StateGraph.

    Args:
        workflow_def: Parsed and validated workflow definition.
        agent_registry: Maps agent name → async callable ``(state) → state``.
        checkpointer: Any LangGraph-compatible checkpointer
                      (MemorySaver, AsyncPostgresSaver, etc.).

    Returns:
        A compiled LangGraph StateGraph ready for ``.invoke()`` / ``.astream()``.
    """
    state_type = _build_typed_dict(workflow_def)
    graph: StateGraph[Any, Any, Any, Any] = StateGraph(state_type)

    # --- Track which nodes are human gateways for interrupt_before ---
    gateway_ids: list[str] = []

    # --- Add nodes ---
    for node_def in workflow_def.nodes:
        if node_def.type == "human_gateway":
            gateway_ids.append(node_def.id)
            # LangGraph interrupt_before works by stopping BEFORE the node executes.
            # We still need a stub node in the graph — it does nothing on resume.
            async def _gateway_stub(state: dict[str, Any]) -> dict[str, Any]:
                return state

            graph.add_node(node_def.id, _gateway_stub)  # type: ignore[type-var]
        else:
            # Capture agent_name in closure to avoid late-binding.
            agent_name = node_def.agent
            assert agent_name is not None  # guaranteed by NodeDefinition validator

            agent_fn = agent_registry.get(agent_name)
            if agent_fn is None:
                raise KeyError(
                    f"Agent '{agent_name}' (node '{node_def.id}') not found in "
                    f"agent_registry. Available: {sorted(agent_registry.keys())}"
                )

            # Wrap to ensure we always get a dict back.
            async def _agent_node(
                state: dict[str, Any], _fn: AgentFn = agent_fn
            ) -> dict[str, Any]:
                return await _fn(state)

            graph.add_node(node_def.id, _agent_node)  # type: ignore[type-var]

    # --- Group edges by source node ---
    # For a given source node: if ALL outgoing edges are unconditional (no condition
    # string), use add_edge; if ANY have conditions, use add_conditional_edges.
    from collections import defaultdict

    edges_by_source: dict[str, list[Any]] = defaultdict(list)
    for edge in workflow_def.edges:
        edges_by_source[edge.from_node].append(edge)

    for from_node, out_edges in edges_by_source.items():
        has_conditions = any(e.condition is not None for e in out_edges)

        if not has_conditions:
            # Simple unconditional edges — there should be exactly one.
            for edge in out_edges:
                target = END if edge.to_node == _SENTINEL_END else edge.to_node
                graph.add_edge(from_node, target)
        else:
            # Build a routing function from the conditions.
            # Track loop counts in state under a private key.
            loop_key_prefix = f"__loops_{from_node}_"

            def _make_router(
                captured_edges: list[Any],
                captured_loop_prefix: str,
            ) -> Callable[[dict[str, Any]], str]:
                def _router(state: dict[str, Any]) -> str:
                    for edge in captured_edges:
                        if edge.condition is None:
                            return END if edge.to_node == _SENTINEL_END else edge.to_node

                        # Approved/rejected sentinels come from human gateway context.
                        approved = state.get("__human_decision") == "approved"
                        rejected = state.get("__human_decision") == "rejected"

                        try:
                            matched = evaluate_condition(
                                edge.condition,
                                state,
                                approved=approved,
                                rejected=rejected,
                            )
                        except (SecurityError, Exception):
                            matched = False

                        if not matched:
                            continue

                        # Enforce max_loops cap.
                        loop_key = f"{captured_loop_prefix}{edge.to_node}"
                        current_loops = int(state.get(loop_key, 0))
                        if edge.max_loops > 0 and current_loops >= edge.max_loops:
                            continue  # cap exceeded — try next edge

                        return END if edge.to_node == _SENTINEL_END else edge.to_node

                    # No edge matched — terminate the graph.
                    return END

                return _router

            router_fn = _make_router(out_edges, loop_key_prefix)

            # Build the mapping from router return values → node IDs.
            path_map: dict[str, str] = {END: END}
            for edge in out_edges:
                target = END if edge.to_node == _SENTINEL_END else edge.to_node
                path_map[target] = target

            graph.add_conditional_edges(from_node, router_fn, path_map)  # type: ignore[arg-type]

    # --- Entry point ---
    entry = _find_entry_node(workflow_def)
    graph.set_entry_point(entry)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=gateway_ids if gateway_ids else None,
    )

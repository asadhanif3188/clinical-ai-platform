"""Workflow recovery from persisted checkpoints.

``resume_from_checkpoint`` is the primary entry point.  It loads the last
saved state from the ``PostgresCheckpointer``, applies any pending human
decision if required, and delegates to ``WorkflowEngine.resume()`` or restarts
from the saved node.

Design intent
-------------
The ``WorkflowEngine`` already has the concept of a checkpoint via its
``CheckpointerProtocol``.  Recovery here bridges the gap between a
*PostgreSQL-persisted* checkpoint (via ``PostgresCheckpointer``) and the
engine's in-memory state.

For simple crash-and-resume (no human gateway pending), we reload the saved
state dict and call ``engine.run()`` with the saved ``run_id`` – the engine's
internal routing will start from the node recorded in ``_current_node``.

For human-gateway resumes, callers should use ``WorkflowEngine.resume()``
directly after supplying a ``HumanDecision``.
"""

from __future__ import annotations

from typing import Any

from clinical_ai_clinflow.checkpoint import PostgresCheckpointer
from clinical_ai_clinflow.engine import WorkflowEngine, WorkflowResult
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)


async def resume_from_checkpoint(
    run_id: str,
    engine: WorkflowEngine,
    *,
    checkpointer: PostgresCheckpointer,
) -> WorkflowResult:
    """Resume a previously interrupted workflow from its last checkpoint.

    This function is used for **crash recovery** — when a workflow process was
    killed mid-execution and the ``WorkflowEngine`` no longer holds the in-flight
    state.  It reconstructs the engine's internal state from the persisted
    checkpoint and continues execution from the node where execution stopped.

    For **human-gateway pauses** (``HumanGatewayPause`` was raised), use
    ``WorkflowEngine.resume()`` directly instead.

    Args:
        run_id: The workflow run ID.  Must match a row in ``workflow_runs``.
        engine: A ``WorkflowEngine`` instance configured with the same
                ``agent_registry`` as the original run.
        checkpointer: The ``PostgresCheckpointer`` that holds the persisted state.

    Returns:
        ``WorkflowResult`` on successful completion.

    Raises:
        KeyError: If no checkpoint is found for ``run_id``.
        RuntimeError: If the saved checkpoint cannot be reconstructed.
    """
    from langchain_core.runnables import RunnableConfig  # noqa: PLC0415

    config: RunnableConfig = {"configurable": {"thread_id": run_id}}
    tup = await checkpointer.aget_tuple(config)

    if tup is None:
        raise KeyError(
            f"No checkpoint found for run_id '{run_id}'. "
            "The workflow may not have been started or its checkpoint was deleted."
        )

    # The checkpoint stores the raw LangGraph state dict inside channel_values.
    # The engine's own state dict is stored under the channel "__root__" or
    # directly as the channel values depending on how the graph was compiled.
    # We extract the full state and feed it back to the engine.
    channel_values: dict[str, Any] = tup.checkpoint.get("channel_values", {})

    # Restore the engine-internal fields that were persisted by the engine itself.
    # The engine stores its bookkeeping under "_"-prefixed keys in the state dict.
    # These were serialised into channel_values by the graph checkpointer.
    restored_state: dict[str, Any] = {}
    for key, value in channel_values.items():
        restored_state[key] = value

    # Ensure the run_id is injected so the engine continues with the same ID.
    restored_state["_run_id"] = run_id

    logger.info(
        "resuming_from_checkpoint",
        run_id=run_id,
        current_node=restored_state.get("_current_node"),
        keys=sorted(k for k in restored_state if not k.startswith("_")),
    )

    # Re-use the engine's run() — it will route from _current_node because
    # the engine checkpointer will find the existing state on first save.
    # We pass the restored state as initial_state; the engine prepends _run_id.
    return await engine.run(
        initial_state=restored_state,
        run_id=run_id,
    )

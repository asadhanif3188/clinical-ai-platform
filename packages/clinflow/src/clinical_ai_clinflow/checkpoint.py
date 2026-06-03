"""PostgreSQL-backed LangGraph checkpoint saver for ClinFlow AI.

Stores every LangGraph checkpoint in the ``workflow_runs`` table so that
interrupted workflows can be resumed after a process restart.

Architecture
------------
LangGraph's checkpoint model has two layers:

1. ``Checkpoint`` — the structural snapshot: channel versions, pending sends.
   The *values* of channels are stored separately as blobs (bytes) keyed by
   (thread_id, checkpoint_ns, channel, version).  This allows large channel
   values to be diffed efficiently.

2. ``CheckpointMetadata`` — step count, source, parent ID, etc.

``WorkflowRun.checkpoint`` (JSONB) stores a single JSON object with three
keys:

    {
        "checkpoint_bytes": "<hex>",   # serde.dumps_typed(checkpoint_without_values)
        "metadata_bytes":   "<hex>",   # serde.dumps_typed(metadata)
        "blobs": {                     # keyed by "{channel}/{version}"
            "channel/ver": ["<type>", "<hex_bytes>"]
        },
        "writes": {                    # keyed by "{task_id}/{idx}"
            "task/0": ["task_id", "channel", "<type>", "<hex_bytes>", "path"]
        },
        "parent_checkpoint_id": "<id> | null"
    }

Only ONE row per ``thread_id`` (= ``run_id``) is maintained.  ``alist``
returns a single-entry stream from this row.

The class is async-first: ``aput``, ``aget_tuple``, ``alist``,
``aput_writes`` are the primary interface.  The sync counterparts delegate to
the async versions via ``asyncio.get_event_loop().run_until_complete()`` only
when called from a sync context (e.g. tests).  For production, always use the
async methods.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from datetime import datetime, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clinical_ai_shared.db.models import WorkflowRun
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bytes_to_hex(b: bytes) -> str:
    return b.hex()


def _hex_to_bytes(h: str) -> bytes:
    return bytes.fromhex(h)


def _encode_typed(typed: tuple[str, bytes]) -> list[str]:
    return [typed[0], _bytes_to_hex(typed[1])]


def _decode_typed(raw: list[str]) -> tuple[str, bytes]:
    return (raw[0], _hex_to_bytes(raw[1]))


def _current_node_from_metadata(metadata: dict[str, Any]) -> str | None:
    """Best-effort extraction of the current node from LangGraph step metadata."""
    # LangGraph stores the last completed step in metadata["writes"] keys.
    writes = metadata.get("writes") or {}
    if writes:
        return str(next(iter(writes)))
    return None


# ---------------------------------------------------------------------------
# PostgresCheckpointer
# ---------------------------------------------------------------------------


class PostgresCheckpointer(BaseCheckpointSaver[int]):
    """LangGraph checkpoint saver backed by the ``workflow_runs`` PostgreSQL table.

    Args:
        session_factory: An ``async_sessionmaker[AsyncSession]`` produced by
            ``clinical_ai_shared.db.postgres.get_session_factory()``.
        workflow_name: Workflow name stored in new ``WorkflowRun`` rows.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workflow_name: str = "unknown",
    ) -> None:
        super().__init__()
        self._factory = session_factory
        self._workflow_name = workflow_name

    # ------------------------------------------------------------------
    # Internal: load / persist the JSONB envelope
    # ------------------------------------------------------------------

    async def _load_row(
        self, session: AsyncSession, thread_id: str
    ) -> WorkflowRun | None:
        result = await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(thread_id))
        )
        return result.scalar_one_or_none()

    async def _upsert_row(
        self,
        session: AsyncSession,
        thread_id: str,
        payload: dict[str, Any],
        status: str,
        current_node: str | None,
    ) -> None:
        run_id = uuid.UUID(thread_id)
        existing = await self._load_row(session, thread_id)
        if existing is None:
            row = WorkflowRun(
                id=run_id,
                workflow_name=self._workflow_name,
                status=status,
                current_node=current_node,
                checkpoint=payload,
            )
            session.add(row)
        else:
            await session.execute(
                update(WorkflowRun)
                .where(WorkflowRun.id == run_id)
                .values(
                    status=status,
                    current_node=current_node,
                    checkpoint=payload,
                    updated_at=datetime.now(timezone.utc),
                )
            )
        await session.commit()

    # ------------------------------------------------------------------
    # put / get_tuple / list / put_writes  (sync wrappers for LangGraph)
    # ------------------------------------------------------------------

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Synchronous put — delegates to aput via a new event loop iteration."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.aput(config, checkpoint, metadata, new_versions)
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Synchronous get_tuple — delegates to aget_tuple."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.aget_tuple(config))

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """Synchronous list — collects the async iterator."""
        import asyncio

        async def _collect() -> list[CheckpointTuple]:
            return [
                t
                async for t in self.alist(config, filter=filter, before=before, limit=limit)
            ]

        return iter(asyncio.get_event_loop().run_until_complete(_collect()))

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            self.aput_writes(config, writes, task_id, task_path)
        )

    # ------------------------------------------------------------------
    # aput
    # ------------------------------------------------------------------

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        parent_checkpoint_id: str | None = config["configurable"].get("checkpoint_id")

        # Serialise the checkpoint (without channel_values — stored as blobs).
        c: dict[str, Any] = dict(checkpoint)
        raw_channel_values = c.pop("channel_values", {})
        channel_values: dict[str, Any] = raw_channel_values if isinstance(raw_channel_values, dict) else {}

        checkpoint_bytes = self.serde.dumps_typed(c)

        # Serialise metadata.
        meta_bytes = self.serde.dumps_typed(
            dict(metadata)
        )

        # Load existing payload to merge blobs and writes.
        async with self._factory() as session:
            existing_row = await self._load_row(session, thread_id)

        existing_payload: dict[str, Any] = {}
        if existing_row and existing_row.checkpoint:
            existing_payload = dict(existing_row.checkpoint)

        blobs: dict[str, list[str]] = dict(existing_payload.get("blobs", {}))
        for channel, version in new_versions.items():
            blob_key = f"{channel}/{version}"
            if channel in channel_values:
                blobs[blob_key] = _encode_typed(self.serde.dumps_typed(channel_values[channel]))
            else:
                blobs[blob_key] = ["empty", ""]

        payload: dict[str, Any] = {
            "checkpoint_id": checkpoint["id"],
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_bytes": _bytes_to_hex(checkpoint_bytes[1]),
            "checkpoint_type": checkpoint_bytes[0],
            "metadata_bytes": _bytes_to_hex(meta_bytes[1]),
            "metadata_type": meta_bytes[0],
            "blobs": blobs,
            "writes": existing_payload.get("writes", {}),
            "parent_checkpoint_id": parent_checkpoint_id,
        }

        current_node = _current_node_from_metadata(dict(metadata))
        status = "running"

        async with self._factory() as session:
            await self._upsert_row(session, thread_id, payload, status, current_node)

        logger.info(
            "checkpoint_saved",
            thread_id=thread_id,
            checkpoint_id=checkpoint["id"],
            current_node=current_node,
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    # ------------------------------------------------------------------
    # aget_tuple
    # ------------------------------------------------------------------

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id: str = config["configurable"]["thread_id"]

        async with self._factory() as session:
            row = await self._load_row(session, thread_id)

        if row is None or not row.checkpoint:
            return None

        payload = dict(row.checkpoint)
        checkpoint_id: str = payload["checkpoint_id"]
        checkpoint_ns: str = payload.get("checkpoint_ns", "")

        # If caller requested a specific checkpoint_id, verify it matches.
        requested_id = get_checkpoint_id(config)
        if requested_id and requested_id != checkpoint_id:
            return None

        # Deserialise checkpoint (structural part only).
        chk: Checkpoint = self.serde.loads_typed(
            (payload["checkpoint_type"], _hex_to_bytes(payload["checkpoint_bytes"]))
        )

        # Rebuild channel_values from blobs.
        channel_values: dict[str, Any] = {}
        blobs: dict[str, list[str]] = payload.get("blobs", {})
        for blob_key, encoded in blobs.items():
            channel = blob_key.rsplit("/", 1)[0]
            if encoded[0] == "empty":
                continue
            channel_values[channel] = self.serde.loads_typed(_decode_typed(encoded))
        chk = {**chk, "channel_values": channel_values}

        # Deserialise metadata.
        meta: CheckpointMetadata = self.serde.loads_typed(
            (payload["metadata_type"], _hex_to_bytes(payload["metadata_bytes"]))
        )

        # Reconstruct pending_writes.
        raw_writes = payload.get("writes", {})
        pending_writes: list[tuple[str, str, Any]] = []
        for _key, parts in raw_writes.items():
            task_id_w, channel_w, type_w, hex_w, _path = parts
            pending_writes.append(
                (task_id_w, channel_w, self.serde.loads_typed((type_w, _hex_to_bytes(hex_w))))
            )

        parent_checkpoint_id: str | None = payload.get("parent_checkpoint_id")

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=chk,
            metadata=meta,
            pending_writes=pending_writes,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
        )

    # ------------------------------------------------------------------
    # alist
    # ------------------------------------------------------------------

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Yield the latest checkpoint for a thread (at most one per run_id)."""
        if config is None:
            return

        tup = await self.aget_tuple(config)
        if tup is None:
            return

        if before:
            before_id = get_checkpoint_id(before)
            if before_id and tup.checkpoint["id"] >= before_id:
                return

        if filter:
            meta = dict(tup.metadata) if tup.metadata else {}
            if not all(meta.get(k) == v for k, v in filter.items()):
                return

        yield tup

    # ------------------------------------------------------------------
    # aput_writes
    # ------------------------------------------------------------------

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_id: str = config["configurable"]["checkpoint_id"]

        async with self._factory() as session:
            row = await self._load_row(session, thread_id)

        if row is None or not row.checkpoint:
            return

        payload = dict(row.checkpoint)
        raw_writes: dict[str, list[str]] = dict(payload.get("writes", {}))

        write_channel: str
        write_value: Any
        for idx, (write_channel, write_value) in enumerate(writes):
            key = f"{task_id}/{idx}"
            if key in raw_writes:
                continue  # idempotent — skip duplicates
            typed = self.serde.dumps_typed(write_value)
            raw_writes[key] = [task_id, write_channel, typed[0], _bytes_to_hex(typed[1]), task_path]

        payload["writes"] = raw_writes

        async with self._factory() as session:
            run_id = uuid.UUID(thread_id)
            await session.execute(
                update(WorkflowRun)
                .where(WorkflowRun.id == run_id)
                .values(
                    checkpoint=payload,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        logger.debug(
            "checkpoint_writes_saved",
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            n_writes=len(writes),
        )

"""Unit tests for AuditTrailWriter.

Coverage:
- Append-only: write() only calls session.add() / commit(), never UPDATE/DELETE
- AuditTrailWriter has no update() or delete() methods
- input_hash stored is SHA-256 digest, not raw input
- hash_input() produces a 64-char hex SHA-256 digest
- export_csv() returns correct headers and one row per entry
- export_csv() with zero results returns headers-only CSV
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinical_ai_clinflow.audit import AuditTrailWriter, hash_input
from clinical_ai_shared.schemas.audit import AuditLogEntry, AuditQuery


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_entry(**overrides: object) -> AuditLogEntry:
    defaults: dict[str, object] = {
        "entry_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "agent": "intake_agent",
        "node": "classify",
        "input_hash": hashlib.sha256(b"test_input").hexdigest(),
        "output_summary": "Classified as lab_report",
        "model_used": "claude-haiku-4-5-20251001",
        "tokens_used": 500,
        "cost_usd": 0.0005,
        "duration_ms": 800,
        "timestamp": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return AuditLogEntry(**defaults)  # type: ignore[arg-type]


def _make_orm_row(**overrides: object) -> MagicMock:
    """Minimal mock that satisfies the ORM-to-schema conversion."""
    row = MagicMock()
    row.id = overrides.get("id", uuid.uuid4())
    row.run_id = overrides.get("run_id", uuid.uuid4())
    row.agent = overrides.get("agent", "intake_agent")
    row.node = overrides.get("node", "classify")
    row.input_hash = overrides.get("input_hash", hashlib.sha256(b"x").hexdigest())
    row.output_summary = overrides.get("output_summary", "ok")
    row.model_used = overrides.get("model_used", "claude-haiku-4-5-20251001")
    row.tokens_used = overrides.get("tokens_used", 100)
    row.cost_usd = overrides.get("cost_usd", 0.001)
    row.duration_ms = overrides.get("duration_ms", 500)
    row.timestamp = overrides.get("timestamp", datetime.now(timezone.utc))
    row.human_decision = overrides.get("human_decision", None)
    row.human_reviewer = overrides.get("human_reviewer", None)
    return row


def _make_session_factory(session: AsyncMock) -> MagicMock:
    """Return a mock session factory whose async context manager yields *session*."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=cm)
    return factory


# ---------------------------------------------------------------------------
# Append-only tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_calls_add_and_commit_only() -> None:
    """write() must use session.add() + commit() — never execute(update/delete)."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    factory = _make_session_factory(session)

    writer = AuditTrailWriter(factory)
    await writer.write(_make_entry())

    session.add.assert_called_once()
    session.commit.assert_awaited_once()

    # Verify no UPDATE/DELETE in any execute() calls
    for call in session.execute.call_args_list:
        stmt = call.args[0] if call.args else None
        if stmt is not None:
            stmt_str = str(stmt).upper()
            assert "UPDATE" not in stmt_str, "write() must not issue UPDATE"
            assert "DELETE" not in stmt_str, "write() must not issue DELETE"


@pytest.mark.asyncio
async def test_write_stores_correct_fields() -> None:
    """write() passes all AuditLogEntry fields to the ORM object unchanged."""
    session = AsyncMock()
    captured: list[object] = []
    session.add = MagicMock(side_effect=lambda obj: captured.append(obj))
    session.commit = AsyncMock()
    factory = _make_session_factory(session)

    entry = _make_entry()
    writer = AuditTrailWriter(factory)
    await writer.write(entry)

    assert len(captured) == 1
    orm_obj = captured[0]
    assert orm_obj.id == entry.entry_id
    assert orm_obj.run_id == entry.run_id
    assert orm_obj.agent == entry.agent
    assert orm_obj.node == entry.node
    assert orm_obj.input_hash == entry.input_hash
    assert orm_obj.output_summary == entry.output_summary


def test_audit_trail_writer_has_no_update_or_delete_methods() -> None:
    """AuditTrailWriter must not expose update() or delete() — append-only by design."""
    session = AsyncMock()
    factory = _make_session_factory(session)
    writer = AuditTrailWriter(factory)

    assert not hasattr(writer, "update"), "AuditTrailWriter must not expose update()"
    assert not hasattr(writer, "delete"), "AuditTrailWriter must not expose delete()"


@pytest.mark.asyncio
async def test_write_reraises_on_db_failure() -> None:
    """If the DB write fails, write() must raise — never swallow the error."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock(side_effect=RuntimeError("DB down"))
    factory = _make_session_factory(session)

    writer = AuditTrailWriter(factory)
    with pytest.raises(RuntimeError, match="DB down"):
        await writer.write(_make_entry())


# ---------------------------------------------------------------------------
# input_hash tests
# ---------------------------------------------------------------------------


def test_hash_input_produces_sha256_hex_digest() -> None:
    """hash_input() returns the 64-char SHA-256 hex digest of the input."""
    raw = "patient_id=PHI-12345"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    result = hash_input(raw)
    assert result == expected
    assert len(result) == 64


def test_hash_input_differs_for_different_inputs() -> None:
    assert hash_input("doc_a") != hash_input("doc_b")


@pytest.mark.asyncio
async def test_write_stores_hash_not_raw_input() -> None:
    """The value persisted in the ORM row must be the hash, not the raw input."""
    session = AsyncMock()
    captured: list[object] = []
    session.add = MagicMock(side_effect=lambda obj: captured.append(obj))
    session.commit = AsyncMock()
    factory = _make_session_factory(session)

    raw_input = "patient_id=PHI-12345"
    input_hash = hash_input(raw_input)
    entry = _make_entry(input_hash=input_hash)

    writer = AuditTrailWriter(factory)
    await writer.write(entry)

    orm_obj = captured[0]
    assert orm_obj.input_hash == input_hash, "stored hash must equal SHA-256 digest"
    assert orm_obj.input_hash != raw_input, "raw input must NOT be stored"
    assert len(orm_obj.input_hash) == 64, "SHA-256 digest must be 64 hex chars"


# ---------------------------------------------------------------------------
# CSV export tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_csv_correct_headers_and_row_count() -> None:
    """export_csv() returns all expected column headers and one row per entry."""
    rows = [_make_orm_row() for _ in range(3)]

    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=execute_result)
    factory = _make_session_factory(session)

    writer = AuditTrailWriter(factory)
    buffer = await writer.export_csv(AuditQuery())

    assert isinstance(buffer, io.StringIO)
    reader = list(csv.DictReader(buffer))

    expected_headers = {
        "entry_id",
        "run_id",
        "agent",
        "node",
        "input_hash",
        "output_summary",
        "model_used",
        "tokens_used",
        "cost_usd",
        "duration_ms",
        "timestamp",
        "human_decision",
        "human_reviewer",
    }
    assert expected_headers == set(reader[0].keys()), "CSV headers must match AuditLogEntry fields"
    assert len(reader) == 3, "one CSV row per entry"


@pytest.mark.asyncio
async def test_export_csv_empty_result_returns_headers_only() -> None:
    """export_csv() with no rows must still emit a header line."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=execute_result)
    factory = _make_session_factory(session)

    writer = AuditTrailWriter(factory)
    buffer = await writer.export_csv(AuditQuery())
    content = buffer.read()

    non_empty_lines = [line for line in content.strip().splitlines() if line]
    assert len(non_empty_lines) == 1, "headers-only CSV must have exactly one line"
    assert "entry_id" in non_empty_lines[0]


@pytest.mark.asyncio
async def test_export_csv_row_values_are_correct() -> None:
    """CSV rows must contain the correct values from each ORM row."""
    run_id = uuid.uuid4()
    input_hash = hashlib.sha256(b"data").hexdigest()
    ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    row = _make_orm_row(
        agent="validation_agent",
        node="validate",
        run_id=run_id,
        input_hash=input_hash,
        output_summary="Validation passed",
        tokens_used=300,
        timestamp=ts,
    )

    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [row]
    session.execute = AsyncMock(return_value=execute_result)
    factory = _make_session_factory(session)

    writer = AuditTrailWriter(factory)
    buffer = await writer.export_csv(AuditQuery())
    data_row = list(csv.DictReader(buffer))[0]

    assert data_row["agent"] == "validation_agent"
    assert data_row["node"] == "validate"
    assert data_row["run_id"] == str(run_id)
    assert data_row["input_hash"] == input_hash
    assert data_row["output_summary"] == "Validation passed"
    assert data_row["tokens_used"] == "300"
    assert data_row["timestamp"] == ts.isoformat()

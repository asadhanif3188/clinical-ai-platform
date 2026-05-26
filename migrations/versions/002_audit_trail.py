"""audit_trail

Revision ID: 002
Revises: 001
Create Date: 2026-05-26 13:15:39.540236

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_log_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent", sa.String(length=100), nullable=False),
        sa.Column("node", sa.String(length=255), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("human_decision", sa.String(length=50), nullable=True),
        sa.Column("human_reviewer", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add append-only trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_audit_log()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'AuditLogEntry is append-only. UPDATE and DELETE are not allowed.';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log_entries
        FOR EACH ROW EXECUTE FUNCTION protect_audit_log();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log_entries")
    op.execute("DROP FUNCTION IF EXISTS protect_audit_log()")
    op.drop_table("audit_log_entries")

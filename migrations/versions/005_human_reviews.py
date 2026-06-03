"""human_reviews

Revision ID: 005
Revises: 004
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | Sequence[str] | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "human_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewer_id", sa.String(length=255), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_reviews_run_id", "human_reviews", ["run_id"], unique=False)
    op.create_index("ix_human_reviews_status", "human_reviews", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_human_reviews_status", table_name="human_reviews")
    op.drop_index("ix_human_reviews_run_id", table_name="human_reviews")
    op.drop_table("human_reviews")

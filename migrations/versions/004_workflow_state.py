"""workflow_state

Revision ID: 004
Revises: 003
Create Date: 2026-05-26 13:16:31.626086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, Sequence[str], None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_workflow_runs_status', 'workflow_runs', ['status'], unique=False)
    op.create_index('ix_workflow_runs_workflow_name', 'workflow_runs', ['workflow_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_workflow_runs_workflow_name', table_name='workflow_runs')
    op.drop_index('ix_workflow_runs_status', table_name='workflow_runs')

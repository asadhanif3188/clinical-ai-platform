"""memory_tables

Revision ID: 003
Revises: 002
Create Date: 2026-05-26 13:16:06.612216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, Sequence[str], None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'long_term_memory_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_accessed', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('access_count', sa.Integer(), nullable=False),
        sa.Column('source_sessions', sa.ARRAY(sa.String()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create HNSW index for pgvector
    op.execute("CREATE INDEX ix_long_term_memory_entries_embedding ON long_term_memory_entries USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        'procedural_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(length=100), nullable=False),
        sa.Column('format_fingerprint', sa.String(length=255), nullable=False),
        sa.Column('extraction_hints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=False),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('procedural_templates')
    op.drop_table('long_term_memory_entries')

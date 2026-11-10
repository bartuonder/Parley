"""add rag chunk index

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10 21:48:53.049579

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("strategy", sa.String(length=16), nullable=False),
        sa.Column("chunk_id", sa.String(length=120), nullable=False),
        sa.Column("doc_id", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "refunds",
                "shipping",
                "subscriptions",
                "billing",
                "escalation",
                "general",
                "promotions",
                name="policycategory",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expires_date", sa.Date(), nullable=True),
        sa.Column("section", sa.String(length=200), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
        sa.UniqueConstraint("strategy", "chunk_id", name="uq_chunks_strategy_chunk"),
    )
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_pk", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_pk"],
            ["chunks.id"],
            name=op.f("fk_chunk_embeddings_chunk_pk_chunks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk_embeddings")),
        sa.UniqueConstraint("chunk_pk", "model", name="uq_chunk_embeddings_chunk_model"),
    )
    op.create_index(
        op.f("ix_chunk_embeddings_chunk_pk"), "chunk_embeddings", ["chunk_pk"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_chunk_embeddings_chunk_pk"), table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_table("chunks")

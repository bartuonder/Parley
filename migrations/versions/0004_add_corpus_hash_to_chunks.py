"""add corpus hash to chunks

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10 22:43:37.248425

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "chunks",
        sa.Column("corpus_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.alter_column("chunks", "corpus_hash", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chunks", "corpus_hash")

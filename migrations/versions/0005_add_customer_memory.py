"""add customer memory

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "customer_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("ticket_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_memory_customer_id_customers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_memory")),
    )
    op.create_index(
        op.f("ix_customer_memory_customer_id"), "customer_memory", ["customer_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_customer_memory_customer_id"), table_name="customer_memory")
    op.drop_table("customer_memory")

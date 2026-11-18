"""add service tickets and ticket events

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "service_tickets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("specialist", sa.String(length=24), nullable=True),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("followup", sa.Text(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("latency_s", sa.Float(), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("pending", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_tickets")),
    )
    op.create_index(
        op.f("ix_service_tickets_sender_email"), "service_tickets", ["sender_email"], unique=False
    )
    op.create_index(op.f("ix_service_tickets_status"), "service_tickets", ["status"], unique=False)
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_events")),
    )
    op.create_index(
        "ix_ticket_events_ticket_id_id", "ticket_events", ["ticket_id", "id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ticket_events_ticket_id_id", table_name="ticket_events")
    op.drop_table("ticket_events")
    op.drop_index(op.f("ix_service_tickets_status"), table_name="service_tickets")
    op.drop_index(op.f("ix_service_tickets_sender_email"), table_name="service_tickets")
    op.drop_table("service_tickets")

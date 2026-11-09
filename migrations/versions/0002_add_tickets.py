"""add tickets

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-09 23:41:00.518522

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "refund",
                "shipping",
                "subscription",
                "billing",
                "general",
                name="ticketcategory",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.Enum(
                "refunded",
                "denied",
                "info_provided",
                "action_taken",
                "escalated",
                name="ticketoutcome",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=False),
        sa.Column("policy_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_tickets_customer_id_customers")
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], name=op.f("fk_tickets_invoice_id_invoices")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_tickets_order_id_orders")
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_tickets_subscription_id_subscriptions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index(op.f("ix_tickets_customer_id"), "tickets", ["customer_id"], unique=False)
    op.create_index(op.f("ix_tickets_invoice_id"), "tickets", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_tickets_order_id"), "tickets", ["order_id"], unique=False)
    op.create_index(
        op.f("ix_tickets_subscription_id"), "tickets", ["subscription_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tickets_subscription_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_order_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_invoice_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_customer_id"), table_name="tickets")
    op.drop_table("tickets")

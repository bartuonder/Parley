"""add a readable ticket number

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE service_ticket_number_seq START 1001")
    op.add_column(
        "service_tickets",
        sa.Column(
            "number",
            sa.Integer(),
            server_default=sa.text("nextval('service_ticket_number_seq')"),
            nullable=False,
        ),
    )
    op.execute("ALTER SEQUENCE service_ticket_number_seq OWNED BY service_tickets.number")
    op.create_unique_constraint(op.f("uq_service_tickets_number"), "service_tickets", ["number"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("uq_service_tickets_number"), "service_tickets", type_="unique")
    op.drop_column("service_tickets", "number")
    op.execute("DROP SEQUENCE IF EXISTS service_ticket_number_seq")

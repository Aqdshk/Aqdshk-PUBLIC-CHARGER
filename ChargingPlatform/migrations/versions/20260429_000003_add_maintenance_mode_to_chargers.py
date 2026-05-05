"""add operator maintenance_mode flag to chargers

Operator-initiated soft disable, independent of OCPP availability.
- Survives charger disconnect (DB-level, not requiring live OCPP session)
- Captures reason + who + when for audit
- /pay rejects with 503 + reason when set
- Cleared via /api/admin/charger/{id}/enable

Revision ID: 20260429_000003
Revises: 20260429_000002
Create Date: 2026-04-29 23:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260429_000003"
down_revision: Union[str, None] = "20260429_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.add_column(
            sa.Column(
                "maintenance_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(sa.Column("maintenance_reason", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("maintenance_started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("maintenance_started_by", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.drop_column("maintenance_started_by")
        batch.drop_column("maintenance_started_at")
        batch.drop_column("maintenance_reason")
        batch.drop_column("maintenance_mode")

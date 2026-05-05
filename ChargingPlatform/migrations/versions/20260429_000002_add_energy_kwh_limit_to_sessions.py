"""add energy_kwh_limit + auto_stopped to charging_sessions

Quick-pay flow buys a fixed kWh quota = amount_paid / tariff_per_kwh.
The OCPP server watches incoming MeterValues for sessions with a non-NULL
`energy_kwh_limit` and fires RemoteStopTransaction automatically when the
delivered energy reaches the quota. `auto_stopped` is the idempotency flag
so we only send RemoteStop once per session.

Revision ID: 20260429_000002
Revises: 20260429_000001
Create Date: 2026-04-29 22:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260429_000002"
down_revision: Union[str, None] = "20260429_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("charging_sessions") as batch:
        batch.add_column(sa.Column("energy_kwh_limit", sa.Float(), nullable=True))
        batch.add_column(
            sa.Column(
                "auto_stopped",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("charging_sessions") as batch:
        batch.drop_column("auto_stopped")
        batch.drop_column("energy_kwh_limit")

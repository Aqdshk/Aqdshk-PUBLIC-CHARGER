"""add tariff_per_kwh to chargers

Per-charger pricing in RM per kWh. Default RM 0.10/kWh for staging/testing
(low value so test charging sessions don't drain real wallet balances).
Production deployments should bump per charger via admin UI to RM 0.80–1.50.

Revision ID: 20260429_000001
Revises: 20260428_000001
Create Date: 2026-04-29 22:00:00
"""
from typing import Sequence, Union
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision: str = "20260429_000001"
down_revision: Union[str, None] = "20260428_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.add_column(
            sa.Column(
                "tariff_per_kwh",
                sa.Numeric(precision=8, scale=4),
                nullable=False,
                server_default="0.1000",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.drop_column("tariff_per_kwh")

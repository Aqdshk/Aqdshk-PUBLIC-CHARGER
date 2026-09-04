"""add soc to meter_values

Chargers have always sent the vehicle's state of charge in MeterValues, and we
parsed every measurand except that one, so the figure the driver reads off the
charger's own screen was thrown away on arrival.

Revision ID: 20260826_000001
Revises: 20260821_000002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_000001"
down_revision: Union[str, None] = "20260821_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("meter_values") as batch:
        batch.add_column(sa.Column("soc", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("meter_values") as batch:
        batch.drop_column("soc")

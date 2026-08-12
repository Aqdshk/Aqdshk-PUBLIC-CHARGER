"""record how each charger authenticates

OCPP auth enforcement is off fleet-wide and cannot be switched on blind: a
charger that presents no credentials would drop the moment it reconnects, and
until now the only way to know which ones those are was grepping container
logs.

Storing the last observed method and verdict on the charger row turns "can we
turn auth on yet" into something the dashboard can answer.

Left NULL for existing rows: the value is only meaningful once a charger has
actually completed a handshake since this shipped.

Revision ID: 20260812_000001
Revises: 20260810_000003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_000001"
down_revision: Union[str, None] = "20260810_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chargers", sa.Column("auth_method", sa.String(48), nullable=True))
    op.add_column("chargers", sa.Column("auth_ok", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("chargers", "auth_ok")
    op.drop_column("chargers", "auth_method")

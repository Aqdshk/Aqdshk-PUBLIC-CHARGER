"""add per-connector status JSON to chargers

A charger sends StatusNotification per connector (0 = whole station,
>=1 = each socket). The single `availability` column cannot represent
a multi-connector charger (e.g. socket 1 available, socket 2 faulted).
`connector_status` stores a JSON map {"1": "available", "2": "faulted"};
`availability` stays as the derived best-usable status.

Revision ID: 20260523_000001
Revises: 20260429_000003
Create Date: 2026-05-23 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260523_000001"
down_revision: Union[str, None] = "20260429_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.add_column(sa.Column("connector_status", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.drop_column("connector_status")

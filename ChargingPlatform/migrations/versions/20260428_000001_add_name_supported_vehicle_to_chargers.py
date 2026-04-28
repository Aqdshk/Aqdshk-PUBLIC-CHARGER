"""add name + supported_vehicle to chargers

Friendly metadata fields requested by Jeffrey:
- name: human-readable charger name (e.g. "Bangsar Mall L2 Bay 3")
- supported_vehicle: list of supported EV makes / connector compatibility note

Revision ID: 20260428_000001
Revises: 20260427_000001
Create Date: 2026-04-28 09:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260428_000001"
down_revision: Union[str, None] = "20260427_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.add_column(sa.Column("name", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("supported_vehicle", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.drop_column("supported_vehicle")
        batch.drop_column("name")

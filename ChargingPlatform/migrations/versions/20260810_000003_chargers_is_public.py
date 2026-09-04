"""add is_public to chargers — controls OCPI publication

The chargers table holds 476 rows but only single digits have reported in the
last month; the rest connected once months ago and never returned. OCPI
/locations had no filter, so a roaming partner pulling our catalogue would
publish every one of them to end users, who would then drive to charge points
that are not there.

NULL means "decide from heartbeat age", which is the wanted behaviour for
almost every row. True and False are explicit operator overrides in each
direction, for a real charger that is temporarily down and for one that should
never be published.

Left NULL for all existing rows deliberately: the automatic rule already
excludes the stale ones, and hard-coding a decision now would freeze today's
online/offline split into the data.

Revision ID: 20260810_000003
Revises: 20260810_000002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_000003"
down_revision: Union[str, None] = "20260810_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chargers", sa.Column("is_public", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("chargers", "is_public")

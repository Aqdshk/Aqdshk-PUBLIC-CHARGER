"""Partner fleet ownership: chargers.partner_owner_id

Adds a nullable partner ownership tag on chargers. When set, only partner
API calls with a matching PARTNER_OWNER_ID env value may control the charger.
NULL rows stay under admin + walk-up TNG control only (partner endpoints 403).

Revision ID: 20260709_000001
Revises: 20260622_000001
Create Date: 2026-07-09 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260709_000001"
down_revision: Union[str, None] = "20260622_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chargers",
        sa.Column("partner_owner_id", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_chargers_partner_owner_id",
        "chargers",
        ["partner_owner_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chargers_partner_owner_id", table_name="chargers")
    op.drop_column("chargers", "partner_owner_id")

"""Tenant tag on chargers — feeds the admin dashboard's tenant filter

Every charger belongs to exactly one tenant (fleet operator). Existing rows
are backfilled: chargers with a Perodua-scoped partner_owner_id → 'perodua',
everything else → 'czero-tng' (the walk-up + TNG default).

Revision ID: 20260710_000002
Revises: 20260710_000001
Create Date: 2026-07-10 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_000002"
down_revision: Union[str, None] = "20260710_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chargers",
        sa.Column(
            "tenant",
            sa.String(length=50),
            nullable=False,
            server_default="czero-tng",
        ),
    )
    op.create_index("ix_chargers_tenant", "chargers", ["tenant"])

    # Backfill: anything already tagged to a Perodua owner belongs to Perodua.
    # We check for owner_id patterns that suggest Perodua (P2-USER-*, PERODUA-*).
    # Anything else stays on the default 'czero-tng'.
    op.execute(
        """
        UPDATE chargers
        SET tenant = 'perodua'
        WHERE partner_owner_id IS NOT NULL
          AND (partner_owner_id LIKE 'P2-USER-%'
               OR partner_owner_id LIKE 'PERODUA%')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_chargers_tenant", table_name="chargers")
    op.drop_column("chargers", "tenant")

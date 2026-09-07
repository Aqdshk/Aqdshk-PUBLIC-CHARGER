"""make the tenant list editable instead of hardcoded

The dashboard's tenant switcher read a hardcoded array in static/tenant.js, so
adding a fleet operator meant a code change and a deploy. There was also no way
to move a charger between tenants except an UPDATE against the database, since
`tenant` appeared only in the charger response schema.

This table backs the switcher. `chargers.tenant` is deliberately left as a
free-form string rather than a foreign key: it predates this table and a
charger carrying an unregistered key must keep working rather than fail.

Seeds the two operators already in use so nothing changes on upgrade.

Revision ID: 20260904_000001
Revises: 20260828_000002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_000001"
down_revision: Union[str, None] = "20260828_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("badge", sa.String(12), nullable=True),
        sa.Column("hint", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tenants_key", "tenants", ["key"], unique=True)

    # The two the switcher already offered. Keys match chargers.tenant values,
    # so the existing filter keeps working unchanged.
    op.execute(
        """
        INSERT INTO tenants (`key`, label, badge, hint, is_active, sort_order)
        VALUES
          ('czero-tng', 'CZero TNG Public', 'TNG', 'Walk-up + TNG payment flow', 1, 10),
          ('perodua',   'Perodua Public',   'P2',  'Perodua P2 Superapp fleet',  1, 20)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_key", table_name="tenants")
    op.drop_table("tenants")

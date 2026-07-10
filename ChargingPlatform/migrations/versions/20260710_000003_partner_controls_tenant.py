"""Tenant guard for partner keys — partner_api_keys.controls_tenant

When set, the partner API key is restricted to chargers whose chargers.tenant
matches this value. NULL keeps existing partners unrestricted (backwards
compatible with bnb-ventures / Jeffrey's app).

Revision ID: 20260710_000003
Revises: 20260710_000002
Create Date: 2026-07-10 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_000003"
down_revision: Union[str, None] = "20260710_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "partner_api_keys",
        sa.Column("controls_tenant", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_partner_api_keys_controls_tenant",
        "partner_api_keys",
        ["controls_tenant"],
    )


def downgrade() -> None:
    op.drop_index("ix_partner_api_keys_controls_tenant", table_name="partner_api_keys")
    op.drop_column("partner_api_keys", "controls_tenant")

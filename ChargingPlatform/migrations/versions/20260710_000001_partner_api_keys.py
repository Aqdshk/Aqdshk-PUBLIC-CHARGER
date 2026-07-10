"""Multi-tenant partner API keys — DB-backed registry

Replaces the single PARTNER_API_KEY env var with a table that maps SHA-256
hashes to partner names. Each partner (Perodua, bnb-ventures, future
integrators) holds their own key; the server hashes incoming headers and
looks them up.

Revision ID: 20260710_000001
Revises: 20260709_000001
Create Date: 2026-07-10 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_000001"
down_revision: Union[str, None] = "20260709_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partner_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("partner_name", sa.String(length=50), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("partner_name", name="uq_partner_api_keys_partner_name"),
        sa.UniqueConstraint("key_hash", name="uq_partner_api_keys_key_hash"),
    )
    op.create_index("ix_partner_api_keys_partner_name", "partner_api_keys", ["partner_name"])
    op.create_index("ix_partner_api_keys_key_hash", "partner_api_keys", ["key_hash"])
    op.create_index("ix_partner_api_keys_active", "partner_api_keys", ["active"])


def downgrade() -> None:
    op.drop_index("ix_partner_api_keys_active", table_name="partner_api_keys")
    op.drop_index("ix_partner_api_keys_key_hash", table_name="partner_api_keys")
    op.drop_index("ix_partner_api_keys_partner_name", table_name="partner_api_keys")
    op.drop_table("partner_api_keys")

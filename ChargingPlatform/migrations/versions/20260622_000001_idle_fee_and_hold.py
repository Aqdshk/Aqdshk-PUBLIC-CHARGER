"""Idle-fee + hold/refund: system_settings, charger idle config, session idle/refund tracking

Adds the schema needed for the post-charge idle fee + deposit-and-refund flow:

1. system_settings — generic kv store, seeded with payment_hold_amount_rm=150
   so ops can tune the deposit amount without a redeploy.
2. chargers — per-charger idle fee toggle, rate (RM/min), grace period (min).
3. charging_sessions — energy budget the customer picked, deposit held,
   when charge actually finished, idle minutes accrued, idle fee, final
   refund amount + linkage back to the TNG refund txn.

Revision ID: 20260622_000001
Revises: 20260618_000001
Create Date: 2026-06-22 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_000001"
down_revision: Union[str, None] = "20260618_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) system_settings — generic kv store for ops-tunable knobs
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    # Seed the deposit amount (RM 150) as the default hold per session.
    op.execute(
        "INSERT INTO system_settings (`key`, value, description, updated_at) VALUES "
        "('payment_hold_amount_rm', '150', "
        "'Deposit held per charging session (RM). Unused balance refunded after unplug.', "
        "NOW())"
    )

    # 2) chargers — idle fee config (off by default so this rolls out gracefully)
    op.add_column("chargers", sa.Column("idle_fee_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("chargers", sa.Column("idle_fee_per_min", sa.Numeric(6, 2), nullable=False, server_default="0.40"))
    op.add_column("chargers", sa.Column("idle_grace_minutes", sa.Integer(), nullable=False, server_default="15"))

    # 3) charging_sessions — track the customer's energy budget, the deposit,
    #    and the post-charge idle / refund settlement.
    op.add_column("charging_sessions", sa.Column("energy_budget_rm", sa.Numeric(8, 2), nullable=True))
    op.add_column("charging_sessions", sa.Column("hold_amount_rm", sa.Numeric(8, 2), nullable=True))
    op.add_column("charging_sessions", sa.Column("charge_complete_at", sa.DateTime(), nullable=True))
    op.add_column("charging_sessions", sa.Column("idle_started_at", sa.DateTime(), nullable=True))
    op.add_column("charging_sessions", sa.Column("idle_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("charging_sessions", sa.Column("idle_fee_amount", sa.Numeric(8, 2), nullable=False, server_default="0"))
    op.add_column("charging_sessions", sa.Column("refund_amount", sa.Numeric(8, 2), nullable=True))
    op.add_column("charging_sessions", sa.Column("refund_status", sa.String(length=32), nullable=True))
    op.add_column("charging_sessions", sa.Column("refund_txn_ref", sa.String(length=64), nullable=True))
    op.add_column("charging_sessions", sa.Column("refund_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ("refund_at", "refund_txn_ref", "refund_status", "refund_amount",
                "idle_fee_amount", "idle_minutes", "idle_started_at",
                "charge_complete_at", "hold_amount_rm", "energy_budget_rm"):
        op.drop_column("charging_sessions", col)
    for col in ("idle_grace_minutes", "idle_fee_per_min", "idle_fee_enabled"):
        op.drop_column("chargers", col)
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")

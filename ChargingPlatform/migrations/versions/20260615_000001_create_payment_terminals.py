"""create payment_terminals + terminal_chargers tables

Self-service payment kiosks (tablet/POS) mounted at charging stations.
User picks a charger on the terminal screen → TNG QR shown → user scans
with TNG app → backend triggers OCPP RemoteStart.

Each terminal can be assigned 1..N chargers (a 4-charger location uses
one terminal that manages all four).

Revision ID: 20260615_000001
Revises: 20260609_000001
Create Date: 2026-06-15 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260615_000001"
down_revision: Union[str, None] = "20260609_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_terminals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False, unique=True),  # opaque identifier in the URL
        sa.Column("api_key", sa.String(length=128), nullable=False),                # secret for terminal-auth header
        sa.Column("display_name", sa.String(length=128), nullable=False),           # "Petronas Setia Alam Terminal 1"
        sa.Column("location_label", sa.String(length=256), nullable=True),          # human-readable location
        sa.Column("location_lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("location_lng", sa.Numeric(10, 7), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),  # active|offline|disabled
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payment_terminals_device_id", "payment_terminals", ["device_id"])

    op.create_table(
        "terminal_chargers",
        sa.Column("terminal_id", sa.Integer(), sa.ForeignKey("payment_terminals.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("charger_id", sa.Integer(), sa.ForeignKey("chargers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),  # order on terminal UI
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_terminal_chargers_terminal_id", "terminal_chargers", ["terminal_id"])
    op.create_index("ix_terminal_chargers_charger_id", "terminal_chargers", ["charger_id"])


def downgrade() -> None:
    op.drop_index("ix_terminal_chargers_charger_id", table_name="terminal_chargers")
    op.drop_index("ix_terminal_chargers_terminal_id", table_name="terminal_chargers")
    op.drop_table("terminal_chargers")
    op.drop_index("ix_payment_terminals_device_id", table_name="payment_terminals")
    op.drop_table("payment_terminals")

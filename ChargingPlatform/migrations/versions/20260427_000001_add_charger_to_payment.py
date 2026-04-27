"""add charger_id/connector_id/customer_email to payment_transactions

Adds linkage from payment to a specific charger so that the TNG callback
handler can auto-trigger OCPP RemoteStartTransaction once payment is
verified, without requiring the user to be logged in (QR-scan flow).

Revision ID: 20260427_000001
Revises: 20260301_000001
Create Date: 2026-04-27 12:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260427_000001"
down_revision: Union[str, None] = "20260301_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payment_transactions") as batch:
        batch.add_column(sa.Column("charger_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("connector_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("customer_email", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_payment_transactions_charger_id",
        "payment_transactions",
        ["charger_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_charger_id", table_name="payment_transactions")
    with op.batch_alter_table("payment_transactions") as batch:
        batch.drop_column("customer_email")
        batch.drop_column("connector_id")
        batch.drop_column("charger_id")

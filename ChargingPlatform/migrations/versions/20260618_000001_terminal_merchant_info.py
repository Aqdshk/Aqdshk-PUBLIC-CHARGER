"""add merchant info fields to payment_terminals for TNG extendInfo

TNGD requires merchant location, brand, shop name, MCC etc. in
extendInfo on every OrderCode Create request (per TPA v1.6 spec).
We store this per terminal so the kiosk's payment_start can inline
the fields when calling TNG, instead of asking ops to set them
globally or per-charger.

Revision ID: 20260618_000001
Revises: 20260615_000002
Create Date: 2026-06-18 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_000001"
down_revision: Union[str, None] = "20260615_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_terminals", sa.Column("shop_name", sa.String(length=128), nullable=True))
    op.add_column("payment_terminals", sa.Column("brand", sa.String(length=128), nullable=True))
    op.add_column("payment_terminals", sa.Column("street", sa.String(length=256), nullable=True))
    op.add_column("payment_terminals", sa.Column("city", sa.String(length=64), nullable=True))
    op.add_column("payment_terminals", sa.Column("state", sa.String(length=64), nullable=True))
    op.add_column("payment_terminals", sa.Column("postcode", sa.String(length=16), nullable=True))
    op.add_column("payment_terminals", sa.Column("mcc", sa.String(length=8), nullable=True))


def downgrade() -> None:
    for col in ("mcc", "postcode", "state", "city", "street", "brand", "shop_name"):
        op.drop_column("payment_terminals", col)

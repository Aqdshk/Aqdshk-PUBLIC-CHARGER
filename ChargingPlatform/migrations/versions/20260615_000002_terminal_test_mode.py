"""add test_mode flag to payment_terminals

Lets ops mark a terminal as test-mode so the kiosk skips TNG, fakes
a 5-second "payment received", and fires OCPP RemoteStart for real
— end-to-end charging flow validation without burning real money or
needing TNG credentials.

Revision ID: 20260615_000002
Revises: 20260615_000001
Create Date: 2026-06-15 08:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260615_000002"
down_revision: Union[str, None] = "20260615_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_terminals",
        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("payment_terminals", "test_mode")

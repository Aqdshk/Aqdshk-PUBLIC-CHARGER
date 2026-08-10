"""add ocpp_transaction_id and evse_id to charging_sessions

OCPP 2.0.1 lets the charger mint the transaction id, and it is a string rather
than the integer the Central System assigns in 1.6. Widening transaction_id
would touch every billing, metering, idle-fee and OCPI query that reads it as
an int, so 2.0.1 sessions instead keep a generated integer for internal use
and record the charger's own id alongside it.

evse_id captures the extra level in 2.0.1's (evse, connector) addressing.

Both columns are nullable and stay NULL for every 1.6 session, so existing
rows and queries are unaffected.

Revision ID: 20260810_000001
Revises: 20260806_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_000001"
down_revision: Union[str, None] = "20260806_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("charging_sessions", sa.Column("ocpp_transaction_id", sa.String(64), nullable=True))
    op.add_column("charging_sessions", sa.Column("evse_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_charging_sessions_ocpp_transaction_id",
        "charging_sessions",
        ["ocpp_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_charging_sessions_ocpp_transaction_id", table_name="charging_sessions")
    op.drop_column("charging_sessions", "evse_id")
    op.drop_column("charging_sessions", "ocpp_transaction_id")

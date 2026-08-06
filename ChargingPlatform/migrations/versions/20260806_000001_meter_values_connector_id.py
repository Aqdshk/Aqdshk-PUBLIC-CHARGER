"""add connector_id to meter_values

MeterValues.req always carries connectorId, but the column did not exist so
the value was discarded on ingest. Readings could only be attributed to a gun
indirectly, via the session owning their transactionId — and clock-aligned
readings carry no transactionId at all, leaving them unattributable on a
multi-connector charger.

Backfills from charging_sessions where a transaction link exists. Rows with no
transaction stay NULL: their gun was never recorded and cannot be recovered.

Revision ID: 20260806_000001
Revises: 20260710_000003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_000001"
down_revision: Union[str, None] = "20260710_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meter_values", sa.Column("connector_id", sa.Integer(), nullable=True))
    op.create_index("ix_meter_values_connector_id", "meter_values", ["connector_id"])

    # Backfill what can be recovered from the owning session.
    op.execute(
        """
        UPDATE meter_values m
        JOIN charging_sessions s ON s.transaction_id = m.transaction_id
        SET m.connector_id = s.connector_id
        WHERE m.transaction_id IS NOT NULL
          AND m.connector_id IS NULL
          AND s.connector_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_meter_values_connector_id", table_name="meter_values")
    op.drop_column("meter_values", "connector_id")

"""record the OCPP version each charger speaks

Now that the server accepts both 1.6 and 2.0.1, the operator needs to know
which one a given charger negotiated — including while it is offline, which
rules out reading it live from the connection pool.

Backfills existing rows that have connected before as "1.6". That is a
statement of fact rather than a guess: the server advertised only ocpp1.6
until today, so anything that ever completed a handshake used it. Rows that
have never connected stay NULL.

Revision ID: 20260810_000002
Revises: 20260810_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_000002"
down_revision: Union[str, None] = "20260810_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chargers", sa.Column("ocpp_version", sa.String(16), nullable=True))
    op.execute(
        """
        UPDATE chargers
        SET ocpp_version = '1.6'
        WHERE ocpp_version IS NULL
          AND last_heartbeat IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("chargers", "ocpp_version")

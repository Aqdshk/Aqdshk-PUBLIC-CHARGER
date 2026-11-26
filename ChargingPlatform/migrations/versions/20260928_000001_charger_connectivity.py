"""charger connectivity: SIM identity and a connection event log

BootNotification's ICCID/IMSI (1.6) and modem block (2.0.1) were dropped, so
the dashboard could not say whether a charger is on a SIM. Connects and
disconnects were only in the rotated container log, so a charger losing its
link every two minutes looked merely "online".

Adds chargers.iccid / imsi / connectivity_override / last_remote_ip and the
charger_connection_events table. Additive only: nothing reads these until
the new code runs, and old code ignores them.

Revision ID: 20260928_000001
Revises: 20260904_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_000001"
down_revision: Union[str, None] = "20260904_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chargers", sa.Column("iccid", sa.String(32), nullable=True))
    op.add_column("chargers", sa.Column("imsi", sa.String(20), nullable=True))
    op.add_column("chargers", sa.Column("connectivity_override", sa.String(16), nullable=True))
    op.add_column("chargers", sa.Column("last_remote_ip", sa.String(64), nullable=True))

    op.create_table(
        "charger_connection_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("charge_point_id", sa.String(255), nullable=False),
        sa.Column("event", sa.String(16), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("close_code", sa.Integer(), nullable=True),
        sa.Column("close_reason", sa.String(255), nullable=True),
        sa.Column("remote_ip", sa.String(64), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("detail", sa.String(255), nullable=True),
    )
    op.create_index("ix_charger_connection_events_id", "charger_connection_events", ["id"])
    op.create_index("ix_conn_events_cp_at", "charger_connection_events", ["charge_point_id", "at"])


def downgrade() -> None:
    op.drop_index("ix_conn_events_cp_at", table_name="charger_connection_events")
    op.drop_index("ix_charger_connection_events_id", table_name="charger_connection_events")
    op.drop_table("charger_connection_events")
    op.drop_column("chargers", "last_remote_ip")
    op.drop_column("chargers", "connectivity_override")
    op.drop_column("chargers", "imsi")
    op.drop_column("chargers", "iccid")

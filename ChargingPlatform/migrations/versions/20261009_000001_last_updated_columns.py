"""Store last_updated on sessions and chargers.

OCPI filters Sessions, CDRs, Locations and Tariffs on last_updated: date_from
and date_to select rows changed inside a window, not rows that started inside
one. We filtered sessions on start_date_time, so once a session had begun a
partner could never pull its updates again. Voltality hit exactly that on
2026-10-09 and could not retrieve session changes after the start.

last_updated was computed at render time, which cannot be put in a WHERE
clause, so it becomes a real column maintained wherever the row changes.

Both columns hold Malaysia wall time, like every other clock on these tables.
The OCPI layer converts on the way out.

Revision ID: 20261009_000001
Revises: 20261006_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_000001"
down_revision: Union[str, None] = "20261006_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns(table)}


def _indexes(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    if "last_updated" not in _columns("charging_sessions"):
        op.add_column(
            "charging_sessions",
            sa.Column("last_updated", sa.DateTime(), nullable=True),
        )
    if "ix_charging_sessions_last_updated" not in _indexes("charging_sessions"):
        op.create_index(
            "ix_charging_sessions_last_updated",
            "charging_sessions",
            ["last_updated"],
        )

    if "last_updated" not in _columns("chargers"):
        op.add_column(
            "chargers",
            sa.Column("last_updated", sa.DateTime(), nullable=True),
        )
    if "ix_chargers_last_updated" not in _indexes("chargers"):
        op.create_index("ix_chargers_last_updated", "chargers", ["last_updated"])

    # Backfill from the best evidence each row already carries, newest first.
    # A partner asking for everything changed since the epoch must still see
    # historical rows, so none may be left NULL.
    op.execute(
        "UPDATE charging_sessions "
        "SET last_updated = COALESCE(unplugged_at, stop_time, start_time)"
    )
    op.execute(
        "UPDATE chargers "
        "SET last_updated = COALESCE(last_heartbeat, created_at)"
    )


def downgrade() -> None:
    if "ix_charging_sessions_last_updated" in _indexes("charging_sessions"):
        op.drop_index("ix_charging_sessions_last_updated", "charging_sessions")
    if "last_updated" in _columns("charging_sessions"):
        op.drop_column("charging_sessions", "last_updated")
    if "ix_chargers_last_updated" in _indexes("chargers"):
        op.drop_index("ix_chargers_last_updated", "chargers")
    if "last_updated" in _columns("chargers"):
        op.drop_column("chargers", "last_updated")

"""Record who ended a charge, not only what the charger called it.

OCPP 1.6 gives a reason on StopTransaction, but DC3001 answers "Other" both
when the driver ends the charge from the car and when the charge point
finishes by itself. Voltality's live test on 2026-11-25 ended two charges
from the vehicle and the dashboard could only say "reason: other".

Whether the platform asked for the stop is known in the process that asked
and nowhere else, so it is decided at StopTransaction and kept here.

Nullable, no backfill: a session that ended before this existed has no
honest value to give it, and guessing one would put a confident label on
something nobody recorded.

Revision ID: 20261125_000001
Revises: 20261116_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261125_000001"
down_revision: Union[str, None] = "20261116_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing() -> set:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns("charging_sessions")}


def upgrade() -> None:
    if "stop_initiator" not in _existing():
        op.add_column(
            "charging_sessions",
            sa.Column("stop_initiator", sa.String(16), nullable=True),
        )


def downgrade() -> None:
    if "stop_initiator" in _existing():
        op.drop_column("charging_sessions", "stop_initiator")

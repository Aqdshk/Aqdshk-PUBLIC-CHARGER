"""Freeze a session's prices onto the session.

A CDR is rebuilt from the session row every time a partner reads it, and it
took the rates from the charger as it stands today. Editing a charger's price
therefore rewrote every bill it had ever issued. Session 588 went to Voltality
carrying RM1.60 of parking; raising the idle rate from RM0.20 to RM0.30 a
minute would have made that same record read RM2.40 the next time they pulled
it, against a figure they had already settled. Our own terms promise the
opposite, that a price change "will never affect a session already in
progress".

Four nullable columns, filled at insert by a mapper event. Nothing is
backfilled: a null means "no snapshot", and the readers fall back to the
charger for those rows, which is exactly what they did before. Backfilling
today's rates onto old sessions would be a guess, and a wrong one wherever a
price has moved since.

Revision ID: 20261112_000001
Revises: 20261014_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261112_000001"
down_revision: Union[str, None] = "20261014_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = (
    ("tariff_per_kwh_at_start", sa.Numeric(8, 4)),
    ("idle_fee_enabled_at_start", sa.Boolean()),
    ("idle_fee_per_min_at_start", sa.Numeric(6, 2)),
    ("idle_grace_minutes_at_start", sa.Integer()),
)


def _existing() -> set:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns("charging_sessions")}


def upgrade() -> None:
    have = _existing()
    for name, type_ in _COLUMNS:
        if name not in have:
            op.add_column(
                "charging_sessions",
                sa.Column(name, type_, nullable=True),
            )


def downgrade() -> None:
    have = _existing()
    for name, _ in _COLUMNS:
        if name in have:
            op.drop_column("charging_sessions", name)

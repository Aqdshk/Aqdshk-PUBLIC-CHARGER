"""Put chargers.last_updated back into UTC.

20261009_000001 backfilled it from last_heartbeat and created_at, which are
UTC, but the mapper event that maintains it was writing Malaysia wall time. So
between the deploy and this fix the column held both: rows the migration filled
were UTC, rows touched since were eight hours ahead of that. The OCPI layer
then subtracted eight hours from all of them, which put every untouched charger
eight hours into the past.

The chargers table is UTC throughout, so the event now writes UTC and this
recomputes the column from the same UTC sources the first migration used. It
is deterministic rather than an adjustment, so running it twice is harmless.

Revision ID: 20261009_000002
Revises: 20261009_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_000002"
down_revision: Union[str, None] = "20261009_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "last_updated" not in {c["name"] for c in insp.get_columns("chargers")}:
        return

    chargers = sa.table(
        "chargers",
        sa.column("id", sa.Integer),
        sa.column("last_updated", sa.DateTime),
        sa.column("last_heartbeat", sa.DateTime),
        sa.column("created_at", sa.DateTime),
    )
    # Computed row by row rather than in SQL, because adding an interval is
    # spelled differently on MySQL and SQLite and this has to run on both.
    rows = bind.execute(
        sa.select(chargers.c.id, chargers.c.last_heartbeat, chargers.c.created_at)
    ).fetchall()
    for row in rows:
        stamp = row.last_heartbeat or row.created_at
        if stamp is None:
            continue
        bind.execute(
            chargers.update()
            .where(chargers.c.id == row.id)
            .values(last_updated=stamp)
        )


def downgrade() -> None:
    # Nothing to undo: the column keeps its values, only their zone was wrong.
    pass

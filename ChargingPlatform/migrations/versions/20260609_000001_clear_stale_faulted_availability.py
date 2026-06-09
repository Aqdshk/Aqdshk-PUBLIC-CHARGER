"""clear stale availability='faulted' on long-dead chargers

When a charger goes offline, the row's `availability` column is never
cleared — it stays at whatever the charger last reported (often
'faulted'). This caused the Analytics insights engine to report
"X chargers reporting faults" when the chargers had been dead for
weeks/months and weren't actionable.

One-shot cleanup: any charger whose last_heartbeat is older than 1 day
(or NULL) AND whose availability is still 'faulted' gets reset to
'unavailable'. Active fault state from currently-online chargers
is preserved.

Revision ID: 20260609_000001
Revises: 20260604_000001
Create Date: 2026-06-09 00:00:00
"""
from typing import Sequence, Union
from datetime import datetime, timedelta, timezone

from alembic import op


revision: str = "20260609_000001"
down_revision: Union[str, None] = "20260604_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        f"UPDATE chargers SET availability = 'unavailable' "
        f"WHERE availability = 'faulted' "
        f"AND (last_heartbeat IS NULL OR last_heartbeat < '{cutoff}')"
    )


def downgrade() -> None:
    # Cannot reverse — we don't track which rows we changed. No-op.
    pass

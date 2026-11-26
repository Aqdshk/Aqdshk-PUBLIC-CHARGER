"""Record when the cable was actually removed.

Idle minutes were measured from idle_started_at to stop_time. That works for a
driver who walks up and unplugs, because the charger only sends
StopTransaction then. It does not work for a stop issued from the app or by a
roaming partner: the transaction closes immediately, stop_time is the moment
of the request, and the car can sit in the bay for hours scoring zero idle
minutes. Billing has to run to the unplug, so the unplug needs a column.

Revision ID: 20261006_000001
Revises: 20260928_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_000001"
down_revision: Union[str, None] = "20260928_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("charging_sessions", "unplugged_at"):
        op.add_column(
            "charging_sessions",
            sa.Column("unplugged_at", sa.DateTime(), nullable=True),
        )

    # Sessions that closed before this change were all settled against
    # stop_time, so their idle figure is final. Backfilling unplugged_at from
    # stop_time marks them settled and keeps them out of the new hold window;
    # without it every historical CDR would look like it is still waiting for
    # a cable to come out and would stop being published.
    op.execute(
        "UPDATE charging_sessions "
        "SET unplugged_at = stop_time "
        "WHERE unplugged_at IS NULL AND stop_time IS NOT NULL"
    )


def downgrade() -> None:
    if _has_column("charging_sessions", "unplugged_at"):
        op.drop_column("charging_sessions", "unplugged_at")

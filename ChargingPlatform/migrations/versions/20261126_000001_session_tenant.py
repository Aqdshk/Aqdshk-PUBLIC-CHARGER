"""Freeze the fleet a charge belonged to onto the charge itself.

A session already froze its rates. It did not freeze its owner, so a report
filtered by tenant resolved `chargers.tenant` as it stands today, and moving
a charger between fleets carried every one of its past sessions along with
it. Re-running last month's invoice after a move returned different money.

Backfilled from the charger's current tenant, which is exact rather than a
guess: no charger on this platform has been moved between tenants yet, so
where a charger sits today is where it sat for every session it has. That
stops being true the moment the first charger moves, which is why the
backfill runs now and not later.

`tenants.billing_locked` is the second guard: a fleet being invoiced against
a live contract refuses a charger move unless the caller says outright that
it means to. It protects future earnings, not past invoices.

Revision ID: 20261126_000001
Revises: 20261125_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_000001"
down_revision: Union[str, None] = "20261125_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "tenant_at_start" not in _columns("charging_sessions"):
        op.add_column(
            "charging_sessions",
            sa.Column("tenant_at_start", sa.String(50), nullable=True),
        )
        op.create_index(
            "ix_charging_sessions_tenant_at_start",
            "charging_sessions",
            ["tenant_at_start"],
        )

    # A correlated UPDATE rather than a JOIN, so the same statement runs on
    # MySQL and on the SQLite the test suite uses.
    op.execute(
        """
        UPDATE charging_sessions
           SET tenant_at_start = (
                   SELECT tenant FROM chargers
                    WHERE chargers.id = charging_sessions.charger_id
               )
         WHERE tenant_at_start IS NULL
           AND charger_id IS NOT NULL
        """
    )

    if "billing_locked" not in _columns("tenants"):
        op.add_column(
            "tenants",
            sa.Column("billing_locked", sa.Boolean(), nullable=False,
                      server_default="0"),
        )


def downgrade() -> None:
    if "billing_locked" in _columns("tenants"):
        op.drop_column("tenants", "billing_locked")
    if "tenant_at_start" in _columns("charging_sessions"):
        try:
            op.drop_index("ix_charging_sessions_tenant_at_start",
                          table_name="charging_sessions")
        except Exception:
            pass
        op.drop_column("charging_sessions", "tenant_at_start")

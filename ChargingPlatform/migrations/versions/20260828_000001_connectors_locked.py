"""let an operator pin a charger's real gun count

number_of_connectors grows automatically from whatever the charger reports and
never shrinks. DC3001 physically has one gun, but its firmware announces a
second one and reports it Faulted, so the count was raised to 2 permanently.
That phantom gun was then published to roaming partners as an out-of-order
bay that does not exist.

This flag lets the operator say "this count is correct, ignore the firmware".

Revision ID: 20260828_000001
Revises: 20260826_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_000001"
down_revision: Union[str, None] = "20260826_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.add_column(
            sa.Column("connectors_locked", sa.Boolean(), nullable=False,
                      server_default=sa.text("0"))
        )


def downgrade() -> None:
    with op.batch_alter_table("chargers") as batch:
        batch.drop_column("connectors_locked")

"""add authorization_reference to charging_sessions

A roaming partner sends its own reference with StartSession and expects the
same value back when it polls the session, so it can tie the session it asked
for to the session we report. OCPI carries this as authorization_reference on
the Session and CDR objects. We had the field in the response model but
nowhere to keep the value, so it was always null and partners could not map
the sessions they started.

Revision ID: 20260821_000001
Revises: 20260812_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_000001"
down_revision: Union[str, None] = "20260812_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("charging_sessions") as batch:
        batch.add_column(sa.Column("authorization_reference", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("charging_sessions") as batch:
        batch.drop_column("authorization_reference")

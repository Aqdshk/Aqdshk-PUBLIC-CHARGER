"""store roaming partner credentials

The credentials handshake receives the partner's versions URL and the token we
must present when calling them, but we only wrote a truncated token to the log
and dropped the rest. That makes push impossible: we know where to send data
and cannot authenticate when we get there.

Revision ID: 20260821_000002
Revises: 20260821_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_000002"
down_revision: Union[str, None] = "20260821_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ocpi_partners",
        sa.Column("id", sa.Integer(), primary_key=True),
        # country_code + party_id identify a partner in OCPI, so that pair is
        # what a repeat handshake updates rather than duplicating.
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("party_id", sa.String(3), nullable=False),
        sa.Column("role", sa.String(16), nullable=True),
        sa.Column("business_name", sa.String(128), nullable=True),
        sa.Column("versions_url", sa.String(512), nullable=False),
        # The token we present when calling them. Secret.
        sa.Column("token", sa.String(256), nullable=False),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("country_code", "party_id", name="uq_ocpi_partner"),
    )


def downgrade() -> None:
    op.drop_table("ocpi_partners")

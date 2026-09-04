"""scope OCPI sessions and CDRs to the partner they belong to

The Sessions and CDRs endpoints returned every session on the platform to any
caller holding the single shared OCPI_TOKEN. Voltality reported seeing sessions
that were not theirs; in fact they could see all 345, including app and kiosk
sessions carrying our own customers' identifiers in cdr_token.uid.

Two columns close this:

  charging_sessions.ocpi_partner_id  which partner owns the session, NULL = ours
  ocpi_partners.token_inbound        the partner's Token C, so we can tell
                                     callers apart instead of trusting one
                                     shared secret

Backfill is deliberately absent. Existing rows keep ocpi_partner_id NULL and
the endpoints fall back to authorization_reference, which is the only evidence
we have about who started the older sessions.

Revision ID: 20260828_000002
Revises: 20260828_000001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_000002"
down_revision: Union[str, None] = "20260828_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ocpi_partners") as batch:
        batch.add_column(sa.Column("token_inbound", sa.String(256), nullable=True))

    with op.batch_alter_table("charging_sessions") as batch:
        batch.add_column(sa.Column("ocpi_partner_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_charging_sessions_ocpi_partner_id",
        "charging_sessions",
        ["ocpi_partner_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_charging_sessions_ocpi_partner_id", table_name="charging_sessions")
    with op.batch_alter_table("charging_sessions") as batch:
        batch.drop_column("ocpi_partner_id")
    with op.batch_alter_table("ocpi_partners") as batch:
        batch.drop_column("token_inbound")

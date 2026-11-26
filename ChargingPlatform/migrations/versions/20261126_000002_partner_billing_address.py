"""Give a roaming partner somewhere to keep the address we bill.

The settlement invoice addressed Voltality by business name alone, because
the business name was the only thing the OCPI credentials handshake gives
us. An invoice with no address on it is not one a finance team can file.

Jia Hui gave the address on 26 November 2026 when asked who we bill:
60 Paya Lebar Road, #05-08, Paya Lebar Square, Singapore 409051, invoiced
and paid in MYR. It is a fact about the partner, so it lives on the
partner row rather than in configuration, where a second partner would
have nowhere to put theirs.

Nullable: a partner that has not told us keeps an invoice with just its
name, which is what every invoice did until now.

Revision ID: 20261126_000002
Revises: 20261126_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_000002"
down_revision: Union[str, None] = "20261126_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns("ocpi_partners")}


def upgrade() -> None:
    if "billing_address" not in _columns():
        op.add_column(
            "ocpi_partners",
            sa.Column("billing_address", sa.String(512), nullable=True),
        )


def downgrade() -> None:
    if "billing_address" in _columns():
        op.drop_column("ocpi_partners", "billing_address")

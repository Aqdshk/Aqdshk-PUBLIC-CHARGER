"""Give a charger its own city and postcode.

OCPI publishes an address in parts. We filled the street line from the
charger's own row but took city and postal_code from OCPI_LOCATION_CITY and
OCPI_LOCATION_POSTAL, which are one value for the entire platform and had
never been changed from their defaults. So DC3001, whose row says Seksyen 15
in Shah Alam and whose coordinates are correct, was published as Kuala Lumpur
50000. A driver reading a partner app saw a street in one city labelled with
another.

Nullable, and nothing is backfilled: NULL keeps the old behaviour of reading
the settings, so a charger nobody has filled in is exactly as it was.

Revision ID: 20261116_000001
Revises: 20261112_000001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261116_000001"
down_revision: Union[str, None] = "20261112_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = (
    ("city", sa.String(100)),
    ("postal_code", sa.String(20)),
)


def _existing() -> set:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns("chargers")}


def upgrade() -> None:
    have = _existing()
    for name, type_ in _COLUMNS:
        if name not in have:
            op.add_column("chargers", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    have = _existing()
    for name, _ in _COLUMNS:
        if name in have:
            op.drop_column("chargers", name)

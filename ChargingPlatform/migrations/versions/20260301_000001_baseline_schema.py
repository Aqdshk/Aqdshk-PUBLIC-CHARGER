"""baseline schema marker

Revision ID: 20260301_000001
Revises:
Create Date: 2026-03-01 00:00:01
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260301_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline marker only. Existing databases should use:
    # alembic stamp 20260301_000001
    pass


def downgrade() -> None:
    pass

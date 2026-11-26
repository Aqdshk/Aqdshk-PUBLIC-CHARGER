"""vendor test portal: scoped vendor logins and an OCPP message log

A charger manufacturer integrating a new unit needs to see their charger
connect, drive a start and stop, and push a firmware update. The dashboard's
only login was an administrator's. Adds vendor_accounts (a login tied to a
list of charge point ids), vendor_sessions, and ocpp_message_log, which holds
raw frames for the chargers under test only.

Additive only. The application also creates missing tables at startup
(init_db), so each table is skipped here when it already exists; otherwise a
deploy that restarted before migrating would fail on "table already exists".

Revision ID: 20261014_000001
Revises: 20261009_000002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_000001"
down_revision: Union[str, None] = "20261009_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "vendor_accounts" not in existing:
        op.create_table(
            "vendor_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company", sa.String(120), nullable=False),
            sa.Column("contact_name", sa.String(120), nullable=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("charge_point_ids", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_login", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_vendor_accounts_id", "vendor_accounts", ["id"])
        op.create_index("ix_vendor_accounts_email", "vendor_accounts", ["email"], unique=True)

    if "vendor_sessions" not in existing:
        op.create_table(
            "vendor_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "vendor_id", sa.Integer(),
                sa.ForeignKey("vendor_accounts.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("token", sa.String(128), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_vendor_sessions_id", "vendor_sessions", ["id"])
        op.create_index("ix_vendor_sessions_vendor_id", "vendor_sessions", ["vendor_id"])
        op.create_index("ix_vendor_sessions_token", "vendor_sessions", ["token"], unique=True)

    if "ocpp_message_log" not in existing:
        op.create_table(
            "ocpp_message_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("charge_point_id", sa.String(255), nullable=False),
            sa.Column("at", sa.DateTime(), nullable=False),
            sa.Column("direction", sa.String(3), nullable=False),
            sa.Column("message_type", sa.Integer(), nullable=True),
            sa.Column("unique_id", sa.String(64), nullable=True),
            sa.Column("action", sa.String(64), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
        )
        op.create_index("ix_ocpp_message_log_id", "ocpp_message_log", ["id"])
        op.create_index("ix_ocpp_msg_cp_id", "ocpp_message_log", ["charge_point_id", "id"])


def downgrade() -> None:
    op.drop_table("ocpp_message_log")
    op.drop_table("vendor_sessions")
    op.drop_table("vendor_accounts")

"""totp two-factor login (M3-totp)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-25 22:10:15.166314+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "totp_recovery_codes",
        sa.Column("user_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("used_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_totp_recovery_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_totp_recovery_codes")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    with op.batch_alter_table("totp_recovery_codes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_totp_recovery_codes_user_id"), ["user_id"], unique=False
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("totp_secret_enc", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("totp_pending_enc", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "totp_enabled_at", app.infrastructure.database.types.UTCDateTime(), nullable=True
            )
        )
        batch_op.add_column(sa.Column("totp_last_step", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("totp_last_step")
        batch_op.drop_column("totp_enabled_at")
        batch_op.drop_column("totp_pending_enc")
        batch_op.drop_column("totp_secret_enc")

    op.drop_table("totp_recovery_codes")

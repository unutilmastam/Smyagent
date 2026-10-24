"""auth users sessions

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24 23:32:48.720566+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_login_attempts_ip_created", "login_attempts", ["ip_hash", "created_at"], unique=False
    )
    op.create_index(
        "ix_login_attempts_username_created",
        "login_attempts",
        ["username", "created_at"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "viewer", name="role", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sessions",
        sa.Column("user_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("last_seen_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index("ix_sessions_expires", "sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("login_attempts")

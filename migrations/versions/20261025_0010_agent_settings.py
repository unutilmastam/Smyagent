"""agent settings

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-25 10:26:52.112796+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_setting_versions",
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("changed_by", sa.String(length=80), nullable=False),
        sa.Column("note", sa.String(length=120), nullable=True),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_setting_versions")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_agent_setting_versions_module",
        "agent_setting_versions",
        ["module", "version"],
        unique=False,
    )
    op.create_table(
        "agent_settings",
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("module", name=op.f("pk_agent_settings")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("agent_settings")
    op.drop_table("agent_setting_versions")

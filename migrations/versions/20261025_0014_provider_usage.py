"""provider usage (M11)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-25 21:38:58.838077+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_usage",
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("ai", "search", name="usagekind", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("job_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_provider_usage_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_usage")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    with op.batch_alter_table("provider_usage", schema=None) as batch_op:
        batch_op.create_index(
            "ix_provider_usage_kind_created", ["kind", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_provider_usage_module_created", ["module", "created_at"], unique=False
        )


def downgrade() -> None:
    op.drop_table("provider_usage")

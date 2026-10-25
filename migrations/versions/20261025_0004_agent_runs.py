"""agent runs

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25 00:03:21.869467+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("job_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                name="agentrunstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("current_step", sa.String(length=191), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("started_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("heartbeat_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("finished_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_agent_runs_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_agent_runs_module_started", "agent_runs", ["module", "started_at"], unique=False
    )
    op.create_index("ix_agent_runs_started", "agent_runs", ["started_at"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("agent_runs")

"""runner runs and owner alerts (M10)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-25 18:52:58.403330+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_alerts",
        sa.Column("alert_key", sa.String(length=191), nullable=False),
        sa.Column("last_sent_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("pending", sa.Integer(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_owner_alerts")),
        sa.UniqueConstraint("alert_key", name=op.f("uq_owner_alerts_alert_key")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "runner_runs",
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "OK",
                "LOCKED",
                "STOPPED",
                "ERROR",
                name="runnerstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("started_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("finished_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("scheduled", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("retried", sa.Integer(), nullable=False),
        sa.Column("halted", sa.Integer(), nullable=False),
        sa.Column("requeued_stale", sa.Integer(), nullable=False),
        sa.Column("cleaned_up", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(length=120), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runner_runs")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index("ix_runner_runs_started", "runner_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_table("runner_runs")
    op.drop_table("owner_alerts")

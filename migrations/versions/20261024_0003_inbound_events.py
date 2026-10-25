"""inbound events

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24 23:52:43.399482+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbound_events",
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("received_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inbound_events")),
        sa.UniqueConstraint(
            "channel", "external_id", name=op.f("uq_inbound_events_channel_external_id")
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("inbound_events")

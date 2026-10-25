"""outreach events

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-25 14:33:24.485996+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_states",
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("complaints", sa.Integer(), nullable=False),
        sa.Column("changed_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("changed_by", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("channel", name=op.f("pk_channel_states")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "outreach_events",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("lead_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("proposal_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("email", "telegram", "phone", name="channel", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum("first", "follow_up", name="outreachkind", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "SENDING",
                "SENT",
                "UNKNOWN",
                "FAILED",
                "BOUNCED",
                "BLOCKED",
                "TASK",
                "DONE",
                "SKIPPED",
                name="outreachstatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(length=191), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("sent_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("replied_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("error", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_outreach_events_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_outreach_events_lead_id_leads"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            name=op.f("fk_outreach_events_proposal_id_proposals"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach_events")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_outreach_events_idempotency_key")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_outreach_events_channel_sent", "outreach_events", ["channel", "sent_at"], unique=False
    )
    op.create_index(
        "ix_outreach_events_recipient", "outreach_events", ["channel", "recipient"], unique=False
    )
    op.create_index(
        "ix_outreach_events_status", "outreach_events", ["status", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("outreach_events")
    op.drop_table("channel_states")

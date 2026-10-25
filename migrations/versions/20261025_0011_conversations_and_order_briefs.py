"""conversations and order briefs

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-25 11:07:40.860380+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppression_records",
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=191), nullable=False),
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column(
            "source_message_id", app.infrastructure.database.types.GUID(length=36), nullable=True
        ),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_suppression_records_company_id_companies"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppression_records")),
        sa.UniqueConstraint("channel", "value", name=op.f("uq_suppression_records_channel_value")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "conversations",
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("external_chat_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column(
            "language",
            sa.Enum("uz", "uz_cyrl", "ru", "en", name="language", native_enum=False, length=8),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.Enum(
                "OPEN",
                "BRIEF",
                "AWAITING_CONFIRMATION",
                "ORDER_CONFIRMED",
                "HANDOFF",
                "OPTED_OUT",
                name="conversationstate",
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("lead_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("disclosed_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column(
            "last_message_at", app.infrastructure.database.types.UTCDateTime(), nullable=False
        ),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_conversations_company_id_companies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_conversations_lead_id_leads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint(
            "channel", "external_chat_id", name=op.f("uq_conversations_channel_external_chat_id")
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_conversations_last_message", "conversations", ["last_message_at"], unique=False
    )
    op.create_table(
        "conversation_messages",
        sa.Column(
            "conversation_id", app.infrastructure.database.types.GUID(length=36), nullable=False
        ),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column(
            "direction",
            sa.Enum("in", "out", name="messagedirection", native_enum=False, length=4),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "RECEIVED",
                "DRAFT",
                "APPROVED",
                "SENT",
                "REJECTED",
                "BLOCKED",
                name="messagestatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=24), nullable=True),
        sa.Column("external_message_id", sa.String(length=64), nullable=True),
        sa.Column("has_disclosure", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("sent_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_messages")),
        sa.UniqueConstraint(
            "channel",
            "external_message_id",
            name=op.f("uq_conversation_messages_channel_external_message_id"),
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_conversation_messages_conv_created",
        "conversation_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_messages_status",
        "conversation_messages",
        ["status", "created_at"],
        unique=False,
    )
    op.create_table(
        "order_briefs",
        sa.Column(
            "conversation_id", app.infrastructure.database.types.GUID(length=36), nullable=False
        ),
        sa.Column("lead_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "COLLECTING",
                "AWAITING_CONFIRMATION",
                "CONFIRMED",
                "CANCELLED",
                name="briefstatus",
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("services", sa.JSON(), nullable=False),
        sa.Column("budget_note", sa.String(length=500), nullable=True),
        sa.Column("confirmed_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column(
            "confirmation_message_id",
            app.infrastructure.database.types.GUID(length=36),
            nullable=True,
        ),
        sa.Column("notified_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("owner_decision", sa.String(length=16), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["confirmation_message_id"],
            ["conversation_messages.id"],
            name=op.f("fk_order_briefs_confirmation_message_id_conversation_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_order_briefs_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_order_briefs_lead_id_leads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_briefs")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_order_briefs_status", "order_briefs", ["status", "updated_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("order_briefs")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("suppression_records")

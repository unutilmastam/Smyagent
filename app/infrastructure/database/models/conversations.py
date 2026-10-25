"""Client conversations (Mustafo), messages, Order Briefs and opt-out suppression."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.conversation import (
    BriefStatus,
    ConversationState,
    MessageDirection,
    MessageStatus,
)
from app.domain.persona import Language
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime, utcnow


class Conversation(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "conversations"

    channel: Mapped[str] = mapped_column(String(32))  # "telegram"
    external_chat_id: Mapped[str] = mapped_column(String(64))
    # Telegram first name only (minimal personal data, CLAUDE.md §10).
    display_name: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[Language] = mapped_column(enum_column(Language, length=8))
    state: Mapped[ConversationState] = mapped_column(
        enum_column(ConversationState, length=24), default=ConversationState.OPEN
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="SET NULL")
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("leads.id", ondelete="SET NULL")
    )
    disclosed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_message_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )

    __table_args__ = (
        UniqueConstraint("channel", "external_chat_id"),
        Index("ix_conversations_last_message", "last_message_at"),
    )


class ConversationMessage(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    channel: Mapped[str] = mapped_column(String(32))
    direction: Mapped[MessageDirection] = mapped_column(enum_column(MessageDirection, length=4))
    status: Mapped[MessageStatus] = mapped_column(enum_column(MessageStatus, length=16))
    text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(24))
    # Inbound: Telegram message id (idempotency). Outbound: none.
    external_message_id: Mapped[str | None] = mapped_column(String(64))
    has_disclosure: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(80))
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    note: Mapped[str | None] = mapped_column(String(200))  # why it is a draft / blocked

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint("channel", "external_message_id"),
        Index("ix_conversation_messages_conv_created", "conversation_id", "created_at"),
        Index("ix_conversation_messages_status", "status", "created_at"),
    )


class OrderBrief(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "order_briefs"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("leads.id", ondelete="SET NULL")
    )
    status: Mapped[BriefStatus] = mapped_column(
        enum_column(BriefStatus, length=24), default=BriefStatus.COLLECTING
    )
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    services: Mapped[list[str]] = mapped_column(JSON, default=list)
    budget_note: Mapped[str | None] = mapped_column(String(500))  # owner-only
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmation_message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("conversation_messages.id", ondelete="SET NULL")
    )
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    owner_decision: Mapped[str | None] = mapped_column(String(16))  # accepted|question|rejected

    __table_args__ = (Index("ix_order_briefs_status", "status", "updated_at"),)


class SuppressionRecord(UUIDPrimaryKey, Base):
    """Opt-out: this address is never contacted again (CLAUDE.md §4.6, §8.1)."""

    __tablename__ = "suppression_records"

    channel: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(191))  # chat id, email ...
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(200))
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (UniqueConstraint("channel", "value"),)

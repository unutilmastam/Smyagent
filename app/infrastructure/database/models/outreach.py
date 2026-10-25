"""Outbound outreach events (email sends, Telegram/phone owner tasks) and channel pause."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.outreach import Channel, OutreachKind, OutreachStatus
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime, utcnow


class OutreachEvent(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "outreach_events"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("leads.id", ondelete="SET NULL")
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("proposals.id", ondelete="SET NULL")
    )
    channel: Mapped[Channel] = mapped_column(enum_column(Channel, length=16))
    kind: Mapped[OutreachKind] = mapped_column(enum_column(OutreachKind, length=16))
    status: Mapped[OutreachStatus] = mapped_column(enum_column(OutreachStatus, length=16))
    recipient: Mapped[str] = mapped_column(String(191))  # public business address/handle/phone
    # One first message + one follow-up per company and channel, ever (retries reuse it).
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    replied_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(String(80))

    __table_args__ = (
        Index("ix_outreach_events_channel_sent", "channel", "sent_at"),
        Index("ix_outreach_events_status", "status", "created_at"),
        Index("ix_outreach_events_recipient", "channel", "recipient"),
    )


class ChannelState(Base):
    """Email auto-pause (bounces / complaints) and owner resume."""

    __tablename__ = "channel_states"

    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(200))
    complaints: Mapped[int] = mapped_column(default=0)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    changed_by: Mapped[str] = mapped_column(String(80))


__all__ = ["ChannelState", "OutreachEvent"]

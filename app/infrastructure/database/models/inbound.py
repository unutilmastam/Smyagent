"""Processed inbound events, for idempotency (CLAUDE.md §10: unique (channel, external id))."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, UUIDPrimaryKey
from app.infrastructure.database.types import UTCDateTime, utcnow


class InboundEvent(UUIDPrimaryKey, Base):
    __tablename__ = "inbound_events"

    # e.g. "telegram:owner_bot", later "telegram:client_bot", "email:inbox"
    channel: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (UniqueConstraint("channel", "external_id"),)

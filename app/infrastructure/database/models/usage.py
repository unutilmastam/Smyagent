"""Provider usage and cost records (CLAUDE.md §12.1 item 8, M11)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.budget import UsageKind
from app.infrastructure.database.base import Base, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime, utcnow


class ProviderUsage(UUIDPrimaryKey, Base):
    """One provider call (or batch): what it cost. No prompts, texts or personal data."""

    __tablename__ = "provider_usage"

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    kind: Mapped[UsageKind] = mapped_column(enum_column(UsageKind, length=16))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    module: Mapped[str] = mapped_column(String(32))
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("jobs.id", ondelete="SET NULL")
    )
    requests: Mapped[int] = mapped_column(Integer, default=1)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    # Estimated USD (provider price list in config); 0 for free providers.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))

    __table_args__ = (
        Index("ix_provider_usage_kind_created", "kind", "created_at"),
        Index("ix_provider_usage_module_created", "module", "created_at"),
    )

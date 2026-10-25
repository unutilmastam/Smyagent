"""Where the Discovery agent searches automatically (CLAUDE.md §8.1, §8.2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.types import UTCDateTime


class DiscoveryTarget(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "discovery_targets"

    country: Mapped[str] = mapped_column(String(2))
    city: Mapped[str] = mapped_column(String(64))
    # list of app.domain.discovery.Category values
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=7)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (UniqueConstraint("country", "city"),)

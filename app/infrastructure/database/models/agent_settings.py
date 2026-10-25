"""Owner-editable agent settings with a full version history (revert support)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, UUIDPrimaryKey
from app.infrastructure.database.types import UTCDateTime, utcnow


class AgentSetting(Base):
    """Current settings of one agent module (validated by app.domain.agent_settings)."""

    __tablename__ = "agent_settings"

    module: Mapped[str] = mapped_column(String(32), primary_key=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_by: Mapped[str] = mapped_column(String(80))


class AgentSettingVersion(UUIDPrimaryKey, Base):
    """Append-only snapshot of every saved version."""

    __tablename__ = "agent_setting_versions"

    module: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_by: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (Index("ix_agent_setting_versions_module", "module", "version"),)

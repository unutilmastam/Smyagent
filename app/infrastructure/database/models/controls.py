"""Kill switch state per agent module plus one global row (ADR-0006)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.agents import ControlState
from app.infrastructure.database.base import Base
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import UTCDateTime, utcnow


class AgentControl(Base):
    __tablename__ = "agent_controls"

    # One of app.domain.agents.AgentModule values, or "global".
    module: Mapped[str] = mapped_column(String(32), primary_key=True)
    state: Mapped[ControlState] = mapped_column(
        enum_column(ControlState), default=ControlState.ACTIVE
    )
    changed_by: Mapped[str] = mapped_column(String(80))
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    reason: Mapped[str | None] = mapped_column(String(500))

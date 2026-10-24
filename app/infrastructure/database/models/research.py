"""Research runs (one attempt to research a company)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime


class ResearchRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ResearchRun(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "research_runs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    status: Mapped[ResearchRunStatus] = mapped_column(
        enum_column(ResearchRunStatus), default=ResearchRunStatus.PENDING
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Short, secret-free error category/message; full details stay in logs.
    error_message: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (Index("ix_research_runs_company_created", "company_id", "created_at"),)

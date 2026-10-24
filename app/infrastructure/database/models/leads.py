"""Leads: one sales pipeline record per company."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.leads import LeadStage
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime, utcnow


class Lead(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "leads"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE"), unique=True
    )
    stage: Mapped[LeadStage] = mapped_column(enum_column(LeadStage), default=LeadStage.CANDIDATE)
    # Stage to return to when leaving PAUSED / ERROR.
    resume_stage: Mapped[LeadStage | None] = mapped_column(enum_column(LeadStage))
    stage_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (Index("ix_leads_stage_changed", "stage", "stage_changed_at"),)

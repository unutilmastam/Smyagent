"""Opportunities, lead scores (with explainable components) and scoring settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.types import GUID, UTCDateTime


class Opportunity(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "opportunities"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    service: Mapped[str] = mapped_column(String(32))  # app.domain.scoring.Service
    strength: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)  # finding keys
    # Findings this opportunity rests on (evidence trail).
    finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    __table_args__ = (Index("ix_opportunities_company", "company_id"),)


class LeadScore(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "lead_scores"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("leads.id", ondelete="SET NULL")
    )
    total: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(16))
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # snapshot
    missing: Mapped[list[str]] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime())

    components: Mapped[list[ScoreComponent]] = relationship(
        back_populates="score", cascade="all, delete-orphan", order_by="ScoreComponent.component"
    )

    __table_args__ = (
        Index("ix_lead_scores_company_computed", "company_id", "computed_at"),
        Index("ix_lead_scores_total", "total"),
    )


class ScoreComponent(UUIDPrimaryKey, Base):
    __tablename__ = "score_components"

    score_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("lead_scores.id", ondelete="CASCADE"), index=True
    )
    component: Mapped[str] = mapped_column(String(32))
    value: Mapped[int | None] = mapped_column(Integer)  # NULL = missing data
    weight: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(String(300))

    score: Mapped[LeadScore] = relationship(back_populates="components")


class ScoringSettings(Base):
    """Single row (key='default') of owner-adjustable weights and threshold."""

    __tablename__ = "scoring_settings"

    key: Mapped[str] = mapped_column(String(16), primary_key=True)
    weights: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    qualify_threshold: Mapped[int] = mapped_column(Integer, default=55)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    updated_by: Mapped[str | None] = mapped_column(String(80))

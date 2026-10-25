"""Website audits and research findings (evidence with source, time and confidence)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.audit import Kind
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime


class WebsiteAudit(UUIDPrimaryKey, Timestamps, Base):
    """One deterministic audit of a homepage. Raw HTML is never stored (CLAUDE.md §10)."""

    __tablename__ = "website_audits"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(String(2048))
    final_url: Mapped[str | None] = mapped_column(String(2048))
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_ms: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(300))
    score: Mapped[int | None] = mapped_column(Integer)
    # [{key, severity, evidence}] — see app.domain.audit.Check
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    text_excerpt: Mapped[str | None] = mapped_column(Text)
    error_category: Mapped[str | None] = mapped_column(String(32))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())

    __table_args__ = (Index("ix_website_audits_company_fetched", "company_id", "fetched_at"),)


class ResearchFinding(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "research_findings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="SET NULL")
    )
    key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[Kind] = mapped_column(enum_column(Kind, length=16))
    statement: Mapped[str] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime())

    __table_args__ = (
        Index("ix_research_findings_company", "company_id", "retrieved_at"),
        Index("ix_research_findings_key", "key"),
    )

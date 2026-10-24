"""Companies, their domains and the sources they were discovered from."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.companies import ResearchState
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime


class Company(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(191))
    country: Mapped[str] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(191))
    normalized_city: Mapped[str | None] = mapped_column(String(191))
    industry: Mapped[str | None] = mapped_column(String(191))
    research_state: Mapped[ResearchState] = mapped_column(
        enum_column(ResearchState), default=ResearchState.NEW
    )
    notes: Mapped[str | None] = mapped_column(Text)

    domains: Mapped[list[CompanyDomain]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    sources: Mapped[list[CompanySource]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Duplicate detection on normalized name + city (not unique: same name may
        # legitimately exist in one city; dedup is a review step, not a constraint).
        Index("ix_companies_name_city", "normalized_name", "normalized_city"),
        Index("ix_companies_country_state", "country", "research_state"),
    )


class CompanyDomain(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "company_domains"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    # Normalized bare host (see app.domain.companies.normalize_domain); globally unique.
    domain: Mapped[str] = mapped_column(String(191), unique=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="domains")


class CompanySource(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "company_sources"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    # manual | csv | fixture | 2gis | google_places | yandex | registry ...
    source_type: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(String(191))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime())
    # Fixtures can never be presented as real discoveries (CLAUDE.md §11).
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="sources")

    __table_args__ = (Index("ix_company_sources_type_external", "source_type", "external_id"),)

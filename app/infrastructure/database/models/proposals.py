"""Offers (versioned, Quality Gate verdicts) and explicit owner approval requests."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.persona import Language
from app.domain.proposals import ApprovalStatus, ProposalStatus
from app.domain.quality_gate import Verdict
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime


class Proposal(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "proposals"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("leads.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[ProposalStatus] = mapped_column(
        enum_column(ProposalStatus, length=24), default=ProposalStatus.DRAFT
    )
    language: Mapped[Language] = mapped_column(enum_column(Language, length=8))
    current_version: Mapped[int] = mapped_column(Integer, default=1)

    versions: Mapped[list[ProposalVersion]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="ProposalVersion.number.desc()",
    )

    __table_args__ = (Index("ix_proposals_status_updated", "status", "updated_at"),)


class ProposalVersion(UUIDPrimaryKey, Timestamps, Base):
    """Immutable text of one version; edits create a new version."""

    __tablename__ = "proposal_versions"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("proposals.id", ondelete="CASCADE")
    )
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    services: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Evidence trail: the research findings the offer's observations rest on.
    finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    observation_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)  # i18n keys
    open_questions: Mapped[list[str]] = mapped_column(JSON, default=list)  # i18n keys
    created_by: Mapped[str] = mapped_column(String(80))
    gate_verdict: Mapped[Verdict | None] = mapped_column(enum_column(Verdict, length=16))
    # [{code, severity, detail}] — see app.domain.quality_gate.Issue
    gate_issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    gate_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    proposal: Mapped[Proposal] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("proposal_id", "number"),)


class ApprovalRequest(UUIDPrimaryKey, Timestamps, Base):
    """Explicit record of every owner decision (CLAUDE.md §9 rules)."""

    __tablename__ = "approval_requests"

    entity_type: Mapped[str] = mapped_column(String(32))  # "proposal"
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID())
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[ApprovalStatus] = mapped_column(
        enum_column(ApprovalStatus, length=16), default=ApprovalStatus.PENDING
    )
    requested_by: Mapped[str] = mapped_column(String(80))
    decided_by: Mapped[str | None] = mapped_column(String(80))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("ix_approval_requests_entity", "entity_type", "entity_id"),
        Index("ix_approval_requests_status", "status", "created_at"),
    )

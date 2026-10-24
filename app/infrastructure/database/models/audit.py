"""Workflow transitions and security-relevant audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, UUIDPrimaryKey
from app.infrastructure.database.types import GUID, UTCDateTime, utcnow


class WorkflowEvent(UUIDPrimaryKey, Base):
    """Append-only record of every state transition (CLAUDE.md §9)."""

    __tablename__ = "workflow_events"

    entity_type: Mapped[str] = mapped_column(String(32))  # company | lead | job ...
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID())
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(80))  # user:<id> | agent:<module> | system:<name>
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (
        Index("ix_workflow_events_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_workflow_events_created", "created_at"),
    )


class AuditLog(UUIDPrimaryKey, Base):
    """Append-only audit trail: logins, approvals, setting and control changes."""

    __tablename__ = "audit_logs"

    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    # Must never contain secrets; validated by the repository.
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (
        Index("ix_audit_logs_created", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

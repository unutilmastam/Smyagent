"""Workflow events and audit log writers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import redact
from app.domain.actors import Actor
from app.infrastructure.database.models import AuditLog, WorkflowEvent


class WorkflowEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        from_state: str | None,
        to_state: str,
        actor: Actor,
        reason: str | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            actor=str(actor),
            reason=reason[:500] if reason else None,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def history(self, entity_type: str, entity_id: uuid.UUID) -> list[WorkflowEvent]:
        stmt = (
            select(WorkflowEvent)
            .where(WorkflowEvent.entity_type == entity_type, WorkflowEvent.entity_id == entity_id)
            .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
        )
        return list(self.session.scalars(stmt))


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        actor: Actor,
        action: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor=str(actor),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            # Same redaction as logs: sensitive keys and inline secrets never stored.
            details=redact(details) if details is not None else None,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

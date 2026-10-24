"""Idempotent registration of inbound events (webhook retries are processed once)."""

from __future__ import annotations

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.models import InboundEvent
from app.infrastructure.database.types import utcnow


class InboundEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, channel: str, external_id: str) -> bool:
        """Record the event; False if it was already processed (unique constraint)."""
        try:
            with self.session.begin_nested():
                self.session.execute(
                    insert(InboundEvent).values(
                        channel=channel, external_id=external_id, received_at=utcnow()
                    )
                )
        except IntegrityError:
            return False
        return True

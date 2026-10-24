"""Agent kill-switch state (ADR-0006)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.agents import GLOBAL_CONTROL, AgentModule, ControlState, effective_state
from app.infrastructure.database.models import AgentControl
from app.infrastructure.database.types import utcnow

ALL_CONTROL_KEYS = (GLOBAL_CONTROL, *(m.value for m in AgentModule))


class AgentControlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_rows(self, actor: Actor) -> None:
        """Create missing rows (ACTIVE). Idempotent."""
        existing = set(self.session.scalars(select(AgentControl.module)))
        for key in ALL_CONTROL_KEYS:
            if key not in existing:
                self.session.add(
                    AgentControl(
                        module=key,
                        state=ControlState.ACTIVE,
                        changed_by=str(actor),
                        reason="initial",
                    )
                )
        self.session.flush()

    def states(self) -> dict[str, ControlState]:
        rows = self.session.scalars(select(AgentControl))
        return {row.module: row.state for row in rows}

    def effective(self, module: AgentModule) -> ControlState:
        """State a module must obey. Missing rows are treated as STOPPED (fail closed)."""
        states = self.states()
        return effective_state(
            states.get(GLOBAL_CONTROL, ControlState.STOPPED),
            states.get(module.value, ControlState.STOPPED),
        )

    def set_state(
        self, key: str, state: ControlState, actor: Actor, reason: str | None = None
    ) -> AgentControl:
        if key not in ALL_CONTROL_KEYS:
            raise ValueError(f"unknown agent control: {key!r}")
        row = self.session.get(AgentControl, key)
        if row is None:
            row = AgentControl(module=key)
            self.session.add(row)
        row.state = state
        row.changed_by = str(actor)
        row.changed_at = utcnow()
        row.reason = reason[:500] if reason else None
        self.session.flush()
        return row

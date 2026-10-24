"""Context every logged-in page needs (user, CSRF token, global agent state)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.agents import GLOBAL_CONTROL, ControlState
from app.infrastructure.repositories.controls import AgentControlRepository
from app.web.auth import CurrentUser


def layout_context(session: Session, user: CurrentUser) -> dict[str, object]:
    state = AgentControlRepository(session).states().get(GLOBAL_CONTROL, ControlState.STOPPED)
    return {"user": user, "csrf_token": user.csrf_token, "global_state": state.value}

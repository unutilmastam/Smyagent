"""Control Center API: snapshot (polled every 3-5 s) and state changes (owner only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_database
from app.application.control_snapshot import ControlSnapshotService
from app.application.controls import AgentControlService, describe_change
from app.application.office import OfficeSnapshotService
from app.core.config import Settings, get_settings
from app.domain.actors import Actor
from app.domain.agents import ControlState
from app.infrastructure.database import Database
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user

router = APIRouter(prefix="/control", tags=["control"])


@router.get("/snapshot")
def snapshot(
    _: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    with database.transaction() as session:
        snap = ControlSnapshotService(session).build(
            timezone=settings.default_timezone, ai_budget_today=settings.daily_ai_budget_usd
        )
    return snap.to_json()


@router.get("/office")
def office(
    _: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Virtual Office state (CLAUDE.md §13A.3): every animation comes from these facts."""
    with database.transaction() as session:
        return OfficeSnapshotService(session).build(
            timezone=settings.default_timezone, ai_budget_today=settings.daily_ai_budget_usd
        )


class StateChange(BaseModel):
    state: ControlState
    reason: str = Field(default="", max_length=200)


@router.post("/{key}")
def set_state(
    key: str,
    body: StateChange,
    request: Request,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> dict[str, Any]:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    with database.transaction() as session:
        change = AgentControlService(session).set_state(
            key, body.state, Actor.user(str(user.id)), body.reason or "api"
        )
    request.app.state.notifier.notify("API: " + describe_change(change))
    return {
        "key": change.key,
        "previous": change.previous.value,
        "state": change.state.value,
        "cancelled_running": change.cancelled_running,
        "cancelled_outbound": change.cancelled_outbound,
    }

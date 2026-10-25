"""Agent Control Center pages (CLAUDE.md §13A): live graph, activity feed, controls."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.api.deps import get_database
from app.application.control_snapshot import ControlSnapshotService, Snapshot
from app.application.controls import AgentControlService, describe_change
from app.core.config import Settings, get_settings
from app.domain.actors import Actor
from app.domain.agents import GRAPH_EDGES, PIPELINE, AgentModule, ControlState
from app.domain.errors import DomainError
from app.infrastructure.database import Database
from app.infrastructure.repositories.controls import ALL_CONTROL_KEYS
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user
from app.web.layout import layout_context
from app.web.templating import is_htmx_partial, render

router = APIRouter(include_in_schema=False)

# SVG layout: orchestrator on top, pipeline as a vertical flow (fits a 375 px screen).
NODE_W, NODE_H, GAP = 260, 46, 22
X0, Y0 = 50, 74


def _layout() -> dict[str, tuple[int, int]]:
    positions = {AgentModule.ORCHESTRATOR.value: (X0, 10)}
    for i, module in enumerate(PIPELINE):
        positions[module.value] = (X0, Y0 + i * (NODE_H + GAP))
    return positions


POSITIONS = _layout()
GRAPH_HEIGHT = Y0 + len(PIPELINE) * (NODE_H + GAP)


def build_snapshot(database: Database, settings: Settings) -> tuple[Snapshot, dict[str, object]]:
    with database.transaction() as session:
        snapshot = ControlSnapshotService(session).build(
            timezone=settings.default_timezone, ai_budget_today=settings.daily_ai_budget_usd
        )
    return snapshot, {
        "snap": snapshot,
        "positions": POSITIONS,
        "edges": [(a.value, b.value) for a, b in GRAPH_EDGES],
        "node_w": NODE_W,
        "node_h": NODE_H,
        "graph_height": GRAPH_HEIGHT,
        "modules_order": [AgentModule.ORCHESTRATOR.value] + [m.value for m in PIPELINE],
    }


@router.get("/control", response_class=HTMLResponse)
def control_page(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    _, context = build_snapshot(database, settings)
    if is_htmx_partial(request):
        context["user"] = user
        context["csrf_token"] = user.csrf_token
        return render(request, "control/_live.html", context)
    with database.transaction() as session:
        context.update(layout_context(session, user))
    context["changed"] = request.query_params.get("changed") == "1"
    return render(request, "control/index.html", context)


@router.post("/control/{key}")
def change_state(
    request: Request,
    key: str,
    state: Annotated[str, Form(max_length=16)],
    reason: Annotated[str, Form(max_length=200)] = "",
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    if key not in ALL_CONTROL_KEYS:
        raise DomainError("unknown agent")
    try:
        target = ControlState(state)
    except ValueError as exc:
        raise DomainError("unknown state") from exc
    with database.transaction() as session:
        change = AgentControlService(session).set_state(
            key, target, Actor.user(str(user.id)), reason or f"dashboard ({user.username})"
        )
    request.app.state.notifier.notify("Dashboard: " + describe_change(change))
    return RedirectResponse("/control?changed=1", status_code=303)

"""Agent settings: hub, per-agent form, versions with restore and reset (owner edits)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select

from app.api.deps import get_database
from app.application.agent_settings import AgentSettingsService, values_from_form
from app.domain.actors import Actor
from app.domain.agent_settings import EDITABLE_LANGUAGES, HARD_RULES
from app.domain.agents import AgentModule
from app.domain.errors import DomainError
from app.domain.proposals import FRAME_PARTS, default_service_text, default_text
from app.domain.scoring import Service
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentSetting
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)


def _module(raw: str) -> AgentModule | None:
    try:
        return AgentModule(raw)
    except ValueError:
        return None


@router.get("/settings", response_class=HTMLResponse)
def settings_hub(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        rows = {row.module: row for row in session.scalars(select(AgentSetting))}
        context = layout_context(session, user)
    context.update({"modules": list(AgentModule), "rows": rows, "hard_rules": HARD_RULES})
    return render(request, "settings/index.html", context)


def _render_form(
    request: Request,
    user: CurrentUser,
    database: Database,
    module: AgentModule,
    *,
    errors: tuple[str, ...] = (),
    status: int = 200,
) -> Response:
    with database.transaction() as session:
        repo = AgentSettingsRepository(session)
        context = layout_context(session, user)
        context.update(
            {
                "module": module,
                "s": repo.get(module),
                "version": repo.current_version(module),
                "history": repo.history(module),
                "errors": errors,
                "saved": request.query_params.get("saved"),
                "hard_rules": HARD_RULES,
                "services": list(Service),
                "languages": EDITABLE_LANGUAGES,
                "frame_parts": FRAME_PARTS,
                "default_text": default_text,
                "default_service_text": default_service_text,
            }
        )
        return render(request, "settings/agent.html", context, status=status)


@router.get("/settings/agents/{key}", response_class=HTMLResponse)
def agent_settings_page(
    request: Request,
    key: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    module = _module(key)
    if module is None:
        with database.transaction() as session:
            context = layout_context(session, user)
        context["title_key"] = "error.not_found"
        return render(request, "error.html", context, status=404)
    return _render_form(request, user, database, module)


def _owner_module(user: CurrentUser, key: str) -> AgentModule:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    module = _module(key)
    if module is None:
        raise DomainError("unknown agent")
    return module


@router.post("/settings/agents/{key}")
async def save_agent_settings(
    request: Request,
    key: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    module = _owner_module(user, key)
    form = await request.form()
    flat = {k: str(v) for k, v in form.items()}
    values = values_from_form(module, flat, lambda name: [str(v) for v in form.getlist(name)])
    with database.transaction() as session:
        result = AgentSettingsService(session).save(module, values, Actor.user(str(user.id)))
    if not result.ok:
        return _render_form(request, user, database, module, errors=result.errors, status=422)
    return RedirectResponse(f"/settings/agents/{module.value}?saved={result.version}", 303)


@router.post("/settings/agents/{key}/reset")
def reset_agent_settings(
    key: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    module = _owner_module(user, key)
    with database.transaction() as session:
        version = AgentSettingsRepository(session).reset(module, Actor.user(str(user.id)))
    return RedirectResponse(f"/settings/agents/{module.value}?saved={version}", 303)


@router.post("/settings/agents/{key}/restore/{version_id}")
def restore_agent_settings(
    key: str,
    version_id: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    module = _owner_module(user, key)
    try:
        parsed = uuid.UUID(version_id)
    except ValueError:
        raise DomainError("settings version not found") from None
    with database.transaction() as session:
        version = AgentSettingsRepository(session).restore(module, parsed, Actor.user(str(user.id)))
    return RedirectResponse(f"/settings/agents/{module.value}?saved={version}", 303)

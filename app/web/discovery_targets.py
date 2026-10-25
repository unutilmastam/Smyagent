"""Automatic discovery settings page (`/discovery`): targets, status, "search now"."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app.api.deps import get_database
from app.core.config import Settings, get_settings
from app.domain.actors import Actor
from app.domain.agents import AgentModule
from app.domain.companies import normalize_city, normalize_country
from app.domain.discovery import Category, TargetSpec, parse_categories
from app.domain.errors import DomainError
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentRun, Company, DiscoveryTarget
from app.infrastructure.repositories.workflow import AuditLogRepository
from app.jobs.tasks.discovery import enqueue_due_targets
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_owner
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)


@router.get("/discovery", response_class=HTMLResponse)
def discovery_page(
    request: Request,
    user: CurrentUser = Depends(require_owner),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        targets = list(
            session.scalars(select(DiscoveryTarget).order_by(DiscoveryTarget.created_at))
        )
        found = dict(
            session.execute(
                select(Company.normalized_city, func.count()).group_by(Company.normalized_city)
            )
            .tuples()
            .all()
        )
        runs = list(
            session.scalars(
                select(AgentRun)
                .where(AgentRun.module == AgentModule.DISCOVERY.value)
                .order_by(AgentRun.started_at.desc())
                .limit(10)
            )
        )
        context = layout_context(session, user)
    context.update(
        {
            "targets": targets,
            "found": {t.id: found.get(normalize_city(t.city), 0) for t in targets},
            "runs": runs,
            "categories": list(Category),
            "provider": settings.search_provider.strip().lower(),
            "queued": request.query_params.get("queued"),
            "error": request.query_params.get("error"),
        }
    )
    return render(request, "discovery.html", context)


def _owner(user: CurrentUser) -> Actor:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    return Actor.user(str(user.id))


@router.post("/discovery/targets")
def add_target(
    country: Annotated[str, Form(max_length=8)],
    city: Annotated[str, Form(max_length=64)],
    categories: Annotated[list[str] | None, Form()] = None,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    actor = _owner(user)
    try:
        spec = TargetSpec(
            country=normalize_country(country),
            city=city.strip(),
            categories=parse_categories(categories or []),
        )
    except DomainError as exc:
        return RedirectResponse(f"/discovery?error={str(exc)[:80]}", status_code=303)
    with database.transaction() as session:
        existing = session.scalars(
            select(DiscoveryTarget).where(
                DiscoveryTarget.country == spec.country, DiscoveryTarget.city == spec.city
            )
        ).first()
        target = existing or DiscoveryTarget(country=spec.country, city=spec.city)
        target.categories = [c.value for c in spec.categories]
        target.enabled = True
        session.add(target)
        AuditLogRepository(session).add(
            actor=actor,
            action="discovery.target_saved",
            details={"country": spec.country, "city": spec.city},
        )
    return RedirectResponse("/discovery", status_code=303)


@router.post("/discovery/targets/{target_id}/toggle")
def toggle_target(
    target_id: uuid.UUID,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    actor = _owner(user)
    with database.transaction() as session:
        target = session.get(DiscoveryTarget, target_id)
        if target is None:
            raise DomainError("target not found")
        target.enabled = not target.enabled
        AuditLogRepository(session).add(
            actor=actor,
            action="discovery.target_toggled",
            details={"city": target.city, "enabled": target.enabled},
        )
    return RedirectResponse("/discovery", status_code=303)


@router.post("/discovery/targets/{target_id}/run")
def run_target_now(
    target_id: uuid.UUID,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    actor = _owner(user)
    with database.transaction() as session:
        if session.get(DiscoveryTarget, target_id) is None:
            raise DomainError("target not found")
        queued = enqueue_due_targets(session, force_target=target_id)
        AuditLogRepository(session).add(
            actor=actor,
            action="discovery.run_now",
            details={"target": str(target_id), "jobs": queued},
        )
    return RedirectResponse(f"/discovery?queued={queued}", status_code=303)

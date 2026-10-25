"""Outreach page (email queue, Telegram one-tap and phone tasks) and public unsubscribe."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy import select

from app.api.deps import get_database
from app.application.outreach import OutreachService
from app.core.config import Settings, get_settings
from app.domain.actors import Actor
from app.domain.errors import DomainError
from app.domain.outreach import Channel, OutreachStatus, verify_unsubscribe_token
from app.infrastructure.database import Database
from app.infrastructure.database.models import Company, OutreachEvent
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)
ACTIONS = ("done", "skip", "replied")


@router.get("/outreach", response_class=HTMLResponse)
def outreach_page(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        service = OutreachService(session, settings)
        stats = service.today()
        events = list(
            session.scalars(
                select(OutreachEvent).order_by(OutreachEvent.created_at.desc()).limit(100)
            )
        )
        names = {
            c.id: c.name
            for c in session.scalars(
                select(Company).where(Company.id.in_({e.company_id for e in events}))
            )
        }
        context = layout_context(session, user)
    tasks = [e for e in events if e.status is OutreachStatus.TASK]
    context.update(
        {
            "stats": stats,
            "telegram_tasks": [e for e in tasks if e.channel is Channel.TELEGRAM],
            "phone_tasks": [e for e in tasks if e.channel is Channel.PHONE],
            "emails": [e for e in events if e.channel is Channel.EMAIL],
            "done": [e for e in events if e.status is OutreachStatus.DONE],
            "names": names,
            "email_enabled": settings.email_enabled,
            "sending_enabled": settings.outbound_sending_enabled,
            "saved": request.query_params.get("saved"),
            "error": request.query_params.get("error"),
        }
    )
    return render(request, "outreach.html", context)


@router.post("/outreach/events/{event_id}/{action}")
def task_action(
    event_id: str,
    action: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    try:
        parsed = uuid.UUID(event_id)
    except ValueError:
        parsed = None
    if parsed is None or action not in ACTIONS:
        return PlainTextResponse("Not found", status_code=404)
    actor = Actor.user(str(user.id))
    try:
        with database.transaction() as session:
            service = OutreachService(session, settings)
            if action == "done":
                service.mark_task_done(parsed, actor)
            elif action == "skip":
                service.skip_task(parsed, actor)
            else:
                service.mark_replied(parsed, actor)
    except DomainError as exc:
        return RedirectResponse(f"/outreach?error={quote(str(exc)[:150])}", status_code=303)
    return RedirectResponse(f"/outreach?saved={action}", status_code=303)


@router.post("/outreach/email/resume")
def resume_email(
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    with database.transaction() as session:
        OutreachService(session, settings).resume_email(Actor.user(str(user.id)))
    return RedirectResponse("/outreach?saved=resume", status_code=303)


# -- public: one-click unsubscribe (no login; the signed token is the authorization) ----


def _address(settings: Settings, token: str) -> str | None:
    return verify_unsubscribe_token(settings.app_secret_key.get_secret_value() or "dev", token)


@router.get("/u/{token}", response_class=HTMLResponse)
def unsubscribe_page(
    request: Request,
    token: str,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    # GET never changes anything (mail scanners prefetch links); the button POSTs.
    address = _address(settings, token)
    status = 200 if address else 404
    return render(
        request, "unsubscribe.html", {"token": token, "valid": bool(address), "done": False}, status
    )


@router.post("/u/{token}", response_class=HTMLResponse)
def unsubscribe(
    request: Request,
    token: str,
    settings: Settings = Depends(get_settings),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    """Form button or RFC 8058 one-click POST from the mail client."""
    address = _address(settings, token)
    if address is None:
        return render(request, "unsubscribe.html", {"valid": False, "done": False}, 404)
    with database.transaction() as session:
        OutreachService(session, settings).unsubscribe(address, reason="unsubscribe link")
    return render(request, "unsubscribe.html", {"valid": True, "done": True})

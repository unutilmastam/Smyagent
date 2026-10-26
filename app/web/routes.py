"""Dashboard pages: login, logout, home."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app.api.deps import get_database
from app.application.auth import (
    TOTP_CHALLENGE_LIFETIME,
    AuthError,
    AuthService,
    ThrottledError,
    TotpChallenge,
)
from app.application.automation import cron_view
from app.core.config import Settings, get_settings
from app.core.security import new_token, tokens_equal
from app.domain.auth import SESSION_ABSOLUTE_LIFETIME
from app.domain.jobs import JobStatus
from app.domain.proposals import ProposalStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import Company, Job, Lead, Proposal
from app.web.auth import (
    LOGIN_CSRF_COOKIE,
    SESSION_COOKIE,
    TOTP_CHALLENGE_COOKIE,
    CurrentUser,
    cookie_secure,
    get_optional_user,
    require_csrf,
    require_user,
    safe_next_path,
)
from app.web.conversations import open_order_count
from app.web.i18n import LANG_COOKIE, normalize_language
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)


def _login_page(
    request: Request,
    settings: Settings,
    *,
    next_path: str,
    error: str | None = None,
    status: int = 200,
) -> Response:
    csrf = new_token()
    response = render(
        request, "login.html", {"csrf_token": csrf, "next": next_path, "error": error}, status
    )
    response.set_cookie(
        LOGIN_CSRF_COOKIE,
        csrf,
        max_age=3600,
        httponly=True,
        samesite="strict",
        secure=cookie_secure(settings),
        path="/login",
    )
    return response


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    next: str | None = None,
    user: CurrentUser | None = Depends(get_optional_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    if user is not None:
        return RedirectResponse(safe_next_path(next), status_code=303)
    return _login_page(request, settings, next_path=safe_next_path(next))


@router.post("/login")
def login_submit(
    request: Request,
    username: Annotated[str, Form(max_length=64)],
    password: Annotated[str, Form(max_length=256)],
    csrf_token: Annotated[str, Form(max_length=128)] = "",
    next: Annotated[str, Form(max_length=512)] = "/",
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    next_path = safe_next_path(next)
    if not tokens_equal(csrf_token, request.cookies.get(LOGIN_CSRF_COOKIE)):
        return _login_page(
            request,
            settings,
            next_path=next_path,
            error="login.error.stale",
            status=400,
        )
    client_ip = request.client.host if request.client else "unknown"
    error: str | None = None
    status = 200
    challenge: TotpChallenge | None = None
    token = ""
    with database.transaction() as session:
        service = AuthService(session, secret_key=settings.app_secret_key.get_secret_value())
        # Failures are caught inside the transaction so the attempt record is committed.
        try:
            result = service.login(username, password, client_ip=client_ip)
            if isinstance(result, TotpChallenge):
                challenge = result
            else:
                token = result.token
        except ThrottledError:
            error, status = "login.error.throttled", 429
        except AuthError:
            error, status = "login.error.invalid", 401
    if error is not None:
        return _login_page(request, settings, next_path=next_path, error=error, status=status)
    if challenge is not None:
        response = RedirectResponse(
            f"/login/totp?next={quote(next_path, safe='/')}", status_code=303
        )
        response.set_cookie(
            TOTP_CHALLENGE_COOKIE,
            challenge.token,
            max_age=int(TOTP_CHALLENGE_LIFETIME.total_seconds()),
            httponly=True,
            samesite="strict",
            secure=cookie_secure(settings),
            path="/login",
        )
        return response
    return _session_response(next_path, token, settings)


def _session_response(next_path: str, token: str, settings: Settings) -> Response:
    response = RedirectResponse(next_path, status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_ABSOLUTE_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=cookie_secure(settings),
        path="/",
    )
    response.delete_cookie(LOGIN_CSRF_COOKIE, path="/login")
    response.delete_cookie(TOTP_CHALLENGE_COOKIE, path="/login")
    return response


def _totp_page(
    request: Request, *, next_path: str, error: str | None = None, status: int = 200
) -> Response:
    csrf = request.cookies.get(LOGIN_CSRF_COOKIE) or ""
    return render(
        request, "login_totp.html", {"csrf_token": csrf, "next": next_path, "error": error}, status
    )


@router.get("/login/totp", response_class=HTMLResponse)
def login_totp_form(request: Request, next: str | None = None) -> Response:
    if not request.cookies.get(TOTP_CHALLENGE_COOKIE):
        return RedirectResponse("/login", status_code=303)
    return _totp_page(request, next_path=safe_next_path(next))


@router.post("/login/totp")
def login_totp_submit(
    request: Request,
    code: Annotated[str, Form(max_length=32)],
    csrf_token: Annotated[str, Form(max_length=128)] = "",
    next: Annotated[str, Form(max_length=512)] = "/",
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    next_path = safe_next_path(next)
    challenge = request.cookies.get(TOTP_CHALLENGE_COOKIE)
    if not challenge or not tokens_equal(csrf_token, request.cookies.get(LOGIN_CSRF_COOKIE)):
        return _login_page(
            request, settings, next_path=next_path, error="login.error.stale", status=400
        )
    client_ip = request.client.host if request.client else "unknown"
    error: str | None = None
    status = 200
    token = ""
    with database.transaction() as session:
        service = AuthService(session, secret_key=settings.app_secret_key.get_secret_value())
        try:
            token = service.complete_totp(challenge, code, client_ip=client_ip).token
        except ThrottledError:
            error, status = "login.error.throttled", 429
        except AuthError as exc:
            expired = "expired" in str(exc)
            error, status = ("login.error.stale" if expired else "totp.error.code"), 401
    if error == "login.error.stale":
        return _login_page(request, settings, next_path=next_path, error=error, status=400)
    if error is not None:
        return _totp_page(request, next_path=next_path, error=error, status=status)
    return _session_response(next_path, token, settings)


@router.post("/logout")
def logout(
    request: Request,
    _: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with database.transaction() as session:
            AuthService(session, secret_key=settings.app_secret_key.get_secret_value()).logout(
                token
            )
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/lang/{code}")
def set_language(
    code: str,
    next: str | None = None,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    """Remember the interface language (harmless preference, so a plain GET link)."""
    response = RedirectResponse(safe_next_path(next), status_code=303)
    response.set_cookie(
        LANG_COOKIE,
        normalize_language(code),
        max_age=365 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(settings),
        path="/",
    )
    return response


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        companies = session.scalar(select(func.count()).select_from(Company)) or 0
        leads = session.scalar(select(func.count()).select_from(Lead)) or 0
        new_orders = open_order_count(session)
        awaiting = (
            session.scalar(
                select(func.count())
                .select_from(Proposal)
                .where(Proposal.status == ProposalStatus.AWAITING_APPROVAL)
            )
            or 0
        )
        job_counts = dict(
            session.execute(select(Job.status, func.count()).group_by(Job.status)).tuples().all()
        )
        cron = cron_view(session)
        context = layout_context(session, user)
    context["cron"] = cron
    context["stats"] = {
        "companies": companies,
        "leads": leads,
        "awaiting": awaiting,
        "new_orders": new_orders,
        "jobs_queued": job_counts.get(JobStatus.QUEUED, 0),
        "jobs_running": job_counts.get(JobStatus.RUNNING, 0),
        "jobs_failed": job_counts.get(JobStatus.FAILED, 0),
    }
    return render(request, "home.html", context)

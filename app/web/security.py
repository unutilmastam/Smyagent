"""Security settings: two-factor login with an authenticator app (M3-totp)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_database
from app.application.totp import TotpError, TotpService
from app.core.config import Settings, get_settings
from app.infrastructure.database import Database
from app.infrastructure.database.models import User
from app.web.auth import CurrentUser, require_csrf, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)
BASE = "/settings/security"


def _service(session: Session, settings: Settings) -> TotpService:
    return TotpService(session, secret_key=settings.app_secret_key.get_secret_value())


def _page(
    request: Request,
    database: Database,
    settings: Settings,
    user: CurrentUser,
    *,
    codes: list[str] | None = None,
    error: str | None = None,
    done: str | None = None,
    status: int = 200,
) -> Response:
    with database.transaction() as session:
        account = session.get(User, user.id)
        assert account is not None
        service = _service(session, settings)
        context = layout_context(session, user)
        context.update(
            {
                "enabled": account.totp_enabled,
                "enabled_at": account.totp_enabled_at,
                "setup": service.pending_setup(account),
                "remaining": service.remaining(account) if account.totp_enabled else 0,
                "codes": codes,
                "error": error,
                "done": done or request.query_params.get("done"),
            }
        )
    response = render(request, "settings/security.html", context, status)
    response.headers["Cache-Control"] = "no-store"  # recovery codes / QR never cached
    return response


@router.get(BASE, response_class=HTMLResponse)
def security_page(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    return _page(request, database, settings, user)


@router.post(f"{BASE}/totp/start")
def totp_start(
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        account = session.get(User, user.id)
        assert account is not None
        if not account.totp_enabled:
            _service(session, settings).begin_setup(account)
    return RedirectResponse(BASE, status_code=303)


@router.post(f"{BASE}/totp/cancel")
def totp_cancel(
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        account = session.get(User, user.id)
        if account is not None:
            account.totp_pending_enc = None
    return RedirectResponse(BASE, status_code=303)


@router.post(f"{BASE}/totp/confirm")
def totp_confirm(
    request: Request,
    code: Annotated[str, Form(max_length=32)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    try:
        with database.transaction() as session:
            account = session.get(User, user.id)
            assert account is not None
            codes = _service(session, settings).confirm(account, code)
    except TotpError:
        return _page(request, database, settings, user, error="totp.error.code", status=400)
    request.app.state.notifier.notify(f"🔐 {user.username}: 2FA (TOTP) yoqildi.")
    return _page(request, database, settings, user, codes=codes, done="enabled")


@router.post(f"{BASE}/totp/codes")
def totp_new_codes(
    request: Request,
    code: Annotated[str, Form(max_length=32)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    try:
        with database.transaction() as session:
            account = session.get(User, user.id)
            assert account is not None
            codes = _service(session, settings).regenerate_codes(account, code)
    except TotpError:
        return _page(request, database, settings, user, error="totp.error.code", status=400)
    return _page(request, database, settings, user, codes=codes, done="codes")


@router.post(f"{BASE}/totp/disable")
def totp_disable(
    request: Request,
    password: Annotated[str, Form(max_length=256)],
    code: Annotated[str, Form(max_length=32)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    try:
        with database.transaction() as session:
            account = session.get(User, user.id)
            assert account is not None
            _service(session, settings).disable(account, password=password, code=code)
    except TotpError as exc:
        key = "totp.error.password" if "password" in str(exc) else "totp.error.code"
        return _page(request, database, settings, user, error=key, status=400)
    request.app.state.notifier.notify(f"⚠️ {user.username}: 2FA (TOTP) o'chirildi (dashboard).")
    return RedirectResponse(f"{BASE}?done=disabled", status_code=303)

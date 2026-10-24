"""Request authentication and CSRF for the dashboard and private API routes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import Depends, Request

from app.api.deps import get_database
from app.application.auth import AuthService
from app.core.config import Settings, get_settings
from app.core.security import tokens_equal
from app.domain.auth import Role
from app.infrastructure.database import Database

SESSION_COOKIE = "smy_session"
LOGIN_CSRF_COOKIE = "smy_login_csrf"
CSRF_HEADER = "x-csrf-token"
CSRF_FORM_FIELD = "csrf_token"


@dataclass(frozen=True)
class CurrentUser:
    """Detached snapshot of the logged-in user (safe to use after the DB session closes)."""

    id: uuid.UUID
    username: str
    role: Role
    csrf_token: str

    @property
    def is_owner(self) -> bool:
        return self.role is Role.OWNER


class LoginRequiredError(Exception):
    """Raised when a protected route is hit without a valid session."""

    def __init__(self, next_path: str) -> None:
        super().__init__("login required")
        self.next_path = next_path


class ForbiddenError(Exception):
    pass


class CsrfError(Exception):
    pass


def safe_next_path(value: str | None) -> str:
    """Only allow local absolute paths as post-login redirect targets (no open redirect)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def login_url(next_path: str) -> str:
    return "/login?next=" + quote(safe_next_path(next_path), safe="/")


def cookie_secure(settings: Settings) -> bool:
    return settings.is_production or settings.app_base_url.startswith("https://")


def get_optional_user(
    request: Request,
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CurrentUser | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with database.transaction() as session:
        service = AuthService(session, secret_key=settings.app_secret_key.get_secret_value())
        user_session = service.resolve(token)
        if user_session is None:
            return None
        user = user_session.user
        return CurrentUser(
            id=user.id,
            username=user.username,
            role=user.role,
            csrf_token=user_session.csrf_token,
        )


def require_user(
    request: Request,
    user: CurrentUser | None = Depends(get_optional_user),  # noqa: B008
) -> CurrentUser:
    if user is None:
        path = request.url.path
        if request.url.query:
            path += "?" + request.url.query
        raise LoginRequiredError(path)
    return user


def require_owner(user: CurrentUser = Depends(require_user)) -> CurrentUser:  # noqa: B008
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    return user


async def require_csrf(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
) -> CurrentUser:
    """For state-changing requests: token from header (HTMX) or form field must match."""
    supplied = request.headers.get(CSRF_HEADER)
    if not supplied:
        form = await request.form()
        value = form.get(CSRF_FORM_FIELD)
        supplied = value if isinstance(value, str) else None
    if not tokens_equal(supplied, user.csrf_token):
        raise CsrfError("CSRF token missing or invalid")
    return user

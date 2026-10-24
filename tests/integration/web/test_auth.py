from __future__ import annotations

import re
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_token
from app.domain.auth import MAX_FAILURES_PER_USERNAME, SESSION_IDLE_TIMEOUT
from app.infrastructure.database import Database
from app.infrastructure.database.models import AuditLog, LoginAttempt, User, UserSession
from tests.integration.web.conftest import OWNER_PASSWORD, login


def _csrf_from_page(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf field missing"
    return match.group(1)


def test_anonymous_is_redirected_to_login(web: TestClient) -> None:
    r = web.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login?next=/"


def test_htmx_request_gets_hx_redirect(web: TestClient) -> None:
    r = web.get("/", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers["hx-redirect"].startswith("/login")


def test_login_page_is_mobile_ready_and_sets_csrf_cookie(web: TestClient) -> None:
    r = web.get("/login")
    assert r.status_code == 200
    assert 'name="viewport"' in r.text
    assert "smy_login_csrf" in r.cookies
    assert _csrf_from_page(r.text) == r.cookies["smy_login_csrf"]
    assert r.headers["cache-control"] == "no-store"


def test_login_without_csrf_is_rejected(web: TestClient, owner: str) -> None:
    web.get("/login")
    r = web.post("/login", data={"username": owner, "password": OWNER_PASSWORD})
    assert r.status_code == 400
    assert "smy_session" not in r.cookies


def test_successful_login_sets_secure_session_and_shows_dashboard(
    web: TestClient, owner: str, db: Database
) -> None:
    r = login(web, next_path="/")
    assert r.status_code == 303 and r.headers["location"] == "/"
    set_cookie = r.headers["set-cookie"].lower()
    assert (
        "smy_session=" in set_cookie and "httponly" in set_cookie and "samesite=lax" in set_cookie
    )

    home = web.get("/")
    assert home.status_code == 200
    assert "Salom, bahrullo" in home.text
    assert home.headers["cache-control"] == "no-store"

    # Only the hash of the cookie token is stored.
    token = web.cookies["smy_session"]
    with db.transaction() as s:
        stored = s.scalars(select(UserSession.token_hash)).all()
        actions = s.scalars(select(AuditLog.action)).all()
    assert stored == [hash_token(token)]
    assert token not in stored
    assert "auth.login" in actions


def test_wrong_password_is_generic_and_recorded(web: TestClient, owner: str, db: Database) -> None:
    r = login(web, password="wrong-password-123")
    assert r.status_code == 401
    assert "Login yoki parol noto" in r.text
    r2 = login(web, username="nobody-here")
    assert r2.status_code == 401
    assert r.text.count("noto") == r2.text.count("noto")  # same message for unknown user
    with db.transaction() as s:
        failures = s.scalar(
            select(func.count()).select_from(LoginAttempt).where(LoginAttempt.success.is_(False))
        )
    assert failures == 2


def test_throttling_blocks_even_correct_password(web: TestClient, owner: str) -> None:
    for _ in range(MAX_FAILURES_PER_USERNAME):
        assert login(web, password="wrong-password-123").status_code == 401
    r = login(web)
    assert r.status_code == 429
    assert "smy_session" not in r.cookies


def test_open_redirect_is_blocked(web: TestClient, owner: str) -> None:
    r = login(web, next_path="//evil.example/steal")
    assert r.headers["location"] == "/"


def test_logout_requires_csrf_and_ends_session(web: TestClient, owner: str, db: Database) -> None:
    login(web)
    assert web.post("/logout").status_code == 403
    csrf = _csrf_from_page(web.get("/").text)
    r = web.post("/logout", data={"csrf_token": csrf})
    assert r.status_code == 303 and r.headers["location"] == "/login"
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(UserSession)) == 0
    web.cookies.clear()
    assert web.get("/").status_code == 303


def test_idle_session_expires(web: TestClient, owner: str, db: Database) -> None:
    login(web)
    with db.transaction() as s:
        session = s.scalars(select(UserSession)).one()
        session.last_seen_at = session.last_seen_at - SESSION_IDLE_TIMEOUT - timedelta(minutes=1)
    assert web.get("/").status_code == 303


def test_inactive_user_cannot_log_in(web: TestClient, owner: str, db: Database) -> None:
    with db.transaction() as s:
        s.scalars(select(User)).one().is_active = False
    assert login(web).status_code == 401


def test_forged_session_cookie_is_ignored(web: TestClient, owner: str) -> None:
    web.cookies.set("smy_session", "forged-token-value")
    assert web.get("/").status_code == 303


def test_security_headers(web: TestClient) -> None:
    r = web.get("/login")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_static_css_served(web: TestClient) -> None:
    r = web.get("/static/app.css")
    assert r.status_code == 200 and "bottom-nav" in r.text

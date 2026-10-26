"""Two-factor login end to end (M3-totp): setup with QR, recovery codes, login, disable."""

from __future__ import annotations

import io
import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import cli
from app.core import totp
from app.core.config import Settings, get_settings
from app.infrastructure.database import Database
from app.infrastructure.database.models import AuditLog, TotpRecoveryCode, User
from app.main import create_app
from tests.integration.web.conftest import OWNER_NAME, OWNER_PASSWORD, login


class Notes:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def notify(self, text: str, buttons: object = ()) -> None:
        self.sent.append(text)


@pytest.fixture
def notes() -> Notes:
    return Notes()


@pytest.fixture
def client(db: Database, settings: Settings, notes: Notes) -> Iterator[TestClient]:
    with TestClient(create_app(settings, database=db, notifier=notes), follow_redirects=False) as c:
        yield c


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def _enable(client: TestClient) -> tuple[str, list[str]]:
    """Owner turns 2FA on from the settings page; returns (secret, recovery codes)."""
    assert login(client).status_code == 303
    page = client.get("/settings/security").text
    assert "2FA" in page
    r = client.post("/settings/security/totp/start", data={"csrf_token": _csrf(page)})
    assert r.status_code == 303
    setup = client.get("/settings/security").text
    assert 'src="data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns' in setup
    secret = re.search(r'id="totp-secret">([A-Z2-7 ]+)<', setup).group(1).replace(" ", "")  # type: ignore[union-attr]
    code = totp.code_at(secret, totp.current_step())
    done = client.post(
        "/settings/security/totp/confirm", data={"csrf_token": _csrf(setup), "code": code}
    )
    assert done.status_code == 200 and done.headers["cache-control"] == "no-store"
    codes = re.findall(r"<code>([a-z2-9]{5}-[a-z2-9]{5})</code>", done.text)
    assert len(codes) == 10 and len(set(codes)) == 10
    return secret, codes


def _logout(client: TestClient) -> None:
    html = client.get("/").text
    client.post("/logout", data={"csrf_token": _csrf(html)})
    client.cookies.clear()


def _password_step(client: TestClient, next_path: str = "/") -> str:
    r = login(client, next_path=next_path)
    assert r.status_code == 303 and r.headers["location"].startswith("/login/totp")
    assert "smy_session" not in r.headers.get("set-cookie", "")
    return _csrf(client.get(r.headers["location"]).text)


def _age_last_step(db: Database) -> None:
    """Let a fresh code be accepted (the enable step already used the current one)."""
    with db.transaction() as s:
        user = s.scalars(select(User)).one()
        user.totp_last_step = (user.totp_last_step or 0) - 5


def test_full_flow(client: TestClient, owner: str, db: Database, notes: Notes) -> None:
    secret, codes = _enable(client)
    with db.transaction() as s:
        user = s.scalars(select(User)).one()
        assert user.totp_enabled and secret not in (user.totp_secret_enc or "")
        stored = s.scalars(select(TotpRecoveryCode.code_hash)).all()
        assert len(stored) == 10 and all(c not in h for c in codes for h in stored)
    assert any("yoqildi" in m for m in notes.sent)
    _logout(client)

    # Password alone is not enough any more.
    csrf = _password_step(client, next_path="/leads")
    bad = client.post("/login/totp", data={"csrf_token": csrf, "code": "000000", "next": "/leads"})
    assert bad.status_code == 401 and "alert-error" in bad.text
    # The current code was used to enable 2FA in this 30 s step: replay is refused.
    same = totp.code_at(secret, totp.current_step())
    replay = client.post("/login/totp", data={"csrf_token": csrf, "code": same, "next": "/"})
    assert replay.status_code == 401
    _age_last_step(db)
    ok = client.post("/login/totp", data={"csrf_token": csrf, "code": same, "next": "/leads"})
    assert ok.status_code == 303 and ok.headers["location"] == "/leads"
    assert client.get("/leads").status_code == 200
    _logout(client)

    # A recovery code works exactly once.
    csrf = _password_step(client)
    first = client.post("/login/totp", data={"csrf_token": csrf, "code": codes[0].upper()})
    assert first.status_code == 303
    _logout(client)
    csrf = _password_step(client)
    again = client.post("/login/totp", data={"csrf_token": csrf, "code": codes[0]})
    assert again.status_code == 401
    with db.transaction() as s:
        actions = s.scalars(select(AuditLog.action)).all()
    assert "auth.totp_recovery_used" in actions and "auth.totp_failed" in actions


def test_wrong_codes_are_throttled(client: TestClient, owner: str, db: Database) -> None:
    _enable(client)
    _logout(client)
    csrf = _password_step(client)
    statuses = [
        client.post("/login/totp", data={"csrf_token": csrf, "code": "000000"}).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5 and statuses[5] == 429


def test_tampered_or_missing_challenge(client: TestClient, owner: str, db: Database) -> None:
    _enable(client)
    _logout(client)
    assert client.get("/login/totp").status_code == 303  # no challenge cookie
    csrf = _password_step(client)
    token = client.cookies.get("smy_totp") or ""
    client.cookies.set("smy_totp", token[:-4] + "aaaa", path="/login")
    r = client.post("/login/totp", data={"csrf_token": csrf, "code": "123456"})
    assert r.status_code == 400  # back to the password step


def test_disable_needs_password_and_code(
    client: TestClient, owner: str, db: Database, notes: Notes
) -> None:
    _secret, codes = _enable(client)
    page = client.get("/settings/security").text
    assert "disable-totp --username bahrullo" in page and "10" in page
    csrf = _csrf(page)
    wrong = client.post(
        "/settings/security/totp/disable",
        data={"csrf_token": csrf, "password": "nope-nope-nope", "code": codes[1]},
    )
    assert wrong.status_code == 400
    r = client.post(
        "/settings/security/totp/disable",
        data={"csrf_token": csrf, "password": OWNER_PASSWORD, "code": codes[1]},
    )
    assert r.status_code == 303
    with db.transaction() as s:
        user = s.scalars(select(User)).one()
        assert not user.totp_enabled and s.scalars(select(TotpRecoveryCode)).all() == []
    assert any("o'chirildi" in m for m in notes.sent)
    _logout(client)
    again = login(client)  # password alone is enough again
    assert again.status_code == 303 and again.headers["location"] == "/"


def test_regenerate_codes_and_viewer_csrf(client: TestClient, owner: str, db: Database) -> None:
    secret, codes = _enable(client)
    _age_last_step(db)
    page = client.get("/settings/security").text
    code = totp.code_at(secret, totp.current_step())
    r = client.post("/settings/security/totp/codes", data={"csrf_token": _csrf(page), "code": code})
    new = re.findall(r"<code>([a-z2-9]{5}-[a-z2-9]{5})</code>", r.text)
    assert len(new) == 10 and not set(new) & set(codes)
    assert client.post("/settings/security/totp/start", data={}).status_code == 403  # CSRF


def test_cli_disable_totp(
    client: TestClient,
    owner: str,
    db: Database,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _enable(client)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    get_settings.cache_clear()
    assert cli.main(["disable-totp", "--username", OWNER_NAME.upper()]) == 0
    assert "o'chirildi" in capsys.readouterr().out
    with db.transaction() as s:
        assert not s.scalars(select(User)).one().totp_enabled
        assert "auth.totp_disabled_cli" in s.scalars(select(AuditLog.action)).all()
    assert cli.main(["disable-totp", "--username", OWNER_NAME]) == 0  # already off
    assert cli.main(["disable-totp", "--username", "nobody"]) == 1

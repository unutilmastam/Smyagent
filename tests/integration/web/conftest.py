from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.application.auth import AuthService
from app.core.config import Settings
from app.infrastructure.database import Database
from app.main import create_app

OWNER_NAME = "bahrullo"
OWNER_PASSWORD = "Denov-ITcoDe-2026!"


@pytest.fixture
def owner(db: Database, settings: Settings) -> str:
    with db.transaction() as session:
        AuthService(session, secret_key="test").create_owner(OWNER_NAME, OWNER_PASSWORD)
    return OWNER_NAME


@pytest.fixture
def web(db: Database, settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, database=db), follow_redirects=False) as client:
        yield client


def login(
    client: TestClient,
    username: str = OWNER_NAME,
    password: str = OWNER_PASSWORD,
    next_path: str = "/",
):  # type: ignore[no-untyped-def]
    page = client.get("/login")
    csrf = page.cookies.get("smy_login_csrf") or client.cookies.get("smy_login_csrf")
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf, "next": next_path},
    )

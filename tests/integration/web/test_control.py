from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.domain.auth import Role
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentControl, User
from app.main import create_app
from tests.integration.web.conftest import login


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, text: str) -> None:
        self.messages.append(text)


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def app_client(db: Database, settings: Settings, notifier: FakeNotifier) -> Iterator[TestClient]:
    app = create_app(settings, database=db, notifier=notifier)
    with TestClient(app, follow_redirects=False) as client:
        yield client


@pytest.fixture
def owner_client(app_client: TestClient, owner: str) -> TestClient:
    assert login(app_client).status_code == 303
    return app_client


@pytest.fixture
def viewer_client(app_client: TestClient, db: Database) -> TestClient:
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    assert login(app_client, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    return app_client


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def _state(db: Database, key: str) -> str:
    with db.transaction() as s:
        return s.scalars(select(AgentControl.state).where(AgentControl.module == key)).one().value


def test_control_requires_login(app_client: TestClient) -> None:
    assert app_client.get("/control").status_code == 303
    assert app_client.get("/api/v1/control/snapshot").status_code == 401


def test_owner_sees_graph_controls_and_stop_button(owner_client: TestClient) -> None:
    html = owner_client.get("/control").text
    assert '<svg class="agent-graph"' in html
    assert html.count('class="node node-idle"') == 7
    assert "HAMMASINI TO&#39;XTATISH" in html
    assert "⛔ STOP" in owner_client.get("/").text  # always-visible emergency stop
    assert 'data-poll="/control"' in html


def test_owner_pauses_agent_and_graph_reflects_it(
    owner_client: TestClient, db: Database, notifier: FakeNotifier
) -> None:
    csrf = _csrf(owner_client.get("/control").text)
    r = owner_client.post("/control/research_audit", data={"csrf_token": csrf, "state": "PAUSED"})
    assert r.status_code == 303 and r.headers["location"] == "/control?changed=1"
    assert _state(db, "research_audit") == "PAUSED"
    partial = owner_client.get("/control", headers={"HX-Request": "true"}).text
    assert "<html" not in partial
    assert 'class="node node-paused"' in partial
    assert notifier.messages and "research_audit" in notifier.messages[0]


def test_emergency_stop_from_dashboard(owner_client: TestClient, db: Database) -> None:
    csrf = _csrf(owner_client.get("/").text)
    owner_client.post("/control/global", data={"csrf_token": csrf, "state": "STOPPED"})
    assert _state(db, "global") == "STOPPED"
    html = owner_client.get("/control").text
    assert html.count('class="node node-stopped"') == 7
    assert "Hammasini faollashtirish" in html
    assert "⛔ STOP" not in html  # replaced by the resume button


def test_state_change_requires_csrf(owner_client: TestClient, db: Database) -> None:
    assert owner_client.post("/control/global", data={"state": "STOPPED"}).status_code == 403
    assert _state(db, "global") == "ACTIVE"


def test_viewer_cannot_change_state(viewer_client: TestClient, db: Database) -> None:
    html = viewer_client.get("/control").text
    assert "Faqat ko&#39;rish" in html and "HAMMASINI" not in html
    csrf = _csrf(viewer_client.get("/").text)
    r = viewer_client.post("/control/global", data={"csrf_token": csrf, "state": "STOPPED"})
    assert r.status_code == 403
    api = viewer_client.post(
        "/api/v1/control/global", json={"state": "STOPPED"}, headers={"X-CSRF-Token": csrf}
    )
    assert api.status_code == 403
    assert _state(db, "global") == "ACTIVE"


def test_invalid_key_or_state_is_400(owner_client: TestClient) -> None:
    csrf = _csrf(owner_client.get("/").text)
    assert (
        owner_client.post("/control/nope", data={"csrf_token": csrf, "state": "PAUSED"}).status_code
        == 400
    )
    assert (
        owner_client.post("/control/global", data={"csrf_token": csrf, "state": "LOL"}).status_code
        == 400
    )


def test_api_snapshot_and_change(owner_client: TestClient, db: Database) -> None:
    snap = owner_client.get("/api/v1/control/snapshot").json()
    assert snap["global_state"] == "ACTIVE" and len(snap["modules"]) == 7
    csrf = _csrf(owner_client.get("/").text)
    r = owner_client.post(
        "/api/v1/control/discovery",
        json={"state": "STOPPED", "reason": "test"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200 and r.json()["state"] == "STOPPED"
    snap = owner_client.get("/api/v1/control/snapshot").json()
    discovery = next(m for m in snap["modules"] if m["key"] == "discovery")
    assert discovery["status"] == "stopped"
    assert (
        owner_client.post("/api/v1/control/discovery", json={"state": "ACTIVE"}).status_code == 403
    )


def test_polling_interval_within_five_seconds() -> None:
    from app.web.templating import STATIC_DIR

    js = (STATIC_DIR / "app.js").read_text()
    interval = int(re.search(r"POLL_MS = (\d+)", js).group(1))  # type: ignore[union-attr]
    assert 3000 <= interval <= 5000

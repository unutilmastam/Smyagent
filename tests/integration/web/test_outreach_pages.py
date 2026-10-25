"""Outreach page, one-tap Telegram tasks, owner actions and public unsubscribe (M9)."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application.auth import AuthService
from app.application.outreach import OutreachService
from app.application.proposals import ProposalService
from app.core.config import Settings, load_settings
from app.core.security import hash_password
from app.domain.actors import Actor
from app.domain.auth import Role
from app.domain.contacts import ContactKind
from app.domain.outreach import unsubscribe_token
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Contact,
    Lead,
    OutreachEvent,
    Proposal,
    SuppressionRecord,
    User,
)
from app.main import create_app
from tests.integration.proposal_helpers import awaiting_proposal
from tests.integration.web.conftest import OWNER_NAME, OWNER_PASSWORD, login

SECRET = "s" * 40
EMAIL = "info@lazzat.uz"


def _settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "app_secret_key": SECRET,
    }
    base.update(kw)
    return load_settings(**base)


@pytest.fixture
def app_client(db: Database) -> Iterator[TestClient]:
    with TestClient(create_app(_settings(), database=db), follow_redirects=False) as c:
        yield c


@pytest.fixture
def owner_client(app_client: TestClient, db: Database) -> TestClient:
    with db.transaction() as s:
        AuthService(s, secret_key="test").create_owner(OWNER_NAME, OWNER_PASSWORD)
    assert login(app_client).status_code == 303
    return app_client


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def _telegram_task(db: Database) -> OutreachEvent:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        proposal = s.get(Proposal, pid)
        assert proposal is not None
        s.add(
            Contact(company_id=proposal.company_id, kind=ContactKind.TELEGRAM, value="@lazzat_uz")
        )
        ProposalService(s).approve(pid, Actor.user("owner"))
    with db.transaction() as s:
        OutreachService(s, _settings()).plan()
        event = s.scalars(select(OutreachEvent)).one()
        s.expunge(event)
        return event


def test_requires_login(app_client: TestClient) -> None:
    assert app_client.get("/outreach").status_code in (302, 303)


def test_page_shows_one_tap_telegram_task(owner_client: TestClient, db: Database) -> None:
    event = _telegram_task(db)
    html = owner_client.get("/outreach").text
    assert 'href="https://t.me/lazzat_uz"' in html and f'data-copy="msg-{event.id}"' in html
    assert "Men Mustafo" in html  # the prepared text to paste
    assert "Yuborish o&#39;chiq" in html  # sending flag is visible
    csrf = _csrf(html)
    r = owner_client.post(f"/outreach/events/{event.id}/done", data={"csrf_token": csrf})
    assert r.status_code == 303 and "saved=done" in r.headers["location"]
    with db.transaction() as s:
        assert s.scalars(select(Lead)).one().stage.value == "CONTACTED"
    again = owner_client.post(f"/outreach/events/{event.id}/done", data={"csrf_token": csrf})
    assert "error=" in again.headers["location"]
    owner_client.post(f"/outreach/events/{event.id}/replied", data={"csrf_token": csrf})
    with db.transaction() as s:
        assert s.scalars(select(Lead)).one().stage.value == "RESPONDED"


def test_viewer_cannot_act(app_client: TestClient, db: Database) -> None:
    event = _telegram_task(db)
    with db.transaction() as s:
        pw = hash_password("Viewer-Pass-2026!")
        s.add(User(username="viewer1", password_hash=pw, role=Role.VIEWER))
    assert login(app_client, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    html = app_client.get("/outreach").text
    assert "lazzat_uz" in html and "/done" not in html
    r = app_client.post(
        f"/outreach/events/{event.id}/done", data={"csrf_token": _csrf(app_client.get("/").text)}
    )
    assert r.status_code == 403


def test_unsubscribe_link(app_client: TestClient, db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        company_id = s.get(Proposal, pid).company_id  # type: ignore[union-attr]
        s.add(
            Contact(
                company_id=company_id, kind=ContactKind.EMAIL, value=EMAIL, is_role_address=True
            )
        )
    token = unsubscribe_token(SECRET, EMAIL)
    page = app_client.get(f"/u/{token}")
    assert page.status_code == 200 and "Boshqa yozmang" in page.text
    with db.transaction() as s:
        assert s.scalars(select(SuppressionRecord)).all() == []  # GET changes nothing
    done = app_client.post(f"/u/{token}", data={"List-Unsubscribe": "One-Click"})
    assert done.status_code == 200 and "boshqa xat yuborilmaydi" in done.text
    with db.transaction() as s:
        assert s.scalars(select(SuppressionRecord.value)).one() == EMAIL
        assert s.scalars(select(Lead)).one().stage.value == "DO_NOT_CONTACT"
    assert app_client.post(f"/u/{token}").status_code == 200  # idempotent
    assert app_client.get("/u/forged.token").status_code == 404
    assert app_client.post(f"/u/{unsubscribe_token('wrong', EMAIL)}").status_code == 404


def test_outreach_settings_saved(owner_client: TestClient) -> None:
    url = "/settings/agents/conversation"
    csrf = _csrf(owner_client.get(url).text)
    r = owner_client.post(
        url,
        data={
            "csrf_token": csrf,
            "reply_mode": "approve_all",
            "email_auto_approve": "on",
            "email_daily_cap": "40",
            "follow_up_days": "7",
        },
    )
    assert r.status_code == 303
    page = owner_client.get(url).text
    assert 'name="email_auto_approve" checked' in page and 'value="40"' in page
    bad = owner_client.post(url, data={"csrf_token": csrf, "follow_up_days": "2"})
    assert bad.status_code == 422  # follow-up never earlier than 5 days

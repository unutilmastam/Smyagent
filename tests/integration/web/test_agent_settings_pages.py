"""Agent settings pages and their effect on the agents (M7c)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application.proposals import ProposalService
from app.core.security import hash_password
from app.domain.agents import AgentModule
from app.domain.auth import Role
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    AgentSetting,
    AgentSettingVersion,
    AuditLog,
    Proposal,
    User,
)
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from tests.integration.proposal_helpers import qualified_lead
from tests.integration.web.conftest import login

URL = "/settings/agents/proposal_requirements"


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def _version(db: Database, module: str) -> int:
    with db.transaction() as s:
        row = s.get(AgentSetting, module)
        return row.version if row else 0


def test_requires_login(web: TestClient) -> None:
    assert web.get("/settings").status_code in (302, 303)
    assert web.get(URL).status_code in (302, 303)


def test_hub_lists_every_agent_and_locked_rules(authed: TestClient) -> None:
    html = authed.get("/settings").text
    for module in AgentModule:
        assert f'href="/settings/agents/{module.value}"' in html
    assert "O&#39;zgartirib bo&#39;lmaydigan qoidalar" in html
    assert "AI ekanini aytadi" in html
    assert authed.get("/settings/agents/nope").status_code == 404


def test_every_agent_page_renders(authed: TestClient) -> None:
    for module in AgentModule:
        r = authed.get(f"/settings/agents/{module.value}")
        assert r.status_code == 200 and 'name="instructions"' in r.text


def test_owner_saves_versions_and_restores(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed.get("/settings/agents/discovery").text)
    data = {"csrf_token": csrf, "results_per_search": "80", "instructions": "Qishloqlarni ham"}
    r = authed.post("/settings/agents/discovery", data=data)
    assert r.status_code == 303 and r.headers["location"].endswith("saved=1")
    authed.post("/settings/agents/discovery", data={**data, "results_per_search": "30"})
    with db.transaction() as s:
        assert AgentSettingsRepository(s).get(AgentModule.DISCOVERY).results_per_search == 30
        first = s.scalars(select(AgentSettingVersion).where(AgentSettingVersion.version == 1)).one()
        assert s.scalars(select(AuditLog).where(AuditLog.action == "settings.agent")).all()
    page = authed.get("/settings/agents/discovery?saved=2").text
    assert "Saqlandi (v2)" in page and f"/restore/{first.id}" in page
    authed.post(f"/settings/agents/discovery/restore/{first.id}", data={"csrf_token": csrf})
    with db.transaction() as s:
        assert AgentSettingsRepository(s).get(AgentModule.DISCOVERY).results_per_search == 80
    assert _version(db, "discovery") == 3  # restore adds a version, never rewrites
    authed.post("/settings/agents/discovery/reset", data={"csrf_token": csrf})
    with db.transaction() as s:
        assert AgentSettingsRepository(s).get(AgentModule.DISCOVERY).results_per_search == 50
    assert _version(db, "discovery") == 4


def test_invalid_values_are_not_saved(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed.get("/settings/agents/discovery").text)
    r = authed.post(
        "/settings/agents/discovery", data={"csrf_token": csrf, "results_per_search": "9999"}
    )
    assert r.status_code == 422 and "Saqlanmadi" in r.text
    assert _version(db, "discovery") == 0


def test_price_in_offer_text_is_refused(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed.get(URL).text)
    r = authed.post(
        URL,
        data={
            "csrf_token": csrf,
            "services": ["telegram_bot"],
            "stext_uz_telegram_bot": "Telegram bot atigi 990 000 so'm!",
        },
    )
    assert r.status_code == 422 and "price" in r.text
    assert _version(db, "proposal_requirements") == 0


def test_requires_csrf_and_owner(web: TestClient, db: Database) -> None:
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    assert login(web, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    html = web.get("/settings/agents/discovery").text
    assert "disabled" in html and "Saqlash</button>" not in html
    csrf = _csrf(web.get("/").text)
    for url in ("/settings/agents/discovery", "/settings/agents/discovery/reset"):
        assert (
            web.post(url, data={"csrf_token": csrf, "results_per_search": "60"}).status_code == 403
        )
    assert _version(db, "discovery") == 0


def test_saved_offer_settings_drive_the_proposal_agent(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed.get(URL).text)
    r = authed.post(
        URL,
        data={
            "csrf_token": csrf,
            "services": ["telegram_bot"],
            "max_services": "1",
            "text_uz_intro": "Hurmatli {company}, ochiq ma'lumotlardan ko'rdikki:",
        },
    )
    assert r.status_code == 303
    lead_id = qualified_lead(db)
    with db.transaction() as s:
        proposal = ProposalService(s).draft_for_lead(lead_id)
        assert proposal is not None
        version = proposal.versions[0]
        assert version.services == ["telegram_bot"]  # business_website disabled by owner
        assert "Hurmatli Lazzat Oshxonasi, ochiq" in version.body


def test_owner_blocked_word_stops_offers(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed.get("/settings/agents/quality_gate").text)
    authed.post(
        "/settings/agents/quality_gate", data={"csrf_token": csrf, "extra_blocked": "Mustafo"}
    )
    lead_id = qualified_lead(db)
    with db.transaction() as s:
        proposal = ProposalService(s).draft_for_lead(lead_id)
        assert proposal is not None
        pid = proposal.id
    with db.transaction() as s:
        outcome = ProposalService(s).run_gate(pid, 1)
        assert outcome is not None and "owner_blocked_word" in outcome.result.codes
        assert s.get(Proposal, pid).status.value == "NEEDS_EDIT"  # type: ignore[union-attr]


def test_control_cards_link_to_settings(authed: TestClient) -> None:
    assert 'href="/settings/agents/research_audit"' in authed.get("/control").text

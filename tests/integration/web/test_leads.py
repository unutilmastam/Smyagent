"""Lead list, company detail scores and scoring settings (M6)."""

from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application.workflow import WorkflowService
from app.core.security import hash_password
from app.domain.actors import Actor
from app.domain.auth import Role
from app.domain.leads import LeadStage
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    AuditLog,
    LeadScore,
    Opportunity,
    ScoreComponent,
    ScoringSettings,
    User,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.jobs.tasks.scoring import load_settings
from tests.integration.web.conftest import login

ACTOR = Actor.agent("opportunity_scoring")


def _scored(db: Database, name: str, total: int, *, qualified: bool) -> uuid.UUID:
    with db.transaction() as s:
        cid = CompanyRepository(s).add(NewCompany(name=name, country="UZ", city="Denov")).id
        wf = WorkflowService(s)
        lead = wf.create_lead(cid, ACTOR)
        if qualified:
            wf.transition_lead(lead.id, LeadStage.QUALIFIED, ACTOR)
        s.add(
            Opportunity(
                company_id=cid,
                service="telegram_bot",
                strength=0.7,
                reasons=["no_online_inquiry"],
                finding_ids=[],
            )
        )
        score = LeadScore(
            company_id=cid,
            lead_id=lead.id,
            total=total,
            version="v1",
            weights={},
            missing=["activity"],
            computed_at=utcnow(),
        )
        score.components = [
            ScoreComponent(component="service_fit", value=70, weight=3.0, explanation="best"),
            ScoreComponent(component="activity", value=None, weight=1.0, explanation="no site"),
        ]
        s.add(score)
    return cid


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def test_leads_require_login(web: TestClient) -> None:
    assert web.get("/leads").status_code in (302, 303)
    assert web.get("/settings/scoring").status_code in (302, 303)


def test_leads_sorted_by_score_with_need(authed: TestClient, db: Database) -> None:
    _scored(db, "Past Ball", 40, qualified=False)
    _scored(db, "Yuqori Ball", 88, qualified=True)
    html = authed.get("/leads").text
    names = re.findall(r'class="company-name">([^<]*)<', html)
    assert names == ["Yuqori Ball", "Past Ball"]
    assert "Telegram bot" in html and "Ball: 88" in html

    only_qualified = authed.get("/leads?stage=QUALIFIED").text
    assert re.findall(r'class="company-name">([^<]*)<', only_qualified) == ["Yuqori Ball"]
    # An unknown stage is ignored, not an error.
    assert authed.get("/leads?stage=NOPE").status_code == 200


def test_empty_leads_state(authed: TestClient) -> None:
    assert "Hali lid yo&#39;q" in authed.get("/leads").text


def test_detail_shows_opportunities_and_score(authed: TestClient, db: Database) -> None:
    cid = _scored(db, "Lazzat", 77, qualified=True)
    html = authed.get(f"/companies/{cid}").text
    assert "Imkoniyatlar" in html and "Telegram bot" in html and "no_online_inquiry" in html
    assert "Baho: 77/100" in html
    assert "Ma&#39;lumot yo&#39;q" in html  # missing component shown, never imputed


def test_owner_saves_weights_and_threshold(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed.get("/settings/scoring").text)
    r = authed.post(
        "/settings/scoring",
        data={
            "csrf_token": csrf,
            "threshold": "70",
            "w_service_fit": "5",
            "w_contactability": "99",  # clamped to 10
            "w_activity": "abc",  # ignored -> default kept
        },
    )
    assert r.status_code == 303
    with db.transaction() as s:
        weights, threshold = load_settings(s)
        assert threshold == 70
        assert {k.value: v for k, v in weights.items()}["service_fit"] == 5.0
        assert {k.value: v for k, v in weights.items()}["contactability"] == 10.0
        assert {k.value: v for k, v in weights.items()}["activity"] == 1.0
        assert s.scalars(select(AuditLog).where(AuditLog.action == "settings.scoring")).first()
    assert 'value="70"' in authed.get("/settings/scoring?saved=1").text


def test_settings_require_csrf_and_valid_threshold(authed: TestClient, db: Database) -> None:
    assert authed.post("/settings/scoring", data={"threshold": "50"}).status_code == 403
    csrf = _csrf(authed.get("/settings/scoring").text)
    bad = authed.post("/settings/scoring", data={"csrf_token": csrf, "threshold": "500"})
    assert bad.status_code in (400, 422)
    with db.transaction() as s:
        assert s.get(ScoringSettings, "default") is None


def test_viewer_cannot_change_scoring(web: TestClient, db: Database) -> None:
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    assert login(web, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    assert web.get("/leads").status_code == 200
    assert web.get("/settings/scoring").status_code == 403
    csrf = _csrf(web.get("/leads").text)
    r = web.post("/settings/scoring", data={"csrf_token": csrf, "threshold": "1"})
    assert r.status_code == 403
    with db.transaction() as s:
        assert s.get(ScoringSettings, "default") is None

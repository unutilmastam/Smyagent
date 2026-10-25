"""Virtual Office (CLAUDE.md §13A.3): page, real-state API, events, controls."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application.controls import AgentControlService
from app.application.office import OfficeSnapshotService
from app.application.workflow import WorkflowService
from app.core.config import Settings
from app.core.security import hash_password
from app.domain.actors import Actor
from app.domain.agents import ControlState
from app.domain.auth import Role
from app.domain.jobs import JobStatus
from app.domain.outreach import Channel, OutreachKind, OutreachStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    AgentControl,
    AgentRun,
    AgentRunStatus,
    AuditLog,
    Job,
    OutreachEvent,
    User,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.main import create_app
from tests.integration.conversation_helpers import confirmed_order
from tests.integration.web.conftest import login

OWNER = Actor.user("owner")


class FakeNotifier:
    def notify(self, text: str, buttons: Any = ()) -> None:
        pass


@pytest.fixture
def client(db: Database, settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings, database=db, notifier=FakeNotifier())
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def owner_client(client: TestClient, owner: str) -> TestClient:
    assert login(client).status_code == 303
    return client


def _office(client: TestClient) -> dict[str, Any]:
    r = client.get("/api/v1/control/office")
    assert r.status_code == 200
    return r.json()


def _agent(data: dict[str, Any], key: str) -> dict[str, Any]:
    return next(a for a in data["agents"] if a["key"] == key)


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def test_office_requires_login(client: TestClient) -> None:
    assert client.get("/control/office").status_code in (302, 303)
    assert client.get("/api/v1/control/office").status_code == 401


def test_page_has_canvas_list_controls_and_no_inline_script(owner_client: TestClient) -> None:
    html = owner_client.get("/control/office").text
    assert 'id="office-canvas"' in html and "/static/office.js" in html
    assert html.count('class="office-agent"') == 7
    assert 'id="office-stop-form"' in html and 'name="next" value="/control/office"' in html
    # Only data blocks inline (CSP script-src 'self' forbids inline code).
    blocks = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", html)
    assert blocks and all('type="application/json"' in b for b in blocks)
    text = json.loads(re.search(r'id="office-text">(.*?)</script>', html, re.S).group(1))  # type: ignore[union-attr]
    assert text["office.mode.work"] == "ishlayapti" and "agent.conversation" in text
    assert "/control/office" in owner_client.get("/").text  # one tap from the home screen


def test_static_script_is_served(owner_client: TestClient) -> None:
    r = owner_client.get("/static/office.js")
    assert r.status_code == 200
    # Server text is only ever set with textContent / canvas fillText (no HTML injection).
    assert "innerHTML" not in r.text and "eval(" not in r.text


def test_api_maps_real_state(owner_client: TestClient, db: Database) -> None:
    now = utcnow()
    with db.transaction() as s:
        job = Job(
            job_type="research.audit",
            agent_module="research_audit",
            status=JobStatus.RUNNING,
            payload={},
            heartbeat_at=now,
            attempts=1,
        )
        s.add(job)
        s.flush()
        s.add(
            AgentRun(
                module="research_audit",
                job_id=job.id,
                current_step="lazzat.uz (3/5)",
                progress_pct=60,
                heartbeat_at=now,
            )
        )
        s.add(
            Job(
                job_type="discovery.search",
                agent_module="discovery",
                status=JobStatus.QUEUED,
                payload={},
                attempts=1,
                last_error="OpenStreetMap: HTTP 429",
                run_after=now + timedelta(minutes=3),
            )
        )
        failed = Job(
            job_type="scoring.evaluate",
            agent_module="opportunity_scoring",
            status=JobStatus.FAILED,
            payload={},
            attempts=3,
            last_error="TimeoutError",
            finished_at=now - timedelta(minutes=1),
        )
        s.add(failed)
        s.add(
            Job(
                job_type="gate.review",
                agent_module="quality_gate",
                status=JobStatus.QUEUED,
                payload={},
                run_after=now - timedelta(seconds=5),
            )
        )
        s.flush()
        failed_id = str(failed.id)
        AgentControlService(s).set_state(
            "proposal_requirements", ControlState.PAUSED, OWNER, "test"
        )
    data = _office(owner_client)
    work = _agent(data, "research_audit")
    assert work["mode"] == "work" and work["progress_pct"] == 60 and "lazzat" in work["detail"]
    wait = _agent(data, "discovery")
    assert wait["mode"] == "wait" and wait["wait_kind"] == "rate_limit" and wait["retry_at"]
    err = _agent(data, "opportunity_scoring")
    assert err["mode"] == "error" and err["detail"] == "TimeoutError" and err["job_id"] == failed_id
    assert _agent(data, "quality_gate")["mode"] == "queued"
    assert _agent(data, "proposal_requirements")["mode"] == "pause"
    assert _agent(data, "conversation")["mode"] == "idle"
    assert data["cron_health"] == "never" and data["global_state"] == "ACTIVE"


def test_global_stop_stops_everyone(owner_client: TestClient, db: Database) -> None:
    with db.transaction() as s:
        AgentControlService(s).set_state("global", ControlState.STOPPED, OWNER, "test")
    data = _office(owner_client)
    assert data["global_state"] == "STOPPED"
    assert {a["mode"] for a in data["agents"]} == {"stop"}


def test_events_email_handoff_and_order(db: Database) -> None:
    with db.transaction() as s:
        company = CompanyRepository(s).add(NewCompany(name="Lazzat", country="UZ"))
        s.add(
            OutreachEvent(
                company_id=company.id,
                channel=Channel.EMAIL,
                kind=OutreachKind.FIRST,
                status=OutreachStatus.SENT,
                recipient="info@lazzat.uz",
                idempotency_key="t:1",
                body="x",
                created_by="t",
                sent_at=utcnow(),
            )
        )
        s.add(
            OutreachEvent(
                company_id=company.id,
                channel=Channel.EMAIL,
                kind=OutreachKind.FIRST,
                status=OutreachStatus.SENT,
                recipient="sales@lazzat.uz",
                idempotency_key="t:2",
                body="x",
                created_by="t",
                sent_at=utcnow() - timedelta(hours=1),
            )
        )  # too old: not animated
    confirmed_order(db)
    with db.transaction() as s:
        data = OfficeSnapshotService(s).build(
            timezone="Asia/Tashkent", ai_budget_today=Decimal("0")
        )
    kinds = [e["kind"] for e in data["events"]]
    assert kinds.count("email_sent") == 1
    mail = next(e for e in data["events"] if e["kind"] == "email_sent")
    assert mail["module"] == "conversation" and mail["text"] == "Lazzat"
    order = next(e for e in data["events"] if e["kind"] == "order_confirmed")
    assert order["id"].startswith("order:") and "telegram_bot" in order["text"]
    assert data["today"]["orders"] == 1 and data["today"]["emails"] == 2


def test_handoff_event_from_workflow(db: Database) -> None:
    from app.domain.companies import ResearchState

    with db.transaction() as s:
        company = CompanyRepository(s).add(NewCompany(name="Denov Mebel", country="UZ"))
        wf = WorkflowService(s)
        wf.transition_company(
            company.id, ResearchState.RESEARCH_PENDING, Actor.agent("research_audit")
        )
        wf.transition_company(company.id, ResearchState.RESEARCHED, Actor.agent("research_audit"))
    with db.transaction() as s:
        data = OfficeSnapshotService(s).build(
            timezone="Asia/Tashkent", ai_budget_today=Decimal("0")
        )
    hand = [e for e in data["events"] if e["kind"] == "handoff"]
    assert {(e["module"], e["to"]) for e in hand} >= {("research_audit", "opportunity_scoring")}


def test_per_agent_stats_today(db: Database) -> None:

    with db.transaction() as s:
        s.add(
            AgentRun(
                module="discovery", status=AgentRunStatus.SUCCEEDED, cost_usd=Decimal("0.0020")
            )
        )
        s.add(AgentRun(module="discovery", status=AgentRunStatus.FAILED))
    with db.transaction() as s:
        data = OfficeSnapshotService(s).build(
            timezone="Asia/Tashkent", ai_budget_today=Decimal("0")
        )
    disc = _agent(data, "discovery")
    assert (disc["done_today"], disc["failed_today"], disc["cost_today_usd"]) == (1, 1, "0.0020")


def test_sheet_form_returns_to_office_and_is_audited(
    owner_client: TestClient, db: Database
) -> None:
    csrf = _csrf(owner_client.get("/control/office").text)
    r = owner_client.post(
        "/control/research_audit",
        data={"csrf_token": csrf, "state": "PAUSED", "next": "/control/office"},
    )
    assert r.status_code == 303 and r.headers["location"] == "/control/office?changed=1"
    # Unknown return paths fall back to /control (no open redirect).
    r = owner_client.post(
        "/control/research_audit",
        data={"csrf_token": csrf, "state": "ACTIVE", "next": "//evil.example"},
    )
    assert r.headers["location"] == "/control?changed=1"
    with db.transaction() as s:
        state = s.scalars(
            select(AgentControl.state).where(AgentControl.module == "research_audit")
        ).one()
        actions = s.scalars(select(AuditLog.action)).all()
    assert state is ControlState.ACTIVE and actions.count("agent_control.set") == 2


def test_viewer_sees_office_without_controls(client: TestClient, db: Database) -> None:
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    assert login(client, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    html = client.get("/control/office").text
    assert 'id="office-canvas"' in html and "office-stop-form" not in html
    assert "data-sheet-form" not in html and 'data-owner="0"' in html

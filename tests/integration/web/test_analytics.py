"""Analytics (M11): funnel counts with defined denominators, outreach, agents, page."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.application.analytics import AnalyticsService
from app.application.budget import BudgetService, UsageRecord
from app.application.workflow import WorkflowService
from app.core.config import Settings
from app.domain.actors import Actor
from app.domain.companies import ResearchState
from app.domain.jobs import JobStatus
from app.domain.leads import LeadStage
from app.domain.outreach import Channel, OutreachKind, OutreachStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import Company, Job, OutreachEvent, WorkflowEvent
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.main import create_app
from tests.integration.web.conftest import login

AGENT = Actor.agent("test")
PATH = [
    LeadStage.QUALIFIED,
    LeadStage.PROPOSAL_DRAFTED,
    LeadStage.AWAITING_APPROVAL,
    LeadStage.APPROVED,
    LeadStage.CONTACTED,
    LeadStage.RESPONDED,
]


def _lead(db: Database, name: str, stages: list[LeadStage], *, inbound: bool = False) -> None:
    with db.transaction() as s:
        company = CompanyRepository(s).add(NewCompany(name=name, country="UZ"))
        wf = WorkflowService(s)
        wf.transition_company(company.id, ResearchState.RESEARCH_PENDING, AGENT)
        wf.transition_company(company.id, ResearchState.RESEARCHED, AGENT)
        lead = wf.create_lead(company.id, AGENT, inbound=inbound)
        for stage in stages:
            wf.transition_lead(lead.id, stage, AGENT)


def test_funnel_counts_and_rates(db: Database, settings: Settings) -> None:
    _lead(db, "A", PATH)  # all the way to a reply
    _lead(db, "B", PATH[:5])  # contacted, no reply
    _lead(db, "C", [LeadStage.QUALIFIED])
    _lead(db, "D", [], inbound=True)  # wrote to the bot first
    with db.transaction() as s:
        company = s.query(Company).filter_by(name="A").one()
        for key, replied in (("a", True), ("b", False)):
            s.add(
                OutreachEvent(
                    company_id=company.id,
                    channel=Channel.EMAIL,
                    kind=OutreachKind.FIRST,
                    status=OutreachStatus.SENT,
                    recipient=f"{key}@x.uz",
                    idempotency_key=f"t:{key}",
                    body="x",
                    created_by="t",
                    sent_at=utcnow(),
                    replied_at=utcnow() if replied else None,
                )
            )
        s.add(
            Job(
                job_type="x",
                agent_module="discovery",
                status=JobStatus.SUCCEEDED,
                payload={},
                finished_at=utcnow(),
            )
        )
        s.add(
            Job(
                job_type="x",
                agent_module="discovery",
                status=JobStatus.FAILED,
                payload={},
                finished_at=utcnow(),
            )
        )
        BudgetService(s, settings).record(
            UsageRecord(
                provider="anthropic",
                model="small",
                module="research_audit",
                cost_usd=Decimal("0.02"),
            )
        )
    with db.transaction() as s:
        r = AnalyticsService(s, settings).report(7)
    steps = {f.key: f for f in r.funnel}
    assert steps["found"].count == 4 and steps["researched"].count == 4
    assert steps["qualified"].count == 3 and steps["qualified"].rate_pct == 75
    assert steps["contacted"].count == 2
    assert steps["replied"].count == 1 and steps["replied"].rate_pct == 50
    assert steps["replied"].denominator_key == "contacted"
    assert r.inbound == 1  # inbound clients are not counted as outreach replies
    assert steps["orders"].denominator_key == "replied_all" and steps["orders"].rate_pct == 0
    assert steps["won"].rate_pct is None  # 0 of 0
    assert r.outreach["emails_sent"] == 2 and r.outreach["reply_pct"] == 50
    disc = next(a for a in r.agents if a.module == "discovery")
    assert (disc.succeeded, disc.failed, disc.success_pct) == (1, 1, 50)
    assert r.cost_by_module[0].label == "research_audit"
    assert r.budget.spent_today_usd == Decimal("0.02")


def test_period_excludes_old_events(db: Database, settings: Settings) -> None:
    _lead(db, "Old", [LeadStage.QUALIFIED])
    with db.transaction() as s:
        for event in s.query(WorkflowEvent).all():
            event.created_at = utcnow() - timedelta(days=40)
        for company in s.query(Company).all():
            company.created_at = utcnow() - timedelta(days=40)
    with db.transaction() as s:
        week = AnalyticsService(s, settings).report(7)
        ever = AnalyticsService(s, settings).report(0)
        odd = AnalyticsService(s, settings).report(13)  # unknown period → 7 days
    assert week.funnel[0].count == 0 and ever.funnel[0].count == 1 and odd.days == 7


@pytest.fixture
def client(db: Database, settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, database=db), follow_redirects=False) as c:
        yield c


def test_page_requires_login_and_renders(client: TestClient, owner: str, db: Database) -> None:
    assert client.get("/analytics").status_code in (302, 303)
    assert login(client).status_code == 303
    _lead(db, "A", PATH[:1])
    for days in ("1", "7", "30", "0", "x"):
        page = client.get(f"/analytics?days={days}")
        assert page.status_code == 200
    html = client.get("/analytics?days=30").text
    assert "Voronka" in html and "<meter" in html and "MONTHLY_AI_BUDGET_USD" in html
    assert "/analytics" in client.get("/").text

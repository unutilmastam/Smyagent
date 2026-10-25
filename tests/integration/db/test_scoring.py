"""Opportunity & Scoring agent task against a real schema (M6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select

from app.core.config import Settings
from app.domain.agents import AgentModule
from app.domain.companies import ResearchState
from app.domain.leads import LeadStage
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Company,
    Job,
    Lead,
    LeadScore,
    Opportunity,
    ResearchFinding,
    ScoringSettings,
)
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.jobs.context import TaskContext
from app.jobs.runner import JobRunner
from app.jobs.tasks.scoring import SCORING_EVALUATE, enqueue_researched_companies, run_scoring


class RecordingNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, text: str) -> None:
        self.messages.append(text)


def _researched(db: Database, settings: Settings, **contacts: Any) -> uuid.UUID:
    """A company without a website, researched by the real agent (no network needed)."""
    with db.transaction() as s:
        cid = CompanyRepository(s).add(NewCompany(name="Lazzat", country="UZ", **contacts)).id
    JobRunner(db, settings, search_provider_factory=lambda _s: None, worker_id="t").run(
        max_jobs=5, max_seconds=60
    )
    with db.transaction() as s:
        assert s.get(Company, cid).research_state is ResearchState.RESEARCHED  # type: ignore[union-attr]
    return cid


def _ctx(db: Database, settings: Settings, notifier: RecordingNotifier) -> TaskContext:
    return TaskContext(
        database=db,
        settings=settings,
        module=AgentModule.OPPORTUNITY_SCORING,
        job_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        search_provider_factory=lambda _s: None,
        notifier=notifier,
    )


def test_researched_company_becomes_qualified_hot_lead(db: Database, settings: Settings) -> None:
    cid = _researched(db, settings, phones=("+998901234567",), emails=("info@lazzat.uz",))
    notifier = RecordingNotifier()
    message = run_scoring(_ctx(db, settings, notifier), {"company_id": str(cid)})
    assert "QUALIFIED" in message

    with db.transaction() as s:
        company = s.get(Company, cid)
        assert company is not None and company.research_state is ResearchState.ANALYZED
        lead = s.scalars(select(Lead).where(Lead.company_id == cid)).one()
        assert lead.stage is LeadStage.QUALIFIED
        finding = s.scalars(select(ResearchFinding).where(ResearchFinding.company_id == cid)).one()
        opps = {o.service: o for o in s.scalars(select(Opportunity))}
        assert set(opps) == {"business_website", "telegram_bot"}
        # Every opportunity points at the evidence it rests on.
        assert opps["business_website"].finding_ids == [str(finding.id)]
        assert opps["business_website"].reasons == ["no_website"]
        row = s.scalars(select(LeadScore)).one()
        assert row.lead_id == lead.id and row.total == round(600 / 7)
        assert row.missing == ["activity"]
        components = {c.component: c for c in row.components}
        assert components["activity"].value is None
        assert components["contactability"].value == 65
        assert row.weights["service_fit"] == 3.0

    assert len(notifier.messages) == 1 and "Lazzat" in notifier.messages[0]
    # Already ANALYZED: a duplicate job changes nothing and notifies no one again.
    assert "skipped" in run_scoring(_ctx(db, settings, notifier), {"company_id": str(cid)})
    assert len(notifier.messages) == 1
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(LeadScore)) == 1


def test_company_without_contacts_stays_candidate(db: Database, settings: Settings) -> None:
    cid = _researched(db, settings)
    notifier = RecordingNotifier()
    assert "CANDIDATE" in run_scoring(_ctx(db, settings, notifier), {"company_id": str(cid)})
    with db.transaction() as s:
        assert s.scalars(select(Lead)).one().stage is LeadStage.CANDIDATE
        assert s.scalar(select(func.count()).select_from(Opportunity)) == 2
    assert notifier.messages == []


def test_owner_threshold_and_weights_are_used(db: Database, settings: Settings) -> None:
    cid = _researched(db, settings, phones=("+998901234567",))
    with db.transaction() as s:
        s.add(
            ScoringSettings(
                key="default", weights={"service_fit": 0, "bogus": 5}, qualify_threshold=99
            )
        )
    run_scoring(_ctx(db, settings, RecordingNotifier()), {"company_id": str(cid)})
    with db.transaction() as s:
        assert s.scalars(select(Lead)).one().stage is LeadStage.CANDIDATE
        row = s.scalars(select(LeadScore)).one()
        assert row.weights["service_fit"] == 0.0 and "bogus" not in row.weights


def test_enqueue_is_idempotent_per_research_version(db: Database, settings: Settings) -> None:
    _researched(db, settings)
    with db.transaction() as s:
        assert enqueue_researched_companies(s) == 1
    with db.transaction() as s:
        assert enqueue_researched_companies(s) == 0
    with db.transaction() as s:
        assert s.scalar(select(func.count()).where(Job.job_type == SCORING_EVALUATE)) == 1


def test_deleted_company_is_ignored(db: Database, settings: Settings) -> None:
    ctx = _ctx(db, settings, RecordingNotifier())
    assert run_scoring(ctx, {"company_id": str(uuid.uuid4())}) == "company deleted"


def test_owner_hot_lead_threshold(db: Database, settings: Settings) -> None:
    from app.domain.actors import Actor
    from app.domain.agent_settings import ScoringExtraSettings
    from app.infrastructure.repositories.agent_settings import AgentSettingsRepository

    with db.transaction() as s:
        AgentSettingsRepository(s).save(
            AgentModule.OPPORTUNITY_SCORING,
            ScoringExtraSettings(hot_lead_threshold=99),
            Actor.user("owner"),
        )
    cid = _researched(db, settings, phones=("+998901234567",), emails=("info@lazzat.uz",))
    notifier = RecordingNotifier()
    assert "QUALIFIED" in run_scoring(_ctx(db, settings, notifier), {"company_id": str(cid)})
    assert notifier.messages == []  # 86 < owner's hot threshold 99

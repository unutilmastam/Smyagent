"""Opportunity & Scoring agent task: opportunities + explainable score + lead (M6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.workflow import WorkflowService
from app.domain.actors import Actor
from app.domain.agents import AgentModule
from app.domain.audit import Kind
from app.domain.companies import ResearchState
from app.domain.contacts import ContactKind
from app.domain.leads import LeadStage
from app.domain.scoring import (
    DEFAULT_QUALIFY_THRESHOLD,
    DEFAULT_WEIGHTS,
    HOT_LEAD_THRESHOLD,
    Component,
    FindingInput,
    ScoreInput,
    qualifies,
    score,
)
from app.infrastructure.database.models import (
    Company,
    Contact,
    Lead,
    LeadScore,
    Opportunity,
    ResearchFinding,
    ResearchRun,
    ScoreComponent,
    ScoringSettings,
    WebsiteAudit,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.jobs import JobRepository
from app.jobs.context import TaskContext

SCORING_EVALUATE = "scoring.evaluate"
ACTOR = Actor.agent(AgentModule.OPPORTUNITY_SCORING.value)


def load_settings(session: Session) -> tuple[dict[Component, float], int]:
    row = session.get(ScoringSettings, "default")
    weights = dict(DEFAULT_WEIGHTS)
    threshold = DEFAULT_QUALIFY_THRESHOLD
    if row is not None:
        for key, value in (row.weights or {}).items():
            try:
                weights[Component(key)] = max(0.0, float(value))
            except ValueError:
                continue
        threshold = row.qualify_threshold
    return weights, threshold


def enqueue_researched_companies(session: Session, *, limit: int = 50) -> int:
    jobs = JobRepository(session)
    queued = 0
    for company in session.scalars(
        select(Company)
        .where(Company.research_state == ResearchState.RESEARCHED)
        .order_by(Company.updated_at, Company.id)
        .limit(limit)
    ):
        _, created = jobs.enqueue(
            job_type=SCORING_EVALUATE,
            agent_module=AgentModule.OPPORTUNITY_SCORING.value,
            payload={"company_id": str(company.id)},
            idempotency_key=f"scoring:{company.id}:{company.updated_at:%Y%m%d%H%M%S}",
        )
        queued += int(created)
    return queued


def _inputs(session: Session, company: Company) -> tuple[ScoreInput, list[ResearchFinding]]:
    latest_run = session.scalars(
        select(ResearchRun.id)
        .where(ResearchRun.company_id == company.id)
        .order_by(ResearchRun.created_at.desc())
        .limit(1)
    ).first()
    findings = (
        list(
            session.scalars(
                select(ResearchFinding).where(ResearchFinding.research_run_id == latest_run)
            )
        )
        if latest_run
        else []
    )
    contacts = session.scalars(select(Contact).where(Contact.company_id == company.id)).all()
    kinds = {
        c.kind.value
        for c in contacts
        if c.kind is not ContactKind.EMAIL or c.is_role_address  # personal emails never count
    }
    audit = session.scalars(
        select(WebsiteAudit)
        .where(WebsiteAudit.company_id == company.id)
        .order_by(WebsiteAudit.fetched_at.desc())
        .limit(1)
    ).first()
    keys = {f.key for f in findings}
    if "no_website" in keys:
        reachable: bool | None = None
    elif audit is None:
        reachable = None if not keys else "website_unreachable" not in keys
    else:
        reachable = audit.score is not None
    recent: bool | None = None
    if audit is not None:
        check = next((c for c in audit.checks if c.get("key") == "copyright_year"), None)
        if check is not None:
            recent = check.get("severity") == "ok"
    data = ScoreInput(
        country=company.country,
        findings=[FindingInput(f.key, f.kind is Kind.FACT, f.confidence) for f in findings],
        contact_kinds=frozenset(kinds),
        researched=latest_run is not None,
        website_reachable=reachable,
        recent_copyright=recent,
    )
    return data, findings


def run_scoring(ctx: TaskContext, payload: dict[str, Any]) -> str:
    company_id = uuid.UUID(str(payload["company_id"]))
    with ctx.database.transaction() as session:
        company = session.get(Company, company_id)
        if company is None:
            return "company deleted"
        if company.research_state is not ResearchState.RESEARCHED:
            return f"{company.name}: skipped ({company.research_state.value})"
        weights, threshold = load_settings(session)
        data, findings = _inputs(session, company)
        result = score(data, weights)
        by_key: dict[str, list[str]] = {}
        for f in findings:
            by_key.setdefault(f.key, []).append(str(f.id))

        session.execute(delete(Opportunity).where(Opportunity.company_id == company_id))
        for opp in result.opportunities:
            session.add(
                Opportunity(
                    company_id=company_id,
                    service=opp.service.value,
                    strength=opp.strength,
                    reasons=list(opp.reasons),
                    finding_ids=[fid for key in opp.reasons for fid in by_key.get(key, [])],
                )
            )

        workflow = WorkflowService(session)
        lead = session.scalars(select(Lead).where(Lead.company_id == company_id)).first()
        if lead is None:
            lead = workflow.create_lead(company_id, ACTOR)
        qualified_now = False
        if lead.stage is LeadStage.CANDIDATE and qualifies(result, threshold):
            best = result.opportunities[0].service.value
            workflow.transition_lead(
                lead.id, LeadStage.QUALIFIED, ACTOR, f"score {result.total}: {best}"
            )
            qualified_now = True

        row = LeadScore(
            company_id=company_id,
            lead_id=lead.id,
            total=result.total,
            version=result.version,
            weights={c.value: w for c, w in weights.items()},
            missing=[c.value for c in result.missing],
            computed_at=utcnow(),
        )
        row.components = [
            ScoreComponent(
                component=c.component.value,
                value=c.value,
                weight=weights[c.component],
                explanation=c.explanation[:300],
            )
            for c in result.components
        ]
        session.add(row)
        workflow.transition_company(
            company_id, ResearchState.ANALYZED, ACTOR, f"score {result.total}"
        )
        name, total = company.name, result.total
        best_service = result.opportunities[0].service.value if result.opportunities else None

    if qualified_now and total >= HOT_LEAD_THRESHOLD:
        ctx.notifier.notify(f"🔥 Yangi issiq lid: {name} — ball {total}, ehtiyoj: {best_service}")
    status = "QUALIFIED" if qualified_now else "CANDIDATE"
    return f"{name}: ball {total}, {len(result.opportunities)} ta imkoniyat, {status}"

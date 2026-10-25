"""Seed a researched, scored, QUALIFIED company and draft/gate its offer (M7 tests)."""

from __future__ import annotations

import uuid

from app.application.proposals import ProposalService
from app.application.workflow import WorkflowService
from app.domain.actors import Actor
from app.domain.audit import Kind
from app.domain.leads import LeadStage
from app.infrastructure.database import Database
from app.infrastructure.database.models import Opportunity, ResearchFinding, ResearchRun
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany

ACTOR = Actor.agent("opportunity_scoring")


def qualified_lead(db: Database, name: str = "Lazzat Oshxonasi", country: str = "UZ") -> uuid.UUID:
    with db.transaction() as s:
        cid = CompanyRepository(s).add(NewCompany(name=name, country=country, city="Denov")).id
        run = ResearchRun(company_id=cid)
        s.add(run)
        s.flush()
        s.add_all(
            [
                ResearchFinding(
                    company_id=cid,
                    research_run_id=run.id,
                    key="no_website",
                    kind=Kind.FACT,
                    statement="No website was found for this business in its public listing.",
                    source_url="https://www.openstreetmap.org/node/1",
                    retrieved_at=utcnow(),
                ),
                ResearchFinding(
                    company_id=cid,
                    research_run_id=run.id,
                    key="unrelated_key",
                    kind=Kind.FACT,
                    statement="x",
                    retrieved_at=utcnow(),
                ),
            ]
        )
        s.add_all(
            [
                Opportunity(
                    company_id=cid,
                    service="business_website",
                    strength=0.9,
                    reasons=["no_website"],
                    finding_ids=[],
                ),
                Opportunity(
                    company_id=cid,
                    service="telegram_bot",
                    strength=0.5,
                    reasons=["no_website"],
                    finding_ids=[],
                ),
            ]
        )
        wf = WorkflowService(s)
        lead = wf.create_lead(cid, ACTOR)
        wf.transition_lead(lead.id, LeadStage.QUALIFIED, ACTOR)
        return lead.id


def awaiting_proposal(db: Database, **kw: str) -> uuid.UUID:
    """A proposal that passed the gate and waits for the owner."""
    lead_id = qualified_lead(db, **kw)
    with db.transaction() as s:
        proposal = ProposalService(s).draft_for_lead(lead_id)
        assert proposal is not None
        pid = proposal.id
    with db.transaction() as s:
        outcome = ProposalService(s).run_gate(pid, 1)
        assert outcome is not None and outcome.approval_requested
    return pid

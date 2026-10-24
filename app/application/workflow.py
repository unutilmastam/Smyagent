"""State transitions for companies and leads, always recorded with actor and reason."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.companies import ResearchState, ensure_research_transition
from app.domain.errors import DomainError
from app.domain.leads import INBOUND_ENTRY_STAGE, LeadStage, ensure_transition
from app.infrastructure.database.models import Company, Lead
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.workflow import WorkflowEventRepository


class NotFoundError(DomainError):
    pass


class WorkflowService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.events = WorkflowEventRepository(session)

    def transition_company(
        self, company_id: uuid.UUID, target: ResearchState, actor: Actor, reason: str | None = None
    ) -> Company:
        company = self.session.get(Company, company_id, with_for_update=True)
        if company is None:
            raise NotFoundError("company not found")
        current = company.research_state
        ensure_research_transition(current, target)
        company.research_state = target
        self.events.record(
            entity_type="company",
            entity_id=company.id,
            from_state=current.value,
            to_state=target.value,
            actor=actor,
            reason=reason,
        )
        return company

    def create_lead(self, company_id: uuid.UUID, actor: Actor, *, inbound: bool = False) -> Lead:
        if self.session.get(Company, company_id) is None:
            raise NotFoundError("company not found")
        stage = INBOUND_ENTRY_STAGE if inbound else LeadStage.CANDIDATE
        lead = Lead(company_id=company_id, stage=stage, stage_changed_at=utcnow())
        self.session.add(lead)
        self.session.flush()
        self.events.record(
            entity_type="lead",
            entity_id=lead.id,
            from_state=None,
            to_state=stage.value,
            actor=actor,
            reason="inbound client" if inbound else "created",
        )
        return lead

    def transition_lead(
        self, lead_id: uuid.UUID, target: LeadStage, actor: Actor, reason: str | None = None
    ) -> Lead:
        lead = self.session.get(Lead, lead_id, with_for_update=True)
        if lead is None:
            raise NotFoundError("lead not found")
        current = lead.stage
        ensure_transition(current, target, resume_stage=lead.resume_stage)
        if target in (LeadStage.PAUSED, LeadStage.ERROR):
            lead.resume_stage = current
        elif current in (LeadStage.PAUSED, LeadStage.ERROR):
            lead.resume_stage = None
        lead.stage = target
        lead.stage_changed_at = utcnow()
        self.events.record(
            entity_type="lead",
            entity_id=lead.id,
            from_state=current.value,
            to_state=target.value,
            actor=actor,
            reason=reason,
        )
        return lead

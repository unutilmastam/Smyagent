from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.workflow import NotFoundError, WorkflowService
from app.domain.actors import Actor
from app.domain.companies import ResearchState
from app.domain.errors import InvalidTransitionError
from app.domain.leads import LeadStage
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.infrastructure.repositories.workflow import AuditLogRepository, WorkflowEventRepository

OWNER = Actor.user("owner")


def _company_id(session: Session) -> object:
    return CompanyRepository(session).add(NewCompany(name="Acme", country="UZ")).id


def test_company_research_transition_records_event(session: Session) -> None:
    service = WorkflowService(session)
    cid = _company_id(session)
    service.transition_company(cid, ResearchState.RESEARCH_PENDING, Actor.system("cron"))  # type: ignore[arg-type]
    session.commit()
    events = WorkflowEventRepository(session).history("company", cid)  # type: ignore[arg-type]
    assert [(e.from_state, e.to_state, e.actor) for e in events] == [
        ("NEW", "RESEARCH_PENDING", "system:cron")
    ]


def test_invalid_company_transition_changes_nothing(session: Session) -> None:
    service = WorkflowService(session)
    cid = _company_id(session)
    with pytest.raises(InvalidTransitionError):
        service.transition_company(cid, ResearchState.ANALYZED, OWNER)  # type: ignore[arg-type]
    assert WorkflowEventRepository(session).history("company", cid) == []  # type: ignore[arg-type]


def test_lead_pipeline_pause_resume_and_opt_out(session: Session) -> None:
    service = WorkflowService(session)
    lead = service.create_lead(_company_id(session), OWNER)  # type: ignore[arg-type]
    service.transition_lead(lead.id, LeadStage.QUALIFIED, Actor.agent("opportunity_scoring"))
    service.transition_lead(lead.id, LeadStage.PAUSED, OWNER, "client on holiday")
    assert lead.resume_stage is LeadStage.QUALIFIED
    with pytest.raises(InvalidTransitionError):
        service.transition_lead(lead.id, LeadStage.APPROVED, OWNER)
    service.transition_lead(lead.id, LeadStage.QUALIFIED, OWNER)
    assert lead.resume_stage is None
    service.transition_lead(lead.id, LeadStage.DO_NOT_CONTACT, Actor.agent("conversation"), "stop")
    with pytest.raises(InvalidTransitionError):
        service.transition_lead(lead.id, LeadStage.CANDIDATE, OWNER)
    session.commit()

    stages = [e.to_state for e in WorkflowEventRepository(session).history("lead", lead.id)]
    assert stages == ["CANDIDATE", "QUALIFIED", "PAUSED", "QUALIFIED", "DO_NOT_CONTACT"]


def test_inbound_lead_starts_at_responded(session: Session) -> None:
    lead = WorkflowService(session).create_lead(_company_id(session), OWNER, inbound=True)  # type: ignore[arg-type]
    assert lead.stage is LeadStage.RESPONDED


def test_one_lead_per_company(session: Session) -> None:
    service = WorkflowService(session)
    cid = _company_id(session)
    service.create_lead(cid, OWNER)  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        service.create_lead(cid, OWNER)  # type: ignore[arg-type]


def test_missing_entities(session: Session) -> None:
    import uuid

    with pytest.raises(NotFoundError):
        WorkflowService(session).transition_lead(uuid.uuid4(), LeadStage.QUALIFIED, OWNER)


def test_audit_log_redacts_secrets(session: Session) -> None:
    entry = AuditLogRepository(session).add(
        actor=OWNER,
        action="settings.update",
        details={"api_key": "sk-123", "note": "token=abcdef", "field": "AI_PROVIDER"},
    )
    session.commit()
    assert entry.details is not None
    assert entry.details["api_key"] == "***"
    assert "abcdef" not in entry.details["note"]
    assert entry.details["field"] == "AI_PROVIDER"

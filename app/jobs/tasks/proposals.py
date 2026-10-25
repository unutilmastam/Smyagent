"""Proposal agent (draft offers) and Quality Gate agent tasks (M7)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.proposals import GateOutcome, ProposalService, owner_notification
from app.domain.agents import AgentModule
from app.domain.leads import LeadStage
from app.infrastructure.database.models import Company, Lead, Proposal
from app.infrastructure.repositories.jobs import JobRepository
from app.jobs.context import TaskContext

PROPOSAL_DRAFT = "proposal.draft"
GATE_REVIEW = "quality_gate.review"


def enqueue_qualified_leads(session: Session, *, limit: int = 20) -> int:
    """One draft job per QUALIFIED lead that has no offer yet."""
    jobs = JobRepository(session)
    queued = 0
    for lead in session.scalars(
        select(Lead)
        .outerjoin(Proposal, Proposal.lead_id == Lead.id)
        .where(Lead.stage == LeadStage.QUALIFIED, Proposal.id.is_(None))
        .order_by(Lead.stage_changed_at, Lead.id)
        .limit(limit)
    ):
        _, created = jobs.enqueue(
            job_type=PROPOSAL_DRAFT,
            agent_module=AgentModule.PROPOSAL_REQUIREMENTS.value,
            payload={"lead_id": str(lead.id)},
            idempotency_key=f"proposal:{lead.id}:{lead.stage_changed_at:%Y%m%d%H%M%S}",
        )
        queued += int(created)
    return queued


def enqueue_gate(session: Session, proposal_id: uuid.UUID, number: int) -> None:
    JobRepository(session).enqueue(
        job_type=GATE_REVIEW,
        agent_module=AgentModule.QUALITY_GATE.value,
        payload={"proposal_id": str(proposal_id), "version": number},
        idempotency_key=f"gate:{proposal_id}:{number}",
    )


def run_proposal_draft(ctx: TaskContext, payload: dict[str, Any]) -> str:
    lead_id = uuid.UUID(str(payload["lead_id"]))
    ctx.progress("taklif tayyorlanmoqda", 30)
    with ctx.database.transaction() as session:
        proposal = ProposalService(session).draft_for_lead(lead_id)
        if proposal is None:
            return "taklif kerak emas (lid tayyor emas yoki imkoniyat yo'q)"
        enqueue_gate(session, proposal.id, proposal.current_version)
        company = session.get(Company, proposal.company_id)
        name = company.name if company else "?"
        services = ", ".join(proposal.versions[0].services)
    return f"{name}: taklif v1 ({services}) → Quality Gate"


def run_quality_gate(ctx: TaskContext, payload: dict[str, Any]) -> str:
    proposal_id = uuid.UUID(str(payload["proposal_id"]))
    number = int(payload["version"])
    with ctx.database.transaction() as session:
        outcome: GateOutcome | None = ProposalService(session).run_gate(proposal_id, number)
        if outcome is None:
            return "skipped (eski versiya yoki allaqachon tekshirilgan)"
        proposal = session.get(Proposal, proposal_id)
        assert proposal is not None
        company = session.get(Company, proposal.company_id)
        name = company.name if company else "?"
        message = None
        if outcome.approval_requested:
            message = owner_notification(
                proposal, name, outcome, base_url=ctx.settings.app_base_url
            )
    # Notify after commit: the owner can act on the buttons immediately.
    if message is not None:
        ctx.notifier.notify(*message)
    verdict = outcome.result.verdict.value
    return f"{name}: v{number} {verdict} ({', '.join(outcome.result.codes) or 'ok'})"

"""Proposal agent, Quality Gate agent and owner decisions against a real schema (M7)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest
from sqlalchemy import delete, func, select

from app.application.controls import AgentControlService, Button
from app.application.proposals import ProposalService, ProposalStateError
from app.core.config import Settings
from app.domain.actors import Actor
from app.domain.agents import AgentModule, ControlState
from app.domain.errors import DomainError
from app.domain.leads import LeadStage
from app.domain.proposals import ApprovalStatus, ProposalStatus
from app.domain.quality_gate import Verdict
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    ApprovalRequest,
    AuditLog,
    Job,
    Lead,
    Opportunity,
    Proposal,
    ResearchFinding,
)
from app.jobs.context import TaskContext
from app.jobs.runner import JobRunner
from app.jobs.tasks.proposals import (
    GATE_REVIEW,
    PROPOSAL_DRAFT,
    enqueue_qualified_leads,
    run_proposal_draft,
    run_quality_gate,
)
from tests.integration.proposal_helpers import awaiting_proposal, qualified_lead

OWNER = Actor.user("owner-1")


class RecordingNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, list[Button]]] = []

    def notify(self, text: str, buttons: Sequence[Button] = ()) -> None:
        self.messages.append((text, list(buttons)))


def _ctx(db: Database, settings: Settings, notifier: RecordingNotifier, module: AgentModule):
    return TaskContext(
        database=db,
        settings=settings,
        module=module,
        job_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        search_provider_factory=lambda _s: None,
        notifier=notifier,
    )


def _lead_stage(db: Database, pid: uuid.UUID) -> LeadStage:
    with db.transaction() as s:
        proposal = s.get(Proposal, pid)
        assert proposal is not None
        lead = s.get(Lead, proposal.lead_id)
        assert lead is not None
        return lead.stage


def _approvals(db: Database, pid: uuid.UUID) -> list[tuple[int, ApprovalStatus]]:
    with db.transaction() as s:
        return [
            (a.version, a.status)
            for a in s.scalars(
                select(ApprovalRequest)
                .where(ApprovalRequest.entity_id == pid)
                .order_by(ApprovalRequest.version)
            )
        ]


def test_draft_then_gate_then_owner_notified_once(db: Database, settings: Settings) -> None:
    lead_id = qualified_lead(db)
    with db.transaction() as s:
        assert enqueue_qualified_leads(s) == 1
        assert enqueue_qualified_leads(s) == 0  # idempotent
    notifier = RecordingNotifier()
    draft_msg = run_proposal_draft(
        _ctx(db, settings, notifier, AgentModule.PROPOSAL_REQUIREMENTS), {"lead_id": str(lead_id)}
    )
    assert "Quality Gate" in draft_msg
    with db.transaction() as s:
        proposal = s.scalars(select(Proposal)).one()
        pid = proposal.id
        version = proposal.versions[0]
        assert proposal.status is ProposalStatus.DRAFT and version.gate_verdict is None
        assert version.services == ["business_website", "telegram_bot"]
        finding = s.scalars(
            select(ResearchFinding).where(ResearchFinding.key == "no_website")
        ).one()
        assert version.finding_ids == [str(finding.id)]  # unrelated findings are not evidence
        gate_job = s.scalars(select(Job).where(Job.job_type == GATE_REVIEW)).one()
        assert gate_job.agent_module == "quality_gate"
    assert _lead_stage(db, pid) is LeadStage.PROPOSAL_DRAFTED

    ctx = _ctx(db, settings, notifier, AgentModule.QUALITY_GATE)
    assert "approved" in run_quality_gate(ctx, {"proposal_id": str(pid), "version": 1})
    assert _lead_stage(db, pid) is LeadStage.AWAITING_APPROVAL
    assert _approvals(db, pid) == [(1, ApprovalStatus.PENDING)]
    assert len(notifier.messages) == 1
    text, buttons = notifier.messages[0]
    assert "Lazzat Oshxonasi" in text and str(pid)[:8] in text
    assert [b.data for b in buttons[:2]] == [f"pa:{pid}", f"pr:{pid}"]
    # A repeated gate job is a no-op: no second request, no second notification.
    assert "skipped" in run_quality_gate(ctx, {"proposal_id": str(pid), "version": 1})
    assert len(notifier.messages) == 1 and len(_approvals(db, pid)) == 1


def test_second_draft_for_same_lead_is_refused(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        proposal = s.get(Proposal, pid)
        assert proposal is not None
        assert ProposalService(s).draft_for_lead(proposal.lead_id) is None
        assert s.scalar(select(func.count()).select_from(Proposal)) == 1


def test_no_opportunity_no_offer(db: Database) -> None:
    lead_id = qualified_lead(db)
    with db.transaction() as s:
        s.execute(delete(Opportunity))
    with db.transaction() as s:
        assert ProposalService(s).draft_for_lead(lead_id) is None


def test_owner_approves(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        ProposalService(s).approve(pid, OWNER)
    assert _lead_stage(db, pid) is LeadStage.APPROVED
    assert _approvals(db, pid) == [(1, ApprovalStatus.APPROVED)]
    with db.transaction() as s:
        assert s.scalars(select(AuditLog).where(AuditLog.action == "proposal.approve")).one()
        with pytest.raises(ProposalStateError):
            ProposalService(s).approve(pid, OWNER)  # double approval refused


def test_owner_rejects_and_lead_is_disqualified(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        ProposalService(s).reject(pid, OWNER, "  mos emas ")
    assert _lead_stage(db, pid) is LeadStage.DISQUALIFIED
    with db.transaction() as s:
        request = s.scalars(select(ApprovalRequest)).one()
        assert request.status is ApprovalStatus.REJECTED and request.reason == "mos emas"
        with pytest.raises(ProposalStateError):
            ProposalService(s).edit(pid, OWNER, title="x", body="y")


def test_edit_with_price_is_blocked_until_fixed(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        body = s.get(Proposal, pid).versions[0].body  # type: ignore[union-attr]
    with db.transaction() as s:
        outcome = ProposalService(s).edit(
            pid, OWNER, title="Taklif", body=body + "\nNarxi 2 mln so'm, 5 kun ichida."
        )
        assert outcome.result.verdict is Verdict.REJECTED
        assert {"price", "commitment"} <= set(outcome.result.codes)
    assert _lead_stage(db, pid) is LeadStage.PROPOSAL_DRAFTED
    assert _approvals(db, pid) == [(1, ApprovalStatus.CANCELLED)]
    with db.transaction() as s:
        assert s.get(Proposal, pid).status is ProposalStatus.NEEDS_EDIT  # type: ignore[union-attr]
        with pytest.raises(ProposalStateError):
            ProposalService(s).approve(pid, OWNER)

    with db.transaction() as s:
        fixed = ProposalService(s).edit(pid, OWNER, title="Taklif", body=body)
        assert fixed.result.verdict is Verdict.APPROVED and fixed.approval_requested
    assert _lead_stage(db, pid) is LeadStage.AWAITING_APPROVAL
    assert _approvals(db, pid) == [
        (1, ApprovalStatus.CANCELLED),
        (3, ApprovalStatus.PENDING),
    ]
    with db.transaction() as s:
        ProposalService(s).approve(pid, OWNER)
        proposal = s.get(Proposal, pid)
        assert proposal is not None and proposal.current_version == 3
        assert proposal.versions[0].created_by == "user:owner-1"


def test_edit_after_approval_needs_new_approval(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        service = ProposalService(s)
        service.approve(pid, OWNER)
    with db.transaction() as s:
        body = s.get(Proposal, pid).versions[0].body  # type: ignore[union-attr]
        ProposalService(s).edit(pid, OWNER, title="Yangi", body=body + "\n")
    assert _lead_stage(db, pid) is LeadStage.AWAITING_APPROVAL
    with db.transaction() as s:
        assert s.get(Proposal, pid).status is ProposalStatus.AWAITING_APPROVAL  # type: ignore[union-attr]


def test_edit_validates_input(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s, pytest.raises(DomainError):
        ProposalService(s).edit(pid, OWNER, title=" ", body="x")


def test_prefix_lookup(db: Database) -> None:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        service = ProposalService(s)
        assert service.find_by_prefix(str(pid)[:8]).id == pid  # type: ignore[union-attr]
        assert service.find_by_prefix(str(pid)[:3]) is None  # too short
        assert service.find_by_prefix("zzzzzzzz") is None


def test_stopped_quality_gate_claims_no_jobs(db: Database, settings: Settings) -> None:
    qualified_lead(db)
    with db.transaction() as s:
        AgentControlService(s).set_state(
            AgentModule.QUALITY_GATE.value, ControlState.STOPPED, OWNER, "test"
        )
    runner = JobRunner(db, settings, search_provider_factory=lambda _s: None, worker_id="t")
    summary = runner.run(max_jobs=5, max_seconds=60)
    assert not any("approved" in m for m in summary.messages)  # the gate never ran
    with db.transaction() as s:
        gate = s.scalars(select(Job).where(Job.job_type == GATE_REVIEW)).one()
        assert gate.status.value == "QUEUED"
        assert s.scalars(select(Job).where(Job.job_type == PROPOSAL_DRAFT)).one()
        assert s.scalars(select(Proposal)).one().status is ProposalStatus.DRAFT

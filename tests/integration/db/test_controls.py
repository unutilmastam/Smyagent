"""Kill switch enforcement (CLAUDE.md §13A.2 test list)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.control_snapshot import ControlSnapshotService
from app.application.controls import AgentControlService, ControlGate
from app.domain.actors import Actor
from app.domain.agents import AgentHaltedError, AgentModule, ControlState, SendingBlockedError
from app.domain.control_view import NodeStatus
from app.domain.errors import DomainError
from app.domain.jobs import JobStatus
from app.infrastructure.database.models import AgentRun, AgentRunStatus, AuditLog
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.jobs import JobRepository

OWNER = Actor.user("owner")
R = AgentModule.RESEARCH_AUDIT
D = AgentModule.DISCOVERY
CONV = AgentModule.CONVERSATION


def _gate(session: Session, sending: bool = True) -> ControlGate:
    return ControlGate(session, outbound_sending_enabled=sending)


def test_stopped_agent_claims_no_jobs(session: Session) -> None:
    jobs = JobRepository(session)
    jobs.enqueue(job_type="research.audit", agent_module=R.value)
    AgentControlService(session).set_state(R.value, ControlState.STOPPED, OWNER)
    eligible = _gate(session).eligible_modules()
    assert R.value not in eligible and D.value in eligible
    assert jobs.claim_next("runner", eligible_modules=eligible) is None


def test_global_stop_cancels_queued_outbound_and_blocks_send(session: Session) -> None:
    jobs = JobRepository(session)
    send, _ = jobs.enqueue(job_type="outbound.email", agent_module=CONV.value)
    other, _ = jobs.enqueue(job_type="research.audit", agent_module=R.value)
    gate = _gate(session)
    gate.ensure_may_send(CONV)  # allowed while ACTIVE

    change = AgentControlService(session).set_state("global", ControlState.STOPPED, OWNER, "test")
    assert change.cancelled_outbound == 1
    session.expire_all()
    assert jobs.get(send.id).status is JobStatus.CANCELLED  # type: ignore[union-attr]
    assert jobs.get(other.id).status is JobStatus.QUEUED  # type: ignore[union-attr]
    with pytest.raises(SendingBlockedError):
        gate.ensure_may_send(CONV)
    assert gate.eligible_modules() == []


def test_send_blocked_when_outbound_disabled(session: Session) -> None:
    with pytest.raises(SendingBlockedError):
        _gate(session, sending=False).ensure_may_send(CONV)


def test_pause_and_resume_preserve_queue(session: Session) -> None:
    jobs = JobRepository(session)
    job, _ = jobs.enqueue(job_type="discover", agent_module=D.value)
    service = AgentControlService(session)
    service.set_state(D.value, ControlState.PAUSED, OWNER)
    gate = _gate(session)
    assert jobs.claim_next("runner", eligible_modules=gate.eligible_modules()) is None
    with pytest.raises(AgentHaltedError) as exc:
        gate.checkpoint(D)
    assert exc.value.state is ControlState.PAUSED
    assert jobs.get(job.id).status is JobStatus.QUEUED  # type: ignore[union-attr]

    service.set_state(D.value, ControlState.ACTIVE, OWNER)
    claimed = jobs.claim_next("runner", eligible_modules=gate.eligible_modules())
    assert claimed is not None and claimed.id == job.id


def test_module_stop_cancels_running_work_but_keeps_queue(session: Session) -> None:
    jobs = JobRepository(session)
    jobs.enqueue(job_type="a", agent_module=R.value)
    queued, _ = jobs.enqueue(
        job_type="b", agent_module=R.value, run_after=utcnow() + timedelta(hours=1)
    )
    running = jobs.claim_next("runner", eligible_modules=[R.value])
    assert running is not None
    session.add(AgentRun(module=R.value, job_id=running.id, current_step="auditing x.uz (1/5)"))
    session.flush()

    change = AgentControlService(session).set_state(R.value, ControlState.STOPPED, OWNER)
    assert change.cancelled_running == 1
    session.expire_all()
    assert jobs.get(running.id).status is JobStatus.CANCELLED  # type: ignore[union-attr]
    assert jobs.get(queued.id).status is JobStatus.QUEUED  # type: ignore[union-attr]
    run = session.scalars(select(AgentRun)).one()
    assert run.status is AgentRunStatus.CANCELLED
    with pytest.raises(AgentHaltedError):
        _gate(session).ensure_may_call_ai(R)


def test_state_changes_are_audited(session: Session) -> None:
    AgentControlService(session).set_state(D.value, ControlState.PAUSED, OWNER, "lunch")
    entry = session.scalars(select(AuditLog).where(AuditLog.action == "agent_control.set")).one()
    assert entry.actor == "user:owner"
    assert entry.details is not None
    assert entry.details["from"] == "ACTIVE" and entry.details["to"] == "PAUSED"
    assert entry.details["reason"] == "lunch"


def test_unknown_agent_rejected(session: Session) -> None:
    with pytest.raises(DomainError):
        AgentControlService(session).set_state("hacker", ControlState.ACTIVE, OWNER)


def test_snapshot_reflects_real_state(session: Session) -> None:
    now = utcnow()
    jobs = JobRepository(session)
    jobs.enqueue(job_type="discover", agent_module=D.value)
    session.add(
        AgentRun(
            module=R.value,
            current_step="auditing lazzat.uz (3/5)",
            progress_pct=60,
            heartbeat_at=now - timedelta(seconds=5),
            cost_usd=Decimal("0.0123"),
        )
    )
    session.add(
        AgentRun(
            module=AgentModule.OPPORTUNITY_SCORING.value,
            current_step="scoring",
            heartbeat_at=now - timedelta(minutes=10),
        )
    )
    AgentControlService(session).set_state(
        AgentModule.QUALITY_GATE.value, ControlState.PAUSED, OWNER
    )
    session.flush()

    snap = ControlSnapshotService(session).build(
        timezone="Asia/Tashkent", ai_budget_today=Decimal("0.30"), now=now
    )
    research = snap.module(R.value)
    assert research is not None and research.status is NodeStatus.RUNNING
    assert research.current is not None and research.current.progress_pct == 60
    assert snap.module(AgentModule.OPPORTUNITY_SCORING.value).status is NodeStatus.STALLED  # type: ignore[union-attr]
    assert snap.module(AgentModule.QUALITY_GATE.value).status is NodeStatus.PAUSED  # type: ignore[union-attr]
    discovery = snap.module(D.value)
    assert discovery is not None and discovery.status is NodeStatus.IDLE and discovery.queued == 1
    assert snap.ai_cost_today_usd == Decimal("0.0123")
    data = snap.to_json()
    assert data["global_state"] == "ACTIVE"
    assert {m["key"] for m in data["modules"]} == {m.value for m in AgentModule}
    assert any("lazzat.uz" in item["text"] for item in data["feed"])

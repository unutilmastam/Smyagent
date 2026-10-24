from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.agents import AgentModule, ControlState
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.controls import AgentControlRepository
from app.infrastructure.repositories.jobs import JobLockRepository, JobRepository

DISCOVERY = AgentModule.DISCOVERY.value
RESEARCH = AgentModule.RESEARCH_AUDIT.value


def test_enqueue_is_idempotent(session: Session) -> None:
    repo = JobRepository(session)
    first, created = repo.enqueue(job_type="discover", agent_module=DISCOVERY, idempotency_key="k1")
    again, created_again = repo.enqueue(
        job_type="discover", agent_module=DISCOVERY, idempotency_key="k1"
    )
    assert created and not created_again
    assert again.id == first.id


def test_claim_respects_run_after_and_modules(session: Session) -> None:
    repo = JobRepository(session)
    now = utcnow()
    repo.enqueue(job_type="later", agent_module=DISCOVERY, run_after=now + timedelta(hours=1))
    research, _ = repo.enqueue(job_type="audit", agent_module=RESEARCH)
    session.commit()
    now = utcnow()

    assert repo.claim_next("w1", eligible_modules=[DISCOVERY], now=now) is None
    claimed = repo.claim_next("w1", eligible_modules=[DISCOVERY, RESEARCH], now=now)
    assert claimed is not None and claimed.id == research.id
    assert claimed.status is JobStatus.RUNNING
    assert claimed.attempts == 1
    assert repo.claim_next("w1", eligible_modules=[], now=now) is None


def test_two_runners_cannot_claim_the_same_job(db: Database) -> None:
    with db.transaction() as s:
        JobRepository(s).enqueue(job_type="one", agent_module=DISCOVERY)

    s1, s2 = db.session(), db.session()
    try:
        a = JobRepository(s1).claim_next("runner-a", eligible_modules=[DISCOVERY])
        s1.commit()
        b = JobRepository(s2).claim_next("runner-b", eligible_modules=[DISCOVERY])
        s2.commit()
    finally:
        s1.close()
        s2.close()
    assert a is not None
    assert b is None


def test_retryable_failure_requeues_with_backoff_then_fails(session: Session) -> None:
    repo = JobRepository(session)
    repo.enqueue(job_type="x", agent_module=DISCOVERY, max_attempts=2)
    now = utcnow()
    claimed = repo.claim_next("w", eligible_modules=[DISCOVERY], now=now)
    assert claimed is not None
    repo.fail(claimed, "timeout", retryable=True, now=now)
    assert claimed.status is JobStatus.QUEUED
    assert claimed.run_after > now

    claimed = repo.claim_next("w", eligible_modules=[DISCOVERY], now=claimed.run_after)
    assert claimed is not None and claimed.attempts == 2
    repo.fail(claimed, "timeout", retryable=True)
    assert claimed.status is JobStatus.FAILED


def test_non_retryable_failure_is_final(session: Session) -> None:
    repo = JobRepository(session)
    repo.enqueue(job_type="x", agent_module=DISCOVERY)
    job = repo.claim_next("w", eligible_modules=[DISCOVERY])
    assert job is not None
    repo.fail(job, "HTTP 401", retryable=False)
    assert job.status is JobStatus.FAILED and job.finished_at is not None


def test_stop_cancels_running_and_stale_jobs_requeue(session: Session) -> None:
    repo = JobRepository(session)
    repo.enqueue(job_type="a", agent_module=DISCOVERY)
    repo.enqueue(job_type="b", agent_module=RESEARCH)
    now = utcnow()
    a = repo.claim_next("w", eligible_modules=[DISCOVERY], now=now)
    b = repo.claim_next("w", eligible_modules=[RESEARCH], now=now)
    assert a and b
    session.commit()

    assert repo.cancel_running([DISCOVERY]) == 1
    assert (
        repo.requeue_stale(stale_after=timedelta(minutes=10), now=now + timedelta(minutes=11)) == 1
    )
    session.commit()
    session.expire_all()
    assert repo.get(a.id).status is JobStatus.CANCELLED  # type: ignore[union-attr]
    assert repo.get(b.id).status is JobStatus.QUEUED  # type: ignore[union-attr]


def test_lock_prevents_overlap_and_expires(db: Database) -> None:
    now = utcnow()
    ttl = timedelta(minutes=5)
    with db.transaction() as s:
        assert JobLockRepository(s).acquire("runner", "cron-1", ttl=ttl, now=now)
    with db.transaction() as s:
        assert not JobLockRepository(s).acquire("runner", "cron-2", ttl=ttl, now=now)
        assert JobLockRepository(s).acquire("runner", "cron-1", ttl=ttl, now=now)  # re-entrant
    with db.transaction() as s:
        later = now + timedelta(minutes=6)
        assert JobLockRepository(s).acquire("runner", "cron-2", ttl=ttl, now=later)
    with db.transaction() as s:
        assert not JobLockRepository(s).release("runner", "cron-1")
        assert JobLockRepository(s).release("runner", "cron-2")


def test_agent_controls_fail_closed_and_global_wins(session: Session) -> None:
    repo = AgentControlRepository(session)
    owner = Actor.user("owner")
    assert repo.effective(AgentModule.DISCOVERY) is ControlState.ACTIVE
    repo.set_state("global", ControlState.STOPPED, owner, "emergency")
    assert repo.effective(AgentModule.DISCOVERY) is ControlState.STOPPED
    repo.set_state("global", ControlState.ACTIVE, owner)
    repo.set_state(DISCOVERY, ControlState.PAUSED, owner)
    assert repo.effective(AgentModule.DISCOVERY) is ControlState.PAUSED
    assert repo.effective(AgentModule.CONVERSATION) is ControlState.ACTIVE

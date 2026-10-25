"""Job queue operations portable across MySQL/MariaDB, SQLite, PostgreSQL (ADR-0004).

Concurrency model: no `SELECT ... FOR UPDATE SKIP LOCKED` (not on older MariaDB,
not on SQLite). A job is claimed with a conditional UPDATE and checking rowcount,
so two runners can never both claim it.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import CursorResult, delete, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.jobs import JobStatus, retry_delay
from app.infrastructure.database.models import Job, JobLock
from app.infrastructure.database.types import utcnow


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(
        self,
        *,
        job_type: str,
        agent_module: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        run_after: datetime | None = None,
        max_attempts: int = 3,
    ) -> tuple[Job, bool]:
        """Insert a job. Returns (job, created). Same idempotency key -> existing job."""
        if idempotency_key is not None:
            existing = self.get_by_key(idempotency_key)
            if existing is not None:
                return existing, False
        job = Job(
            job_type=job_type,
            agent_module=agent_module,
            payload=payload or {},
            idempotency_key=idempotency_key,
            run_after=run_after or utcnow(),
            max_attempts=max_attempts,
        )
        try:
            with self.session.begin_nested():
                self.session.add(job)
        except IntegrityError:
            # Lost a race with a concurrent enqueue of the same key.
            if idempotency_key is None:
                raise
            existing = self.get_by_key(idempotency_key)
            if existing is None:
                raise
            return existing, False
        return job, True

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.session.get(Job, job_id)

    def get_by_key(self, idempotency_key: str) -> Job | None:
        return self.session.scalars(
            select(Job).where(Job.idempotency_key == idempotency_key)
        ).first()

    def claim_next(
        self,
        worker_id: str,
        *,
        eligible_modules: Iterable[str],
        now: datetime | None = None,
        candidates: int = 5,
    ) -> Job | None:
        """Atomically claim the oldest due job of an eligible (ACTIVE) module."""
        modules = list(eligible_modules)
        if not modules:
            return None
        now = now or utcnow()
        ids = self.session.scalars(
            select(Job.id)
            .where(
                Job.status == JobStatus.QUEUED,
                Job.run_after <= now,
                Job.agent_module.in_(modules),
            )
            .order_by(Job.run_after, Job.created_at, Job.id)
            .limit(candidates)
        ).all()
        for job_id in ids:
            result = self.session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
                .values(
                    status=JobStatus.RUNNING,
                    claimed_by=worker_id,
                    claimed_at=now,
                    heartbeat_at=now,
                    attempts=Job.attempts + 1,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if _rowcount(result) == 1:
                job = self.session.get(Job, job_id, populate_existing=True)
                return job
        return None

    def heartbeat(self, job: Job, *, now: datetime | None = None) -> None:
        job.heartbeat_at = now or utcnow()
        self.session.flush()

    def succeed(self, job: Job, *, now: datetime | None = None) -> None:
        now = now or utcnow()
        job.status = JobStatus.SUCCEEDED
        job.finished_at = now
        job.last_error = None
        self.session.flush()

    def fail(self, job: Job, error: str, *, retryable: bool, now: datetime | None = None) -> None:
        """Record a failure; requeue with backoff if retryable and attempts remain."""
        now = now or utcnow()
        job.last_error = error[:500]
        if retryable and job.attempts < job.max_attempts:
            job.status = JobStatus.QUEUED
            job.run_after = now + retry_delay(job.attempts)
            job.claimed_by = None
            job.claimed_at = None
        else:
            job.status = JobStatus.FAILED
            job.finished_at = now
        self.session.flush()

    def cancel_running(self, modules: Iterable[str], *, now: datetime | None = None) -> int:
        """Mark RUNNING jobs of the given modules CANCELLED (STOP semantics)."""
        now = now or utcnow()
        result = self.session.execute(
            update(Job)
            .where(Job.status == JobStatus.RUNNING, Job.agent_module.in_(list(modules)))
            .values(status=JobStatus.CANCELLED, finished_at=now, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        return _rowcount(result)

    def requeue_stale(self, *, stale_after: timedelta, now: datetime | None = None) -> int:
        """Return RUNNING jobs whose runner died (no heartbeat) to the queue.

        A job that already used all its attempts is FAILED instead (see `fail_stale`), so a
        job that kills the process every time (memory limit, host timeout) cannot loop.
        """
        now = now or utcnow()
        result = self.session.execute(
            update(Job)
            .where(
                Job.status == JobStatus.RUNNING,
                Job.heartbeat_at < now - stale_after,
                Job.attempts < Job.max_attempts,
            )
            .values(status=JobStatus.QUEUED, claimed_by=None, claimed_at=None, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        return _rowcount(result)

    def fail_stale(self, *, stale_after: timedelta, now: datetime | None = None) -> list[Job]:
        """FAIL stale RUNNING jobs that have no attempts left; returns them (for alerts)."""
        now = now or utcnow()
        jobs = list(
            self.session.scalars(
                select(Job).where(
                    Job.status == JobStatus.RUNNING,
                    Job.heartbeat_at < now - stale_after,
                    Job.attempts >= Job.max_attempts,
                )
            )
        )
        for job in jobs:
            job.status = JobStatus.FAILED
            job.finished_at = now
            job.claimed_by = job.claimed_at = None
            job.last_error = "stale: runner stopped during the job (time or memory limit?)"
        self.session.flush()
        return jobs


class JobLockRepository:
    """Named locks with expiry. Each call commits nothing; callers commit promptly."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def acquire(
        self, name: str, holder: str, *, ttl: timedelta, now: datetime | None = None
    ) -> bool:
        now = now or utcnow()
        expires = now + ttl
        try:
            with self.session.begin_nested():
                self.session.execute(
                    insert(JobLock).values(
                        name=name, holder=holder, acquired_at=now, expires_at=expires
                    )
                )
            return True
        except IntegrityError:
            pass
        # Row exists: take it over only if expired, or extend if we already hold it.
        result = self.session.execute(
            update(JobLock)
            .where(
                JobLock.name == name,
                or_(JobLock.expires_at < now, JobLock.holder == holder),
            )
            .values(holder=holder, acquired_at=now, expires_at=expires)
            .execution_options(synchronize_session=False)
        )
        return _rowcount(result) == 1

    def release(self, name: str, holder: str) -> bool:
        result = self.session.execute(
            delete(JobLock)
            .where(JobLock.name == name, JobLock.holder == holder)
            .execution_options(synchronize_session=False)
        )
        return _rowcount(result) == 1


def _rowcount(result: Any) -> int:
    return result.rowcount if isinstance(result, CursorResult) else 0

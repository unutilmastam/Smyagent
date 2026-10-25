"""M10: cron invocation records, deduplicated failure alerts, timeouts, retention, job admin."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.application.automation import AlertService, JobAdminService, cleanup, cron_view
from app.application.control_snapshot import ControlSnapshotService
from app.application.controls import Button
from app.application.workflow import NotFoundError
from app.core.config import Settings
from app.domain.actors import Actor
from app.domain.automation import ALERT_WINDOW, CronHealth, RunnerStatus
from app.domain.errors import DomainError
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    AgentRun,
    AgentRunStatus,
    AuditLog,
    Job,
    JobLock,
    OwnerAlert,
    RunnerRun,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.jobs import JobLockRepository, JobRepository
from app.jobs.context import RetryableTaskError, TaskContext
from app.jobs.runner import LOCK_NAME, JobRunner

OWNER = Actor.user("owner")
JOB = "test.work"


class RecordingNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, Sequence[Button]]] = []

    def notify(self, text: str, buttons: Sequence[Button] = ()) -> None:
        self.sent.append((text, buttons))


def _runner(db: Database, settings: Settings, handler: Any, **kw: Any) -> JobRunner:
    return JobRunner(
        db,
        settings,
        handlers={JOB: handler},
        search_provider_factory=lambda _s: None,
        notifier=kw.pop("notifier", None) or RecordingNotifier(),
        worker_id="test-runner",
        **kw,
    )


def _enqueue(db: Database, *, max_attempts: int = 1, key: str | None = None) -> Any:
    with db.transaction() as s:
        job, _ = JobRepository(s).enqueue(
            job_type=JOB, agent_module="discovery", max_attempts=max_attempts, idempotency_key=key
        )
        return job.id


def _fail(_ctx: TaskContext, _payload: dict[str, Any]) -> str:
    raise RuntimeError("boom 42")


def _ok(_ctx: TaskContext, _payload: dict[str, Any]) -> str:
    return "done"


def _records(db: Database) -> list[RunnerRun]:
    with db.transaction() as s:
        return list(s.scalars(select(RunnerRun).order_by(RunnerRun.started_at)))


def test_each_invocation_is_recorded(db: Database, settings: Settings) -> None:
    _enqueue(db)
    summary = _runner(db, settings, _ok).run(max_jobs=5, max_seconds=60)
    assert summary.succeeded == 1
    [record] = _records(db)
    assert record.status is RunnerStatus.OK and record.finished_at is not None
    assert record.succeeded == 1 and record.failed == 0 and record.cleaned_up
    with db.transaction() as s:
        assert cron_view(s).health is CronHealth.OK


def test_overlapping_invocation_is_recorded_as_locked(db: Database, settings: Settings) -> None:
    with db.transaction() as s:
        JobLockRepository(s).acquire(LOCK_NAME, "other-runner", ttl=timedelta(minutes=10))
    summary = _runner(db, settings, _ok).run(max_jobs=5, max_seconds=60)
    assert not summary.lock_acquired
    assert [r.status for r in _records(db)] == [RunnerStatus.LOCKED]


def test_runner_crash_is_recorded_alerted_and_lock_released(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    notifier = RecordingNotifier()
    runner = _runner(db, settings, _ok, notifier=notifier)

    def broken(_summary: Any) -> None:
        raise ZeroDivisionError("bug")

    monkeypatch.setattr(runner, "_prepare", broken)
    summary = runner.run(max_jobs=5, max_seconds=60)
    assert summary.error == "ZeroDivisionError"
    [record] = _records(db)
    assert record.status is RunnerStatus.ERROR and record.error == "ZeroDivisionError"
    assert len(notifier.sent) == 1 and "ZeroDivisionError" in notifier.sent[0][0]
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(JobLock)) == 0


def test_final_failure_alerts_once_per_window(db: Database, settings: Settings) -> None:
    notifier = RecordingNotifier()
    _enqueue(db)
    _runner(db, settings, _fail, notifier=notifier).run(max_jobs=5, max_seconds=60)
    assert len(notifier.sent) == 1
    text, buttons = notifier.sent[0]
    assert "test.work" in text and "RuntimeError" in text
    assert buttons[0].data and buttons[0].data.startswith("job_retry:")
    # The same failure again: counted, not sent.
    _enqueue(db)
    _runner(db, settings, _fail, notifier=notifier).run(max_jobs=5, max_seconds=60)
    assert len(notifier.sent) == 1
    with db.transaction() as s:
        alert = s.scalars(select(OwnerAlert)).one()
        assert alert.total == 2 and alert.pending == 1
        alert.last_sent_at = utcnow() - ALERT_WINDOW - timedelta(minutes=1)
    # After the window: sent again, mentioning the repeats.
    _enqueue(db)
    _runner(db, settings, _fail, notifier=notifier).run(max_jobs=5, max_seconds=60)
    assert len(notifier.sent) == 2 and "yana 1 marta" in notifier.sent[1][0]


def test_retryable_failure_is_not_alerted(db: Database, settings: Settings) -> None:
    notifier = RecordingNotifier()

    def flaky(_ctx: TaskContext, _payload: dict[str, Any]) -> str:
        raise RetryableTaskError("429")

    _enqueue(db, max_attempts=3)
    summary = _runner(db, settings, flaky, notifier=notifier).run(max_jobs=5, max_seconds=60)
    assert summary.retried == 1 and notifier.sent == []


def test_hanging_job_is_cut_and_retried(db: Database, settings: Settings) -> None:
    def hang(_ctx: TaskContext, _payload: dict[str, Any]) -> str:
        time.sleep(10)
        return "never"

    job_id = _enqueue(db, max_attempts=3)
    started = time.monotonic()
    summary = _runner(db, settings, hang, max_job_seconds=0.3).run(max_jobs=1, max_seconds=60)
    assert time.monotonic() - started < 5
    assert summary.timed_out == 1 and summary.retried == 1
    with db.transaction() as s:
        job = s.get(Job, job_id)
        assert job is not None and job.status is JobStatus.QUEUED
        assert job.last_error and job.last_error.startswith("timeout")
    # The database still works after the interrupted job (pool was reset).
    assert _runner(db, settings, _ok).run(max_jobs=1, max_seconds=60).error is None


def test_stale_job_without_attempts_left_fails_and_alerts(db: Database, settings: Settings) -> None:
    old = utcnow() - timedelta(minutes=30)
    with db.transaction() as s:
        dead = Job(
            job_type=JOB,
            agent_module="discovery",
            status=JobStatus.RUNNING,
            payload={},
            attempts=3,
            max_attempts=3,
            heartbeat_at=old,
        )
        alive = Job(
            job_type=JOB,
            agent_module="discovery",
            status=JobStatus.RUNNING,
            payload={},
            attempts=1,
            max_attempts=3,
            heartbeat_at=old,
            run_after=utcnow() + timedelta(hours=1),
        )
        s.add_all([dead, alive])
        s.flush()
        dead_id, alive_id = dead.id, alive.id
    notifier = RecordingNotifier()
    summary = _runner(db, settings, _ok, notifier=notifier).run(max_jobs=5, max_seconds=60)
    assert summary.failed_stale == 1 and summary.requeued_stale == 1
    with db.transaction() as s:
        assert s.get(Job, dead_id).status is JobStatus.FAILED  # type: ignore[union-attr]
        assert s.get(Job, alive_id).status is JobStatus.QUEUED  # type: ignore[union-attr]
    assert len(notifier.sent) == 1 and "stale" in notifier.sent[0][0]


def test_cleanup_keeps_failures_and_recent_history(db: Database) -> None:
    now = utcnow()
    old = now - timedelta(days=40)
    with db.transaction() as s:
        jobs = {
            "old_ok": Job(
                job_type=JOB,
                agent_module="discovery",
                status=JobStatus.SUCCEEDED,
                payload={},
                finished_at=old,
            ),
            "old_failed": Job(
                job_type=JOB,
                agent_module="discovery",
                status=JobStatus.FAILED,
                payload={},
                finished_at=old,
            ),
            "new_ok": Job(
                job_type=JOB,
                agent_module="discovery",
                status=JobStatus.SUCCEEDED,
                payload={},
                finished_at=now,
            ),
            "queued": Job(
                job_type=JOB, agent_module="discovery", status=JobStatus.QUEUED, payload={}
            ),
        }
        s.add_all(jobs.values())
        s.add(AgentRun(module="discovery", status=AgentRunStatus.SUCCEEDED, started_at=old))
        s.add(AgentRun(module="discovery", status=AgentRunStatus.RUNNING, started_at=old))
        s.add(RunnerRun(worker_id="w", status=RunnerStatus.OK, started_at=now - timedelta(days=20)))
        s.flush()
        ids = {k: j.id for k, j in jobs.items()}
    with db.transaction() as s:
        result = cleanup(s, now=now)
    assert (result.jobs, result.agent_runs, result.runner_runs) == (1, 1, 1)
    with db.transaction() as s:
        left = {k for k, i in ids.items() if s.get(Job, i) is not None}
        assert left == {"old_failed", "new_ok", "queued"}
        assert s.scalars(select(AgentRun.status)).all() == [AgentRunStatus.RUNNING]


def test_cleanup_runs_once_a_day(db: Database, settings: Settings) -> None:
    _runner(db, settings, _ok).run(max_jobs=1, max_seconds=60)
    _runner(db, settings, _ok).run(max_jobs=1, max_seconds=60)
    assert [r.cleaned_up for r in _records(db)] == [True, False]


def test_job_admin_retry_cancel_and_audit(db: Database) -> None:
    queued = _enqueue(db, key="a")
    with db.transaction() as s:
        failed = Job(
            job_type=JOB,
            agent_module="discovery",
            status=JobStatus.FAILED,
            payload={},
            attempts=3,
            last_error="x",
            finished_at=utcnow(),
        )
        s.add(failed)
        s.flush()
        failed_id = failed.id
    with db.transaction() as s:
        service = JobAdminService(s)
        with pytest.raises(DomainError):
            service.retry(queued, OWNER)  # only FAILED/CANCELLED
        job = service.retry(failed_id, OWNER)
        assert job.status is JobStatus.QUEUED and job.attempts == 0 and job.finished_at is None
        with pytest.raises(DomainError):
            service.retry(failed_id, OWNER)  # already queued again
    with db.transaction() as s:
        service = JobAdminService(s)
        assert service.cancel(queued, OWNER).status is JobStatus.CANCELLED
        assert service.find_by_prefix(str(failed_id)[:8]).id == failed_id
        with pytest.raises(NotFoundError):
            service.find_by_prefix("ffffffff")
        with pytest.raises(DomainError):
            service.find_by_prefix("ab")
        actions = s.scalars(select(AuditLog.action).order_by(AuditLog.created_at)).all()
    assert actions == ["job.retry", "job.cancel"]


def test_alert_service_dedups_by_key(db: Database) -> None:
    with db.transaction() as s:
        alerts = AlertService(s)
        assert alerts.raise_alert("k", "one") is not None
        assert alerts.raise_alert("k", "two") is None
        assert alerts.raise_alert("other", "three") is not None


def test_snapshot_reports_cron_health(db: Database, settings: Settings) -> None:
    with db.transaction() as s:
        snap = ControlSnapshotService(s).build(
            timezone="Asia/Tashkent", ai_budget_today=Decimal("0")
        )
    assert snap.to_json()["cron_health"] == "never"
    _runner(db, settings, _ok).run(max_jobs=1, max_seconds=60)
    with db.transaction() as s:
        snap = ControlSnapshotService(s).build(
            timezone="Asia/Tashkent", ai_budget_today=Decimal("0")
        )
    assert snap.cron_health == "ok" and snap.cron_minutes_ago == 0

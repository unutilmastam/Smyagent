"""Background automation services (M10): owner alerts, job administration, retention.

Alerts are decided inside the caller's transaction and *returned*; the caller sends
them after commit, so a slow Telegram call never holds a DB transaction open and a
rolled-back transaction never produces a notification.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import String, cast, delete, func, select
from sqlalchemy.orm import Session

from app.application.controls import Button, OwnerNotifier
from app.application.workflow import NotFoundError
from app.domain.actors import Actor
from app.domain.automation import (
    ALERT_WINDOW,
    RETENTION,
    RUNNER_RUN_RETENTION,
    CronView,
    alert_due,
    cron_health,
    error_category,
    failure_alert_key,
)
from app.domain.errors import DomainError
from app.domain.jobs import JobStatus
from app.infrastructure.database.models import AgentRun, AgentRunStatus, Job, OwnerAlert, RunnerRun
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.workflow import AuditLogRepository

CB_JOB_RETRY = "job_retry"


@dataclass(frozen=True)
class Alert:
    text: str
    buttons: tuple[Button, ...] = ()


@dataclass
class AlertOutbox:
    """Alerts collected during a transaction; `flush()` sends them after commit."""

    items: list[Alert] = field(default_factory=list)

    def add(self, alert: Alert | None) -> None:
        if alert is not None:
            self.items.append(alert)

    def flush(self, notifier: OwnerNotifier) -> int:
        sent = 0
        for alert in self.items:
            notifier.notify(alert.text, alert.buttons)  # best-effort, never raises
            sent += 1
        self.items.clear()
        return sent


class AlertService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def raise_alert(
        self,
        key: str,
        text: str,
        buttons: Sequence[Button] = (),
        *,
        now: datetime | None = None,
        window: timedelta = ALERT_WINDOW,
    ) -> Alert | None:
        """Count the occurrence; return the alert only if the key was not sent recently."""
        now = now or utcnow()
        row = self.session.scalars(select(OwnerAlert).where(OwnerAlert.alert_key == key)).first()
        if row is None:
            row = OwnerAlert(alert_key=key[:191], total=0, pending=0)
            self.session.add(row)
        row.total += 1
        if not alert_due(row.last_sent_at, now, window):
            row.pending += 1
            self.session.flush()
            return None
        repeats = row.pending
        row.pending = 0
        row.last_sent_at = now
        self.session.flush()
        if repeats:
            text += f"\n\n(oldingi xabardan beri yana {repeats} marta takrorlandi)"
        return Alert(text, tuple(buttons))

    def job_failed(self, job: Job, *, base_url: str, now: datetime | None = None) -> Alert | None:
        category = error_category(job.last_error)
        text = (
            "⚠️ Vazifa bajarilmadi\n"
            f"Agent: {job.agent_module}\n"
            f"Vazifa: {job.job_type}\n"
            f"Urinishlar: {job.attempts}/{job.max_attempts}\n"
            f"Xato: {category}"
        )
        buttons = [Button("🔁 Qayta urinish", data=f"{CB_JOB_RETRY}:{job.id}")]
        if base_url.startswith("https://"):
            buttons.append(Button("🔎 Ko'rish", url=f"{base_url.rstrip('/')}/jobs/{job.id}"))
        return self.raise_alert(
            failure_alert_key(job.job_type, job.last_error), text, buttons, now=now
        )

    def runner_crashed(self, error_class: str, *, now: datetime | None = None) -> Alert | None:
        return self.raise_alert(
            f"runner_error:{error_class}"[:191],
            "🛑 Fon ishlari (cron runner) xato bilan to'xtadi.\n"
            f"Xato turi: {error_class}\n"
            "Batafsil: ~/smyagent_data/runner.log",
            now=now,
        )


@dataclass(frozen=True)
class JobFilter:
    status: JobStatus | None = None
    module: str | None = None
    page: int = 1


class JobAdminService:
    """Owner-side view and actions on the queue (dashboard + owner bot)."""

    PAGE_SIZE = 25

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, flt: JobFilter) -> tuple[list[Job], int]:
        stmt = select(Job)
        count = select(func.count()).select_from(Job)
        if flt.status is not None:
            stmt = stmt.where(Job.status == flt.status)
            count = count.where(Job.status == flt.status)
        if flt.module:
            stmt = stmt.where(Job.agent_module == flt.module)
            count = count.where(Job.agent_module == flt.module)
        total = int(self.session.scalar(count) or 0)
        page = max(1, flt.page)
        rows = self.session.scalars(
            stmt.order_by(Job.updated_at.desc(), Job.id)
            .offset((page - 1) * self.PAGE_SIZE)
            .limit(self.PAGE_SIZE)
        ).all()
        return list(rows), total

    def counts(self) -> dict[JobStatus, int]:
        return {
            status: n
            for status, n in self.session.execute(
                select(Job.status, func.count()).group_by(Job.status)
            ).tuples()
        }

    def get(self, job_id: uuid.UUID) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError("job not found")
        return job

    def find_by_prefix(self, prefix: str) -> Job:
        """Owner bot shows 8-char ids; match one job by id prefix."""
        prefix = prefix.strip().lower()
        if len(prefix) < 6 or not all(c in "0123456789abcdef-" for c in prefix):
            raise DomainError("id kamida 6 belgi bo'lsin")
        rows = self.session.scalars(
            select(Job).where(cast(Job.id, String(36)).like(f"{prefix}%")).limit(2)
        ).all()
        if len(rows) != 1:
            raise NotFoundError("job not found" if not rows else "id ambiguous")
        return rows[0]

    def runs(self, job_id: uuid.UUID) -> list[AgentRun]:
        return list(
            self.session.scalars(
                select(AgentRun).where(AgentRun.job_id == job_id).order_by(AgentRun.started_at)
            )
        )

    def recent_failures(self, limit: int = 5) -> list[Job]:
        return list(
            self.session.scalars(
                select(Job)
                .where(Job.status == JobStatus.FAILED)
                .order_by(Job.finished_at.desc())
                .limit(limit)
            )
        )

    def retry(self, job_id: uuid.UUID, actor: Actor, *, now: datetime | None = None) -> Job:
        """FAILED or CANCELLED -> QUEUED now, with a fresh attempt budget."""
        job = self.get(job_id)
        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            raise DomainError(
                f"faqat xato yoki bekor qilingan vazifa qayta yuboriladi ({job.status.value})"
            )
        before = job.status.value
        job.status = JobStatus.QUEUED
        job.attempts = 0
        job.run_after = now or utcnow()
        job.claimed_by = job.claimed_at = job.finished_at = None
        self._audit(actor, "job.retry", job, before)
        return job

    def cancel(self, job_id: uuid.UUID, actor: Actor, *, now: datetime | None = None) -> Job:
        """Only queued jobs; a running job is stopped through the Control Center."""
        job = self.get(job_id)
        if job.status is not JobStatus.QUEUED:
            raise DomainError(f"faqat navbatdagi vazifa bekor qilinadi ({job.status.value})")
        job.status = JobStatus.CANCELLED
        job.finished_at = now or utcnow()
        self._audit(actor, "job.cancel", job, JobStatus.QUEUED.value)
        return job

    def _audit(self, actor: Actor, action: str, job: Job, before: str) -> None:
        self.session.flush()
        AuditLogRepository(self.session).add(
            actor=actor,
            action=action,
            entity_type="job",
            entity_id=job.id,
            details={"job_type": job.job_type, "from": before, "to": job.status.value},
        )


def latest_runner_run(session: Session) -> RunnerRun | None:
    return session.scalars(select(RunnerRun).order_by(RunnerRun.started_at.desc()).limit(1)).first()


def cron_view(session: Session, now: datetime | None = None) -> CronView:
    last = latest_runner_run(session)
    return cron_health(last.started_at if last else None, now or utcnow())


@dataclass(frozen=True)
class CleanupResult:
    jobs: int
    agent_runs: int
    runner_runs: int
    alerts: int


def cleanup(session: Session, *, now: datetime | None = None) -> CleanupResult:
    """Retention for shared hosting: delete finished history; FAILED jobs are kept."""
    now = now or utcnow()
    cutoff = now - RETENTION

    def _count(result: object) -> int:
        return int(getattr(result, "rowcount", 0) or 0)

    runs = _count(
        session.execute(
            delete(AgentRun)
            .where(AgentRun.status != AgentRunStatus.RUNNING, AgentRun.started_at < cutoff)
            .execution_options(synchronize_session=False)
        )
    )
    # The maintenance job running this cleanup is RUNNING (no finished_at): never matched.
    jobs = _count(
        session.execute(
            delete(Job)
            .where(
                Job.status.in_([JobStatus.SUCCEEDED, JobStatus.CANCELLED]),
                Job.finished_at < cutoff,
            )
            .execution_options(synchronize_session=False)
        )
    )
    runner_runs = _count(
        session.execute(
            delete(RunnerRun)
            .where(RunnerRun.started_at < now - RUNNER_RUN_RETENTION)
            .execution_options(synchronize_session=False)
        )
    )
    alerts = _count(
        session.execute(
            delete(OwnerAlert)
            .where(OwnerAlert.last_sent_at < cutoff, OwnerAlert.pending == 0)
            .execution_options(synchronize_session=False)
        )
    )
    return CleanupResult(jobs=jobs, agent_runs=runs, runner_runs=runner_runs, alerts=alerts)

"""Bounded job runner, invoked by cron (CLAUDE.md §16.3, ADR-0004):

    python -m app.jobs.runner --max-jobs 5 --max-seconds 240

One run: record the invocation (cron liveness) -> take the overlap lock -> requeue
jobs of crashed runs -> schedule due work -> claim and execute jobs of ACTIVE modules
until the job or time limit (each job also has its own time limit) -> release the
lock. A global STOP makes the runner exit at its next check. Final job failures and a
crash of the runner itself are reported to the owner bot, deduplicated (M10).
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.application.automation import AlertOutbox, AlertService, cleanup
from app.application.controls import ControlGate, OwnerNotifier
from app.application.outreach import INBOX_JOB, OutreachService
from app.core.config import ConfigurationError, Settings, get_settings
from app.core.logging import configure_logging
from app.domain.agents import GLOBAL_CONTROL, AgentHaltedError, AgentModule, ControlState
from app.domain.automation import CLEANUP_EVERY, RunnerStatus
from app.domain.budget import BudgetExhaustedError
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentRun, AgentRunStatus, RunnerRun
from app.infrastructure.database.types import utcnow
from app.infrastructure.email.inbox import Inbox, build_inbox
from app.infrastructure.email.smtp import EmailSender, build_email_sender
from app.infrastructure.http_fetcher.fetcher import SafeFetcher
from app.infrastructure.repositories.controls import AgentControlRepository
from app.infrastructure.repositories.jobs import JobLockRepository, JobRepository
from app.infrastructure.search_providers.base import ProviderError, SearchProvider
from app.infrastructure.search_providers.factory import build_search_provider
from app.infrastructure.telegram.client_bot import ClientMessenger, build_client_bot
from app.infrastructure.telegram.notifier import build_owner_notifier
from app.jobs.context import (
    DeferTaskError,
    JobTimeoutError,
    RetryableTaskError,
    TaskContext,
    time_limit,
)
from app.jobs.tasks import HANDLERS, Handler
from app.jobs.tasks.discovery import enqueue_due_targets
from app.jobs.tasks.proposals import enqueue_qualified_leads
from app.jobs.tasks.research import enqueue_new_companies
from app.jobs.tasks.scoring import enqueue_researched_companies

logger = logging.getLogger("app.runner")

LOCK_NAME = "job-runner"
# (job id, agent run id, job type, module, payload) of a claimed job
Claimed = tuple[uuid.UUID, uuid.UUID, str, str, dict[str, object]]
STALE_AFTER = timedelta(minutes=10)
# Per-job limit; well under STALE_AFTER so a slow job is cut before it looks dead.
DEFAULT_MAX_JOB_SECONDS = 120.0


@dataclass
class RunSummary:
    lock_acquired: bool = True
    scheduled: int = 0
    requeued_stale: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    halted: int = 0
    stopped_globally: bool = False
    failed_stale: int = 0
    timed_out: int = 0
    alerts_sent: int = 0
    cleaned_up: bool = False
    budget_deferred: int = 0
    error: str | None = None
    messages: list[str] = field(default_factory=list)


class JobRunner:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        handlers: dict[str, Handler] | None = None,
        search_provider_factory: Callable[
            [Settings], SearchProvider | None
        ] = build_search_provider,
        fetcher_factory: Callable[[], SafeFetcher] = SafeFetcher,
        notifier: OwnerNotifier | None = None,
        client_bot_factory: Callable[[Settings], ClientMessenger | None] = build_client_bot,
        email_sender_factory: Callable[[Settings], EmailSender | None] = build_email_sender,
        inbox_factory: Callable[[Settings], Inbox | None] = build_inbox,
        worker_id: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        max_job_seconds: float = DEFAULT_MAX_JOB_SECONDS,
    ) -> None:
        self.database = database
        self.settings = settings
        self.handlers = handlers if handlers is not None else HANDLERS
        self.search_provider_factory = search_provider_factory
        self.fetcher_factory = fetcher_factory
        self.notifier = notifier or build_owner_notifier(settings)
        self.client_bot_factory = client_bot_factory
        self.email_sender_factory = email_sender_factory
        self.inbox_factory = inbox_factory
        self.worker_id = (worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}")[:64]
        self.clock = clock
        self.max_job_seconds = max_job_seconds
        self.alerts = AlertOutbox()

    def run(self, *, max_jobs: int, max_seconds: float) -> RunSummary:
        summary = RunSummary()
        record_id = self._start_record()
        try:
            self._run(summary, max_jobs=max_jobs, max_seconds=max_seconds)
        except Exception as exc:  # the runner itself broke (DB down, bug): tell the owner
            logger.exception("runner_crashed")
            summary.error = type(exc).__name__
            with suppress(Exception), self.database.transaction() as session:
                self.alerts.add(AlertService(session).runner_crashed(summary.error))
        finally:
            with suppress(Exception):
                self._finish_record(record_id, summary)
            summary.alerts_sent = self.alerts.flush(self.notifier)
        return summary

    def _run(self, summary: RunSummary, *, max_jobs: int, max_seconds: float) -> None:
        deadline = self.clock() + max_seconds
        # A job started just before the deadline may run up to its own limit.
        ttl = timedelta(seconds=max_seconds + max(0.0, self.max_job_seconds) + 120)
        with self.database.transaction() as session:
            if not JobLockRepository(session).acquire(LOCK_NAME, self.worker_id, ttl=ttl):
                summary.lock_acquired = False
                return
        try:
            self._prepare(summary)
            while summary.succeeded + summary.failed + summary.retried < max_jobs:
                if self.clock() >= deadline or self._globally_stopped():
                    summary.stopped_globally = self._globally_stopped()
                    break
                job = self._claim()
                if job is None:
                    break
                self._execute(job, summary)
            if self.clock() < deadline:
                self._maybe_cleanup(summary)
        finally:
            with self.database.transaction() as session:
                JobLockRepository(session).release(LOCK_NAME, self.worker_id)

    def _maybe_cleanup(self, summary: RunSummary) -> None:
        """Retention cleanup about once a day, after the jobs (never delays real work)."""
        now = utcnow()
        with self.database.transaction() as session:
            recent = session.scalar(
                select(RunnerRun.id)
                .where(RunnerRun.cleaned_up.is_(True), RunnerRun.started_at > now - CLEANUP_EVERY)
                .limit(1)
            )
            if recent is not None:
                return
            result = cleanup(session, now=now)
        summary.cleaned_up = True
        logger.info("retention_cleanup", extra=asdict(result))

    # -- invocation record (cron liveness, M10) ----------------------------

    def _start_record(self) -> uuid.UUID | None:
        try:
            with self.database.transaction() as session:
                record = RunnerRun(worker_id=self.worker_id)
                session.add(record)
                session.flush()
                return record.id
        except Exception:  # DB unreachable: the run itself will report it
            logger.warning("runner_record_failed")
            return None

    def _finish_record(self, record_id: uuid.UUID | None, summary: RunSummary) -> None:
        if record_id is None:
            return
        if summary.error:
            status = RunnerStatus.ERROR
        elif not summary.lock_acquired:
            status = RunnerStatus.LOCKED
        elif summary.stopped_globally:
            status = RunnerStatus.STOPPED
        else:
            status = RunnerStatus.OK
        with self.database.transaction() as session:
            record = session.get(RunnerRun, record_id)
            if record is None:
                return
            record.status, record.finished_at = status, utcnow()
            record.scheduled, record.succeeded = summary.scheduled, summary.succeeded
            record.failed = summary.failed + summary.failed_stale
            record.retried, record.halted = summary.retried, summary.halted
            record.requeued_stale = summary.requeued_stale
            record.cleaned_up = summary.cleaned_up
            record.error = summary.error[:120] if summary.error else None

    # -- steps -------------------------------------------------------------

    def _prepare(self, summary: RunSummary) -> None:
        with self.database.transaction() as session:
            jobs = JobRepository(session)
            dead = jobs.fail_stale(stale_after=STALE_AFTER)
            summary.failed_stale = len(dead)
            alerts = AlertService(session)
            for job in dead:
                self.alerts.add(alerts.job_failed(job, base_url=self.settings.app_base_url))
            summary.requeued_stale = jobs.requeue_stale(stale_after=STALE_AFTER)
            jobs.release_budget_deferred()
            session.execute(
                update(AgentRun)
                .where(
                    AgentRun.status == AgentRunStatus.RUNNING,
                    AgentRun.heartbeat_at < utcnow() - STALE_AFTER,
                )
                .values(status=AgentRunStatus.FAILED, error_category="stale", finished_at=utcnow())
                .execution_options(synchronize_session=False)
            )
        with self.database.transaction() as session:
            gate = ControlGate(session, outbound_sending_enabled=False)
            if gate.state(AgentModule.DISCOVERY) is ControlState.ACTIVE:
                summary.scheduled += enqueue_due_targets(session)
        with self.database.transaction() as session:
            gate = ControlGate(session, outbound_sending_enabled=False)
            if gate.state(AgentModule.RESEARCH_AUDIT) is ControlState.ACTIVE:
                summary.scheduled += enqueue_new_companies(session)
        with self.database.transaction() as session:
            gate = ControlGate(session, outbound_sending_enabled=False)
            if gate.state(AgentModule.OPPORTUNITY_SCORING) is ControlState.ACTIVE:
                summary.scheduled += enqueue_researched_companies(session)
        with self.database.transaction() as session:
            gate = ControlGate(session, outbound_sending_enabled=False)
            if gate.state(AgentModule.PROPOSAL_REQUIREMENTS) is ControlState.ACTIVE:
                summary.scheduled += enqueue_qualified_leads(session)
        with self.database.transaction() as session:
            gate = ControlGate(session, outbound_sending_enabled=False)
            if gate.state(AgentModule.CONVERSATION) is ControlState.ACTIVE:
                summary.scheduled += OutreachService(session, self.settings).plan()
                if self.settings.imap_host:
                    now = utcnow()
                    _, new = JobRepository(session).enqueue(
                        job_type=INBOX_JOB,
                        agent_module=AgentModule.CONVERSATION.value,
                        idempotency_key=f"inbox:{now:%Y%m%d%H}:{now.minute // 15}",
                    )
                    summary.scheduled += int(new)

    def _globally_stopped(self) -> bool:
        with self.database.transaction() as session:
            states = AgentControlRepository(session).states()
        return states.get(GLOBAL_CONTROL, ControlState.STOPPED) is ControlState.STOPPED

    def _claim(self) -> Claimed | None:
        with self.database.transaction() as session:
            gate = ControlGate(
                session, outbound_sending_enabled=self.settings.outbound_sending_enabled
            )
            eligible = gate.eligible_modules()
            job = JobRepository(session).claim_next(self.worker_id, eligible_modules=eligible)
            if job is None:
                return None
            run = AgentRun(module=job.agent_module, job_id=job.id, current_step=job.job_type)
            session.add(run)
            session.flush()
            return job.id, run.id, job.job_type, job.agent_module, dict(job.payload or {})

    def _execute(self, claimed: Claimed, summary: RunSummary) -> None:
        job_id, run_id, job_type, module_key, payload = claimed
        handler = self.handlers.get(job_type)
        ctx = TaskContext(
            database=self.database,
            settings=self.settings,
            module=AgentModule(module_key),
            job_id=job_id,
            run_id=run_id,
            search_provider_factory=self.search_provider_factory,
            fetcher_factory=self.fetcher_factory,
            notifier=self.notifier,
            client_bot_factory=self.client_bot_factory,
            email_sender_factory=self.email_sender_factory,
            inbox_factory=self.inbox_factory,
        )
        outcome: str
        error: str | None = None
        retryable = False
        halted_state: ControlState | None = None
        defer_until: datetime | None = None
        try:
            if handler is None:
                raise LookupError(f"no handler for job type {job_type}")
            with time_limit(self.max_job_seconds):
                outcome = handler(ctx, payload)
        except AgentHaltedError as exc:
            halted_state, outcome = exc.state, f"halted: {exc.state.value}"
        except DeferTaskError as exc:
            defer_until, outcome = exc.run_after, f"deferred: {exc}"[:200]
        except BudgetExhaustedError as exc:
            self._budget_defer(job_id, run_id, exc, summary)
            return
        except JobTimeoutError as exc:
            # The alarm may have fired mid-query: drop pooled connections, start clean.
            self.database.dispose()
            summary.timed_out += 1
            retryable, error, outcome = True, str(exc)[:500], "error"
        except (RetryableTaskError, ProviderError) as exc:
            retryable = not isinstance(exc, ProviderError) or exc.retryable
            error, outcome = str(exc)[:500], "error"
        except Exception as exc:  # one bad job must not stop the run
            logger.exception("job_failed", extra={"job_id": str(job_id), "job_type": job_type})
            error, outcome = f"{type(exc).__name__}", "error"
        if defer_until is not None:
            self._defer(job_id, run_id, outcome, defer_until)
            return
        self._finish(job_id, run_id, outcome, error, retryable, halted_state, summary)

    def _budget_defer(
        self,
        job_id: uuid.UUID,
        run_id: uuid.UUID,
        exc: BudgetExhaustedError,
        summary: RunSummary,
    ) -> None:
        """BUDGET_DEFERRED until the next day/month; the owner is told once per day."""
        now = utcnow()
        with self.database.transaction() as session:
            job = JobRepository(session).get(job_id)
            run = session.get(AgentRun, run_id)
            if job is not None and job.status is JobStatus.RUNNING:
                job.status = JobStatus.BUDGET_DEFERRED
                job.claimed_by, job.claimed_at = None, None
                job.attempts = max(0, job.attempts - 1)
                job.run_after = exc.run_after
            if run is not None:
                run.status, run.current_step = AgentRunStatus.CANCELLED, f"budget: {exc}"[:191]
                run.finished_at = now
            self.alerts.add(
                AlertService(session).raise_alert(
                    f"budget_deferred:{now:%Y%m%d}",
                    "💤 AI byudjeti tugagani uchun AI ishlari keyinga qoldirildi "
                    f"({exc.window.value}). Byudjet: MONTHLY_AI_BUDGET_USD.",
                    now=now,
                    window=timedelta(hours=24),
                )
            )
        summary.budget_deferred += 1

    def _defer(self, job_id: uuid.UUID, run_id: uuid.UUID, outcome: str, until: datetime) -> None:
        with self.database.transaction() as session:
            job = JobRepository(session).get(job_id)
            run = session.get(AgentRun, run_id)
            if job is not None and job.status is JobStatus.RUNNING:
                job.status, job.claimed_by, job.claimed_at = JobStatus.QUEUED, None, None
                job.attempts = max(0, job.attempts - 1)
                job.run_after = until
            if run is not None:
                run.status, run.current_step = AgentRunStatus.SUCCEEDED, outcome
                run.finished_at = utcnow()

    def _finish(
        self,
        job_id: uuid.UUID,
        run_id: uuid.UUID,
        outcome: str,
        error: str | None,
        retryable: bool,
        halted_state: ControlState | None,
        summary: RunSummary,
    ) -> None:
        now = utcnow()
        with self.database.transaction() as session:
            jobs = JobRepository(session)
            job = jobs.get(job_id)
            run = session.get(AgentRun, run_id)
            if job is None or run is None:
                return
            if job.status is JobStatus.CANCELLED:  # STOP arrived while it ran
                run.status = AgentRunStatus.CANCELLED
                summary.halted += 1
            elif halted_state is ControlState.PAUSED:
                # PAUSED: put the job back untouched; it resumes when reactivated.
                job.status, job.claimed_by, job.claimed_at = JobStatus.QUEUED, None, None
                job.attempts = max(0, job.attempts - 1)
                run.status = AgentRunStatus.CANCELLED
                summary.halted += 1
            elif halted_state is ControlState.STOPPED:
                job.status, job.finished_at = JobStatus.CANCELLED, now
                run.status = AgentRunStatus.CANCELLED
                summary.halted += 1
            elif error is None:
                jobs.succeed(job, now=now)
                run.status, run.progress_pct = AgentRunStatus.SUCCEEDED, 100
                summary.succeeded += 1
                summary.messages.append(outcome)
            else:
                jobs.fail(job, error, retryable=retryable, now=now)
                run.status = AgentRunStatus.FAILED
                run.error_category = error[:64]
                if job.status is JobStatus.QUEUED:
                    summary.retried += 1
                else:
                    summary.failed += 1
                    self.alerts.add(
                        AlertService(session).job_failed(job, base_url=self.settings.app_base_url)
                    )
            run.finished_at = now
            run.heartbeat_at = now


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.jobs.runner")
    parser.add_argument("--max-jobs", type=int, default=5)
    parser.add_argument("--max-seconds", type=float, default=240)
    parser.add_argument("--max-job-seconds", type=float, default=DEFAULT_MAX_JOB_SECONDS)
    parser.add_argument(
        "--log-file", help="append JSON logs here, rotated at 1 MB x 3 (cron on shared hosting)"
    )
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    configure_logging(settings.log_level, log_file=args.log_file)
    database = Database(settings.database_url.get_secret_value())
    try:
        summary = JobRunner(
            database, settings, max_job_seconds=max(10.0, args.max_job_seconds)
        ).run(max_jobs=max(1, args.max_jobs), max_seconds=max(10.0, args.max_seconds))
    finally:
        database.dispose()
    logger.info(
        "runner_finished",
        extra={
            "lock_acquired": summary.lock_acquired,
            "scheduled": summary.scheduled,
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "retried": summary.retried,
            "halted": summary.halted,
            "stopped_globally": summary.stopped_globally,
            "failed_stale": summary.failed_stale,
            "timed_out": summary.timed_out,
            "alerts_sent": summary.alerts_sent,
            "error": summary.error,
        },
    )
    return 1 if summary.error else 0


if __name__ == "__main__":
    sys.exit(main())

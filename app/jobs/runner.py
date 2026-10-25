"""Bounded job runner, invoked by cron (CLAUDE.md §16.3, ADR-0004):

    python -m app.jobs.runner --max-jobs 5 --max-seconds 240

One run: take the overlap lock -> requeue jobs of crashed runs -> schedule due
discovery -> claim and execute jobs of ACTIVE modules until the job or time limit
-> release the lock. A global STOP makes the runner exit at its next check.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import update

from app.application.controls import ControlGate, OwnerNotifier
from app.core.config import ConfigurationError, Settings, get_settings
from app.core.logging import configure_logging
from app.domain.agents import GLOBAL_CONTROL, AgentHaltedError, AgentModule, ControlState
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentRun, AgentRunStatus
from app.infrastructure.database.types import utcnow
from app.infrastructure.http_fetcher.fetcher import SafeFetcher
from app.infrastructure.repositories.controls import AgentControlRepository
from app.infrastructure.repositories.jobs import JobLockRepository, JobRepository
from app.infrastructure.search_providers.base import ProviderError, SearchProvider
from app.infrastructure.search_providers.factory import build_search_provider
from app.infrastructure.telegram.client_bot import ClientMessenger, build_client_bot
from app.infrastructure.telegram.notifier import build_owner_notifier
from app.jobs.context import RetryableTaskError, TaskContext
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
        worker_id: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.database = database
        self.settings = settings
        self.handlers = handlers if handlers is not None else HANDLERS
        self.search_provider_factory = search_provider_factory
        self.fetcher_factory = fetcher_factory
        self.notifier = notifier or build_owner_notifier(settings)
        self.client_bot_factory = client_bot_factory
        self.worker_id = (worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}")[:64]
        self.clock = clock

    def run(self, *, max_jobs: int, max_seconds: float) -> RunSummary:
        summary = RunSummary()
        deadline = self.clock() + max_seconds
        ttl = timedelta(seconds=max_seconds + 120)
        with self.database.transaction() as session:
            if not JobLockRepository(session).acquire(LOCK_NAME, self.worker_id, ttl=ttl):
                summary.lock_acquired = False
                return summary
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
        finally:
            with self.database.transaction() as session:
                JobLockRepository(session).release(LOCK_NAME, self.worker_id)
        return summary

    # -- steps -------------------------------------------------------------

    def _prepare(self, summary: RunSummary) -> None:
        with self.database.transaction() as session:
            summary.requeued_stale = JobRepository(session).requeue_stale(stale_after=STALE_AFTER)
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
                summary.scheduled = enqueue_due_targets(session)
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
        )
        outcome: str
        error: str | None = None
        retryable = False
        halted_state: ControlState | None = None
        try:
            if handler is None:
                raise LookupError(f"no handler for job type {job_type}")
            outcome = handler(ctx, payload)
        except AgentHaltedError as exc:
            halted_state, outcome = exc.state, f"halted: {exc.state.value}"
        except (RetryableTaskError, ProviderError) as exc:
            retryable = not isinstance(exc, ProviderError) or exc.retryable
            error, outcome = str(exc)[:500], "error"
        except Exception as exc:  # one bad job must not stop the run
            logger.exception("job_failed", extra={"job_id": str(job_id), "job_type": job_type})
            error, outcome = f"{type(exc).__name__}", "error"
        self._finish(job_id, run_id, outcome, error, retryable, halted_state, summary)

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
            run.finished_at = now
            run.heartbeat_at = now


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.jobs.runner")
    parser.add_argument("--max-jobs", type=int, default=5)
    parser.add_argument("--max-seconds", type=float, default=240)
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    configure_logging(settings.log_level)
    database = Database(settings.database_url.get_secret_value())
    try:
        summary = JobRunner(database, settings).run(
            max_jobs=max(1, args.max_jobs), max_seconds=max(10.0, args.max_seconds)
        )
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
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

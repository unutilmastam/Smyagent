"""What a task handler gets: DB access, settings and a live progress reporter."""

from __future__ import annotations

import signal
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime

from sqlalchemy import update

from app.application.budget import BudgetService, UsageRecord
from app.application.controls import ControlGate, NullNotifier, OwnerNotifier
from app.core.config import Settings
from app.domain.agents import AgentModule
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentRun, Job
from app.infrastructure.database.types import utcnow
from app.infrastructure.email.inbox import Inbox, build_inbox
from app.infrastructure.email.smtp import EmailSender, build_email_sender
from app.infrastructure.http_fetcher.fetcher import SafeFetcher
from app.infrastructure.search_providers.base import SearchProvider
from app.infrastructure.telegram.client_bot import ClientMessenger, build_client_bot


class RetryableTaskError(RuntimeError):
    """Temporary failure (rate limit, timeout): the job is retried with backoff."""


class JobTimeoutError(RetryableTaskError):
    """The handler ran longer than the per-job limit (runner `--max-job-seconds`)."""


class DeferTaskError(RuntimeError):
    """Not now (daily cap, spacing): requeue at `run_after` without using an attempt."""

    def __init__(self, reason: str, run_after: datetime) -> None:
        super().__init__(reason)
        self.run_after = run_after


@dataclass
class TaskContext:
    database: Database
    settings: Settings
    module: AgentModule
    job_id: uuid.UUID
    run_id: uuid.UUID
    search_provider_factory: Callable[[Settings], SearchProvider | None]
    fetcher_factory: Callable[[], SafeFetcher] = SafeFetcher
    notifier: OwnerNotifier = field(default_factory=NullNotifier)
    client_bot_factory: Callable[[Settings], ClientMessenger | None] = build_client_bot
    email_sender_factory: Callable[[Settings], EmailSender | None] = build_email_sender
    inbox_factory: Callable[[Settings], Inbox | None] = build_inbox

    def progress(self, step: str, pct: int) -> None:
        """Visible on the Control Center immediately (own short transaction)."""
        now = utcnow()
        with self.database.transaction() as session:
            session.execute(
                update(AgentRun)
                .where(AgentRun.id == self.run_id)
                .values(
                    current_step=step[:191], progress_pct=max(0, min(100, pct)), heartbeat_at=now
                )
                .execution_options(synchronize_session=False)
            )
            session.execute(
                update(Job)
                .where(Job.id == self.job_id)
                .values(heartbeat_at=now)
                .execution_options(synchronize_session=False)
            )

    def ensure_may_call_ai(self) -> None:
        """Before every optional AI call (§13A.2 point 4, §12): kill switch, then budget.

        Raises AgentHaltedError (paused/stopped) or BudgetExhaustedError (the runner
        defers the job as BUDGET_DEFERRED until the next day/month).
        """
        self.checkpoint()
        with self.database.transaction() as session:
            BudgetService(session, self.settings).ensure_may_spend()

    def record_usage(self, usage: UsageRecord) -> None:
        """After a provider call: cost accounting; a budget alert is sent after commit."""
        usage = replace(usage, module=usage.module or self.module.value)
        usage = replace(
            usage, job_id=usage.job_id or self.job_id, run_id=usage.run_id or self.run_id
        )
        with self.database.transaction() as session:
            alert = BudgetService(session, self.settings).record(usage)
        if alert is not None:
            self.notifier.notify(alert.text, alert.buttons)

    def checkpoint(self) -> None:
        """Raise AgentHaltedError if the module was paused or stopped meanwhile."""
        with self.database.transaction() as session:
            ControlGate(
                session, outbound_sending_enabled=self.settings.outbound_sending_enabled
            ).checkpoint(self.module)


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """Raise JobTimeoutError inside the block after `seconds` (SIGALRM, main thread only).

    The cron runner is a plain CLI process on Linux, so SIGALRM is available. Elsewhere
    (threads, Windows) the limit is skipped and the runner's stale-job requeue remains
    the safety net.
    """
    usable = (
        seconds > 0
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )
    if not usable:
        yield
        return

    def _expired(_signum: int, _frame: object) -> None:
        raise JobTimeoutError(f"timeout: job ran longer than {int(seconds)} s")

    previous = signal.signal(signal.SIGALRM, _expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)

"""What a task handler gets: DB access, settings and a live progress reporter."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import update

from app.application.controls import ControlGate, NullNotifier, OwnerNotifier
from app.core.config import Settings
from app.domain.agents import AgentModule
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentRun, Job
from app.infrastructure.database.types import utcnow
from app.infrastructure.http_fetcher.fetcher import SafeFetcher
from app.infrastructure.search_providers.base import SearchProvider


class RetryableTaskError(RuntimeError):
    """Temporary failure (rate limit, timeout): the job is retried with backoff."""


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

    def checkpoint(self) -> None:
        """Raise AgentHaltedError if the module was paused or stopped meanwhile."""
        with self.database.transaction() as session:
            ControlGate(
                session, outbound_sending_enabled=self.settings.outbound_sending_enabled
            ).checkpoint(self.module)

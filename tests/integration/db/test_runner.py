"""Discovery agent + cron runner end to end (no network: the provider is a fake)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.controls import AgentControlService
from app.core.config import Settings
from app.domain.actors import Actor
from app.domain.agents import ControlState
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    AgentRun,
    AgentRunStatus,
    Company,
    CompanySource,
    DiscoveryTarget,
    Job,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.jobs import JobLockRepository
from app.infrastructure.search_providers.base import ProviderError, SearchQuery, SearchResult
from app.jobs.runner import LOCK_NAME, JobRunner
from app.jobs.tasks.discovery import enqueue_due_targets

OWNER = Actor.user("owner")


class FakeOsm:
    name = "osm"
    is_fixture = False

    def __init__(
        self,
        results: list[SearchResult] | None = None,
        error: Exception | None = None,
        on_search: Any = None,
    ) -> None:
        self.results = (
            results
            if results is not None
            else [
                SearchResult(
                    name="Denov Mebel",
                    country="UZ",
                    city="Denov",
                    industry="Retail: furniture",
                    domain="denovmebel.uz",
                    phones=("+998901112233",),
                    source_url="https://www.openstreetmap.org/node/1",
                    external_id="osm:node/1",
                ),
                SearchResult(
                    name="Surxon Market",
                    country="UZ",
                    city="Denov",
                    source_url="https://www.openstreetmap.org/node/2",
                    external_id="osm:node/2",
                ),
            ]
        )
        self.error = error
        self.on_search = on_search
        self.queries: list[SearchQuery] = []

    def search(self, query: SearchQuery) -> list[SearchResult]:
        self.queries.append(query)
        if self.on_search:
            self.on_search()
        if self.error:
            raise self.error
        return self.results


def _target(db: Database, categories: list[str] | None = None) -> Any:
    with db.transaction() as s:
        target = DiscoveryTarget(country="UZ", city="Denov", categories=categories or ["retail"])
        s.add(target)
        s.flush()
        return target.id


def _runner(db: Database, settings: Settings, provider: Any) -> JobRunner:
    return JobRunner(
        db, settings, search_provider_factory=lambda _s: provider, worker_id="test-runner"
    )


def _count(db: Database, model: Any, *where: Any) -> int:
    with db.transaction() as s:
        return int(s.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def test_scheduler_is_idempotent_and_respects_interval(session: Session) -> None:
    session.add(DiscoveryTarget(country="UZ", city="Termiz", categories=["food", "retail"]))
    session.add(DiscoveryTarget(country="UZ", city="Qarshi", categories=["food"], enabled=False))
    session.flush()
    now = utcnow()
    assert enqueue_due_targets(session, now=now) == 2
    assert enqueue_due_targets(session, now=now + timedelta(hours=1)) == 0  # not due
    assert enqueue_due_targets(session, now=now + timedelta(days=8)) == 2  # due again


def test_runner_discovers_companies_end_to_end(db: Database, settings: Settings) -> None:
    _target(db)
    provider = FakeOsm()
    summary = _runner(db, settings, provider).run(max_jobs=5, max_seconds=60)
    assert summary.lock_acquired and summary.scheduled == 1 and summary.succeeded == 1
    assert provider.queries[0].city == "Denov" and provider.queries[0].category == "retail"
    with db.transaction() as s:
        names = sorted(s.scalars(select(Company.name)).all())
        sources = s.scalars(select(CompanySource)).all()
        run = s.scalars(select(AgentRun)).one()
        job = s.scalars(select(Job)).one()
    assert names == ["Denov Mebel", "Surxon Market"]
    assert all(src.source_type == "osm" and not src.is_fixture for src in sources)
    assert run.status is AgentRunStatus.SUCCEEDED and run.progress_pct == 100
    assert run.current_step == "Denov/retail: 2 yangi, 0 dublikat, 0 xato"
    assert job.status is JobStatus.SUCCEEDED
    # Second run the same day: nothing new scheduled, duplicates never re-created.
    again = _runner(db, settings, provider).run(max_jobs=5, max_seconds=60)
    assert again.scheduled == 0 and _count(db, Company) == 2


def test_overlapping_runs_are_prevented(db: Database, settings: Settings) -> None:
    with db.transaction() as s:
        JobLockRepository(s).acquire(LOCK_NAME, "other-runner", ttl=timedelta(minutes=5))
    summary = _runner(db, settings, FakeOsm()).run(max_jobs=5, max_seconds=60)
    assert summary.lock_acquired is False


def test_paused_discovery_schedules_and_claims_nothing(db: Database, settings: Settings) -> None:
    _target(db)
    with db.transaction() as s:
        AgentControlService(s).set_state("discovery", ControlState.PAUSED, OWNER)
    summary = _runner(db, settings, FakeOsm()).run(max_jobs=5, max_seconds=60)
    assert summary.scheduled == 0 and summary.succeeded == 0
    assert _count(db, Company) == 0


def test_global_stop_makes_runner_exit(db: Database, settings: Settings) -> None:
    _target(db)
    with db.transaction() as s:
        enqueue_due_targets(s)
        AgentControlService(s).set_state("global", ControlState.STOPPED, OWNER)
    summary = _runner(db, settings, FakeOsm()).run(max_jobs=5, max_seconds=60)
    assert summary.stopped_globally and summary.succeeded == 0
    assert _count(db, Job, Job.status == JobStatus.QUEUED) == 1  # queue untouched


def test_pause_during_work_returns_job_to_queue(db: Database, settings: Settings) -> None:
    _target(db)

    def pause() -> None:
        with db.transaction() as s:
            AgentControlService(s).set_state("discovery", ControlState.PAUSED, OWNER)

    summary = _runner(db, settings, FakeOsm(on_search=pause)).run(max_jobs=5, max_seconds=60)
    assert summary.halted == 1
    assert _count(db, Company) == 0  # checkpoint before the first company
    with db.transaction() as s:
        job = s.scalars(select(Job)).one()
        run = s.scalars(select(AgentRun)).one()
    assert job.status is JobStatus.QUEUED and job.attempts == 0
    assert run.status is AgentRunStatus.CANCELLED


def test_rate_limit_is_retried_later(db: Database, settings: Settings) -> None:
    _target(db)
    provider = FakeOsm(error=ProviderError("OpenStreetMap: HTTP 429", retryable=True))
    summary = _runner(db, settings, provider).run(max_jobs=5, max_seconds=60)
    assert summary.retried == 1
    with db.transaction() as s:
        job = s.scalars(select(Job)).one()
        run = s.scalars(select(AgentRun)).one()
    assert job.status is JobStatus.QUEUED and job.run_after > utcnow()
    assert job.last_error == "OpenStreetMap: HTTP 429"
    assert run.status is AgentRunStatus.FAILED


def test_bad_request_fails_without_retry(db: Database, settings: Settings) -> None:
    _target(db)
    provider = FakeOsm(error=ProviderError("OpenStreetMap: HTTP 400", retryable=False))
    summary = _runner(db, settings, provider).run(max_jobs=5, max_seconds=60)
    assert summary.failed == 1
    assert _count(db, Job, Job.status == JobStatus.FAILED) == 1


def test_provider_off_is_reported_not_crashing(db: Database, settings: Settings) -> None:
    _target(db)
    summary = JobRunner(db, settings, search_provider_factory=lambda _s: None).run(
        max_jobs=5, max_seconds=60
    )
    assert summary.succeeded == 1 and "SEARCH_PROVIDER" in summary.messages[0]


def test_max_jobs_bounds_a_run(db: Database, settings: Settings) -> None:
    _target(db, categories=["retail", "food", "health"])
    summary = _runner(db, settings, FakeOsm(results=[])).run(max_jobs=2, max_seconds=60)
    assert summary.succeeded == 2
    assert _count(db, Job, Job.status == JobStatus.QUEUED) == 1


@pytest.mark.parametrize("stale_minutes", [11])
def test_stale_running_job_is_requeued(
    db: Database, settings: Settings, stale_minutes: int
) -> None:
    with db.transaction() as s:
        s.add(
            Job(
                job_type="discovery.search",
                agent_module="discovery",
                status=JobStatus.RUNNING,
                payload={},
                heartbeat_at=utcnow() - timedelta(minutes=stale_minutes),
            )
        )
    summary = _runner(db, settings, FakeOsm()).run(max_jobs=1, max_seconds=60)
    assert summary.requeued_stale == 1

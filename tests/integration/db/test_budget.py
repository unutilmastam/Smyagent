"""Budget enforcement, usage accounting and BUDGET_DEFERRED jobs (M11)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.application.budget import BudgetService, UsageRecord
from app.application.controls import Button
from app.core.config import Settings, load_settings
from app.domain.budget import BudgetExhaustedError, UsageKind
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import AgentRun, Job, ProviderUsage
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.jobs import JobRepository
from app.jobs.context import TaskContext
from app.jobs.runner import JobRunner

D = Decimal


class Notes:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def notify(self, text: str, buttons: Sequence[Button] = ()) -> None:
        self.sent.append(text)


def _settings(monthly: str = "10", daily: str = "1") -> Settings:
    return load_settings(
        _env_file=None, app_env="test", monthly_ai_budget_usd=monthly, daily_ai_budget_usd=daily
    )


def _ai(cost: str) -> UsageRecord:
    return UsageRecord(
        provider="anthropic",
        model="small",
        module="research_audit",
        tokens_in=1000,
        tokens_out=200,
        cost_usd=D(cost),
    )


def test_record_and_status(db: Database) -> None:
    with db.transaction() as s:
        svc = BudgetService(s, _settings())
        assert svc.record(_ai("0.25")) is None
        assert (
            svc.record(UsageRecord(provider="osm", module="discovery", kind=UsageKind.SEARCH))
            is None
        )
        st = svc.status()
        assert st.spent_today_usd == D("0.25") and st.allowed
        assert svc.searches_today() == 1 and svc.searches_today("google") == 0


def test_alerts_once_at_80_percent_and_at_exhaustion(db: Database) -> None:
    with db.transaction() as s:
        svc = BudgetService(s, _settings(monthly="10", daily="10"))
        assert svc.record(_ai("7")) is None
        warn = svc.record(_ai("1.5"))
        assert warn is not None and "8.50 / $10.00" in warn.text
        assert svc.record(_ai("0.1")) is None  # still ≥ 80 %: no second warning
        used = svc.record(_ai("2"))
        assert used is not None and "keyingi davrga" in used.text
        try:
            svc.ensure_may_spend()
        except BudgetExhaustedError as exc:
            assert exc.window.value == "month" and exc.run_after > utcnow()
        else:  # pragma: no cover
            raise AssertionError("budget not enforced")


def test_zero_budget_allows_no_ai(db: Database) -> None:
    with db.transaction() as s:
        svc = BudgetService(s, _settings(monthly="0", daily="0"))
        assert not svc.status().allowed


def _budget_job(db: Database) -> Any:
    with db.transaction() as s:
        job, _ = JobRepository(s).enqueue(
            job_type="test.ai", agent_module="research_audit", max_attempts=2
        )
        return job.id


def test_runner_defers_and_releases_budget_jobs(db: Database) -> None:
    def needs_ai(ctx: TaskContext, _payload: dict[str, Any]) -> str:
        ctx.ensure_may_call_ai()
        ctx.record_usage(
            UsageRecord(provider="anthropic", module="", cost_usd=D("0.01"), tokens_in=10)
        )
        return "ok"

    notes = Notes()
    job_id = _budget_job(db)
    runner = JobRunner(
        db,
        _settings(monthly="0", daily="0"),
        handlers={"test.ai": needs_ai},
        search_provider_factory=lambda _s: None,
        notifier=notes,
    )
    summary = runner.run(max_jobs=3, max_seconds=30)
    assert summary.budget_deferred == 1 and summary.failed == 0
    with db.transaction() as s:
        job = s.get(Job, job_id)
        assert job is not None and job.status is JobStatus.BUDGET_DEFERRED
        assert job.attempts == 0 and job.run_after > utcnow()
        job.run_after = utcnow() - timedelta(seconds=1)  # the new day has come
    assert len(notes.sent) == 1 and "byudjet" in notes.sent[0].lower()
    # With budget: released, run, usage recorded on the agent run too.
    ok = JobRunner(
        db,
        _settings(),
        handlers={"test.ai": needs_ai},
        search_provider_factory=lambda _s: None,
        notifier=notes,
    )
    assert ok.run(max_jobs=3, max_seconds=30).succeeded == 1
    with db.transaction() as s:
        assert s.get(Job, job_id).status is JobStatus.SUCCEEDED  # type: ignore[union-attr]
        usage = s.scalars(select(ProviderUsage)).one()
        assert usage.module == "research_audit" and usage.job_id == job_id
        run = s.scalars(
            select(AgentRun).where(AgentRun.job_id == job_id, AgentRun.cost_usd > 0)
        ).one()
        assert run.tokens_in == 10

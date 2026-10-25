"""Read model for the Virtual Office (`/api/v1/control/office`, CLAUDE.md §13A.3).

Collects real facts per module (control state, runs, queue, failures) and recent events,
then maps them with the pure `app.domain.office.character_state`. Small, indexed queries:
the page polls every 4 s.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.application.control_snapshot import start_of_local_day
from app.domain.agents import GLOBAL_CONTROL, PIPELINE, AgentModule, ControlState
from app.domain.automation import cron_health, error_category
from app.domain.conversation import BriefStatus
from app.domain.jobs import JobStatus
from app.domain.office import (
    ERROR_SHOWN_FOR,
    EVENT_WINDOW,
    AgentFacts,
    CharacterState,
    EventKind,
    FailureFact,
    RunFact,
    WaitFact,
    character_state,
    handoff,
    is_night,
    wait_kind,
)
from app.domain.outreach import Channel, OutreachStatus
from app.infrastructure.database.models import (
    AgentRun,
    AgentRunStatus,
    Company,
    Job,
    Lead,
    OrderBrief,
    OutreachEvent,
    Proposal,
    RunnerRun,
    WorkflowEvent,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.controls import AgentControlRepository

MAX_EVENTS = 20
MODULES: tuple[AgentModule, ...] = (AgentModule.ORCHESTRATOR, *PIPELINE)


@dataclass(frozen=True)
class AgentStats:
    done_today: int = 0
    failed_today: int = 0
    cost_today_usd: Decimal = Decimal("0")


@dataclass(frozen=True)
class OfficeEvent:
    id: str
    kind: EventKind
    module: str
    at: datetime
    to: str | None = None  # handoff target module
    text: str = ""


class OfficeSnapshotService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build(
        self, *, timezone: str, ai_budget_today: Decimal, now: datetime | None = None
    ) -> dict[str, Any]:
        now = now or utcnow()
        controls = AgentControlRepository(self.session)
        global_state = controls.states().get(GLOBAL_CONTROL, ControlState.STOPPED)
        global_stopped = global_state is ControlState.STOPPED
        runs = self._running_runs()
        due = self._due_jobs(now)
        failures = self._recent_failures(now)
        day_start = start_of_local_day(now, timezone)
        stats = self._stats(day_start)
        queued = self._queued_counts()

        agents = []
        for module in MODULES:
            facts = AgentFacts(
                module=module,
                effective=controls.effective(module),
                global_stopped=global_stopped,
                run=runs.get(module.value),
                due_jobs=due.get(module.value, 0),
                waiting=self._waiting(module, now),
                last_failure=failures.get(module.value),
            )
            state = character_state(facts, now)
            agents.append(_agent_json(state, facts, stats.get(module.value), queued))

        last_runner = self.session.scalar(select(func.max(RunnerRun.started_at)))
        cron = cron_health(last_runner, now)
        local = now.astimezone(ZoneInfo(timezone))
        cost_today = sum((s.cost_today_usd for s in stats.values()), Decimal("0"))
        return {
            "generated_at": now.isoformat(),
            "global_state": global_state.value,
            "local_time": local.strftime("%H:%M"),
            "night": is_night(local.hour),
            "cron_health": cron.health.value,
            "cron_minutes_ago": cron.minutes_ago,
            "agents": agents,
            "events": [_event_json(e) for e in self._events(now)],
            "today": self._funnel(day_start),
            "ai_cost_today_usd": str(cost_today.quantize(Decimal("0.0001"))),
            "ai_budget_today_usd": str(ai_budget_today),
        }

    # -- facts ---------------------------------------------------------------

    def _running_runs(self) -> dict[str, RunFact]:
        found: dict[str, RunFact] = {}
        for run in self.session.scalars(
            select(AgentRun)
            .where(AgentRun.status == AgentRunStatus.RUNNING)
            .order_by(AgentRun.heartbeat_at.desc())
        ):
            found.setdefault(
                run.module, RunFact(run.current_step, run.progress_pct, run.heartbeat_at)
            )
        return found

    def _due_jobs(self, now: datetime) -> dict[str, int]:
        return dict(
            self.session.execute(
                select(Job.agent_module, func.count())
                .where(Job.status == JobStatus.QUEUED, Job.run_after <= now)
                .group_by(Job.agent_module)
            ).all()
        )

    def _queued_counts(self) -> dict[str, int]:
        return dict(
            self.session.execute(
                select(Job.agent_module, func.count())
                .where(Job.status.in_([JobStatus.QUEUED, JobStatus.BUDGET_DEFERRED]))
                .group_by(Job.agent_module)
            ).all()
        )

    def _waiting(self, module: AgentModule, now: datetime) -> WaitFact | None:
        job = self.session.scalars(
            select(Job)
            .where(
                Job.agent_module == module.value,
                or_(
                    Job.status == JobStatus.BUDGET_DEFERRED,
                    (Job.status == JobStatus.QUEUED) & (Job.run_after > now),
                ),
            )
            .order_by(Job.run_after)
            .limit(1)
        ).first()
        if job is None:
            return None
        deferred_step = None
        if not job.last_error:
            deferred_step = self.session.scalar(
                select(AgentRun.current_step)
                .where(AgentRun.job_id == job.id)
                .order_by(AgentRun.started_at.desc())
                .limit(1)
            )
        deferred = bool(deferred_step and deferred_step.startswith("deferred:"))
        budget = job.status is JobStatus.BUDGET_DEFERRED
        reason = job.last_error or (deferred_step or "").removeprefix("deferred:").strip()
        kind = wait_kind(budget_deferred=budget, last_error=job.last_error, deferred=deferred)
        return WaitFact(kind, reason[:120], job.run_after)

    def _recent_failures(self, now: datetime) -> dict[str, FailureFact]:
        found: dict[str, FailureFact] = {}
        for job in self.session.scalars(
            select(Job)
            .where(Job.status == JobStatus.FAILED, Job.finished_at >= now - ERROR_SHOWN_FOR)
            .order_by(Job.finished_at.desc())
        ):
            if job.finished_at is not None:
                found.setdefault(
                    job.agent_module,
                    FailureFact(job.finished_at, error_category(job.last_error), str(job.id)),
                )
        return found

    def _stats(self, day_start: datetime) -> dict[str, AgentStats]:
        rows: dict[str, dict[str, Any]] = {}
        for module, status, count, cost in self.session.execute(
            select(
                AgentRun.module,
                AgentRun.status,
                func.count(),
                func.coalesce(func.sum(AgentRun.cost_usd), 0),
            )
            .where(AgentRun.started_at >= day_start)
            .group_by(AgentRun.module, AgentRun.status)
        ).all():
            row = rows.setdefault(module, {"done": 0, "failed": 0, "cost": Decimal("0")})
            if status is AgentRunStatus.SUCCEEDED:
                row["done"] += count
            elif status is AgentRunStatus.FAILED:
                row["failed"] += count
            row["cost"] += Decimal(str(cost or 0))
        return {
            k: AgentStats(v["done"], v["failed"], v["cost"].quantize(Decimal("0.0001")))
            for k, v in rows.items()
        }

    # -- events (each id is animated once by the page) -----------------------

    def _events(self, now: datetime) -> list[OfficeEvent]:
        since = now - EVENT_WINDOW
        events: list[OfficeEvent] = []
        for event_id, sent_at, company in self.session.execute(
            select(OutreachEvent.id, OutreachEvent.sent_at, Company.name)
            .join(Company, Company.id == OutreachEvent.company_id)
            .where(
                OutreachEvent.channel == Channel.EMAIL,
                OutreachEvent.status == OutreachStatus.SENT,
                OutreachEvent.sent_at >= since,
            )
            .order_by(OutreachEvent.sent_at.desc())
            .limit(MAX_EVENTS)
        ).all():
            events.append(
                OfficeEvent(
                    f"mail:{event_id}",
                    EventKind.EMAIL_SENT,
                    AgentModule.CONVERSATION.value,
                    sent_at or now,
                    text=company,
                )
            )
        for brief in self.session.scalars(
            select(OrderBrief)
            .where(OrderBrief.status == BriefStatus.CONFIRMED, OrderBrief.confirmed_at >= since)
            .limit(MAX_EVENTS)
        ):
            events.append(
                OfficeEvent(
                    f"order:{brief.id}",
                    EventKind.ORDER_CONFIRMED,
                    AgentModule.CONVERSATION.value,
                    brief.confirmed_at or now,
                    text=self._order_text(brief),
                )
            )
        for wf in self.session.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.created_at >= since)
            .order_by(WorkflowEvent.created_at.desc())
            .limit(MAX_EVENTS * 3)
        ):
            pair = handoff(wf.entity_type, wf.to_state)
            if pair is not None:
                events.append(
                    OfficeEvent(
                        f"wf:{wf.id}",
                        EventKind.HANDOFF,
                        pair[0].value,
                        wf.created_at,
                        to=pair[1].value,
                    )
                )
        events.sort(key=lambda e: e.at, reverse=True)
        return events[:MAX_EVENTS]

    def _order_text(self, brief: OrderBrief) -> str:
        name = None
        if brief.lead_id is not None:
            name = self.session.scalar(
                select(Company.name)
                .join(Lead, Lead.company_id == Company.id)
                .where(Lead.id == brief.lead_id)
            )
        services = ", ".join(brief.services or [])
        return " — ".join(p for p in (name, services) if p)

    def _funnel(self, day_start: datetime) -> dict[str, int]:
        def count(stmt: Any) -> int:
            return int(self.session.scalar(stmt) or 0)

        return {
            "found": count(
                select(func.count()).select_from(Company).where(Company.created_at >= day_start)
            ),
            "researched": count(
                select(func.count())
                .select_from(WorkflowEvent)
                .where(
                    WorkflowEvent.entity_type == "company",
                    WorkflowEvent.to_state == "RESEARCHED",
                    WorkflowEvent.created_at >= day_start,
                )
            ),
            "proposals": count(
                select(func.count()).select_from(Proposal).where(Proposal.created_at >= day_start)
            ),
            "emails": count(
                select(func.count())
                .select_from(OutreachEvent)
                .where(OutreachEvent.channel == Channel.EMAIL, OutreachEvent.sent_at >= day_start)
            ),
            "replies": count(
                select(func.count())
                .select_from(OutreachEvent)
                .where(OutreachEvent.replied_at >= day_start)
            ),
            "orders": count(
                select(func.count())
                .select_from(OrderBrief)
                .where(OrderBrief.confirmed_at >= day_start)
            ),
        }


def _agent_json(
    state: CharacterState,
    facts: AgentFacts,
    stats: AgentStats | None,
    queued: dict[str, int],
) -> dict[str, Any]:
    stats = stats or AgentStats()
    return {
        "key": state.module,
        "mode": state.mode.value,
        "detail": state.detail[:120],
        "progress_pct": state.progress_pct,
        "retry_at": state.retry_at.isoformat() if state.retry_at else None,
        "wait_kind": facts.waiting.kind.value if facts.waiting else None,
        "job_id": state.job_id,
        "stalled": state.stalled,
        "control": facts.effective.value,
        "queued": queued.get(state.module, 0),
        "done_today": stats.done_today,
        "failed_today": stats.failed_today,
        "cost_today_usd": str(stats.cost_today_usd),
    }


def _event_json(event: OfficeEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "kind": event.kind.value,
        "module": event.module,
        "to": event.to,
        "at": event.at.isoformat(),
        "text": event.text[:120],
    }

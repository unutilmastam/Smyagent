"""Small, indexed read model for `/api/v1/control/snapshot` and the `/control` page."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.agents import GLOBAL_CONTROL, AgentModule, ControlState
from app.domain.control_view import NodeStatus, node_status
from app.domain.jobs import JobStatus
from app.infrastructure.database.models import AgentRun, AgentRunStatus, Job, WorkflowEvent
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.controls import AgentControlRepository

FAILURE_WINDOW = timedelta(hours=1)
FEED_SIZE = 20


@dataclass(frozen=True)
class CurrentRun:
    run_id: uuid.UUID
    step: str | None
    progress_pct: int
    heartbeat_age_s: int


@dataclass(frozen=True)
class ModuleView:
    key: str
    state: str
    effective: str
    status: NodeStatus
    queued: int
    running: int
    failed_1h: int
    current: CurrentRun | None


@dataclass(frozen=True)
class FeedItem:
    at: datetime
    kind: str  # "run" | "workflow"
    module: str | None
    text: str
    status: str


@dataclass(frozen=True)
class Snapshot:
    generated_at: datetime
    global_state: str
    modules: list[ModuleView]
    feed: list[FeedItem] = field(default_factory=list)
    ai_cost_today_usd: Decimal = Decimal("0")
    ai_budget_today_usd: Decimal = Decimal("0")

    def module(self, key: str) -> ModuleView | None:
        return next((m for m in self.modules if m.key == key), None)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["generated_at"] = self.generated_at.isoformat()
        data["ai_cost_today_usd"] = str(self.ai_cost_today_usd)
        data["ai_budget_today_usd"] = str(self.ai_budget_today_usd)
        for module in data["modules"]:
            module["status"] = module["status"].value
            if module["current"]:
                module["current"]["run_id"] = str(module["current"]["run_id"])
        for item in data["feed"]:
            item["at"] = item["at"].isoformat()
        return data


def start_of_local_day(now: datetime, timezone: str) -> datetime:
    local = now.astimezone(ZoneInfo(timezone))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(now.tzinfo)


class ControlSnapshotService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build(
        self, *, timezone: str, ai_budget_today: Decimal, now: datetime | None = None
    ) -> Snapshot:
        now = now or utcnow()
        controls = AgentControlRepository(self.session)
        states = controls.states()
        global_state = states.get(GLOBAL_CONTROL, ControlState.STOPPED)

        job_counts: dict[tuple[str, JobStatus], int] = {
            (module, status): count
            for module, status, count in self.session.execute(
                select(Job.agent_module, Job.status, func.count())
                .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
                .group_by(Job.agent_module, Job.status)
            ).tuples()
        }
        failures = dict(
            self.session.execute(
                select(Job.agent_module, func.count())
                .where(Job.status == JobStatus.FAILED, Job.finished_at >= now - FAILURE_WINDOW)
                .group_by(Job.agent_module)
            )
            .tuples()
            .all()
        )
        running_runs: dict[str, AgentRun] = {}
        for run in self.session.scalars(
            select(AgentRun)
            .where(AgentRun.status == AgentRunStatus.RUNNING)
            .order_by(AgentRun.heartbeat_at.desc())
        ):
            running_runs.setdefault(run.module, run)

        modules = []
        for module in AgentModule:
            effective = controls.effective(module)
            active_run = running_runs.get(module.value)
            current = None
            if active_run is not None:
                run = active_run
                current = CurrentRun(
                    run_id=run.id,
                    step=run.current_step,
                    progress_pct=max(0, min(100, run.progress_pct)),
                    heartbeat_age_s=max(0, int((now - run.heartbeat_at).total_seconds())),
                )
            modules.append(
                ModuleView(
                    key=module.value,
                    state=states.get(module.value, ControlState.STOPPED).value,
                    effective=effective.value,
                    status=node_status(
                        effective=effective,
                        running_heartbeat=active_run.heartbeat_at if active_run else None,
                        recent_failures=failures.get(module.value, 0),
                        now=now,
                    ),
                    queued=job_counts.get((module.value, JobStatus.QUEUED), 0),
                    running=job_counts.get((module.value, JobStatus.RUNNING), 0),
                    failed_1h=failures.get(module.value, 0),
                    current=current,
                )
            )

        day_start = start_of_local_day(now, timezone)
        cost = self.session.scalar(
            select(func.coalesce(func.sum(AgentRun.cost_usd), 0)).where(
                AgentRun.started_at >= day_start
            )
        )
        return Snapshot(
            generated_at=now,
            global_state=global_state.value,
            modules=modules,
            feed=self._feed(),
            ai_cost_today_usd=Decimal(str(cost or 0)).quantize(Decimal("0.0001")),
            ai_budget_today_usd=ai_budget_today,
        )

    def _feed(self) -> list[FeedItem]:
        items = [
            FeedItem(
                at=run.heartbeat_at
                if run.status is AgentRunStatus.RUNNING
                else (run.finished_at or run.started_at),
                kind="run",
                module=run.module,
                text=run.current_step or "",
                status=run.status.value,
            )
            for run in self.session.scalars(
                select(AgentRun).order_by(AgentRun.started_at.desc()).limit(FEED_SIZE)
            )
        ]
        items += [
            FeedItem(
                at=event.created_at,
                kind="workflow",
                module=event.actor.removeprefix("agent:")
                if event.actor.startswith("agent:")
                else None,
                text=f"{event.entity_type}: {event.from_state or '—'} → {event.to_state}",
                status=event.actor,
            )
            for event in self.session.scalars(
                select(WorkflowEvent).order_by(WorkflowEvent.created_at.desc()).limit(FEED_SIZE)
            )
        ]
        items.sort(key=lambda item: item.at, reverse=True)
        return items[:FEED_SIZE]

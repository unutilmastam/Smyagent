"""Analytics (M11): funnel with defined denominators, outreach, agents, AI cost.

Definitions (shown on the page too):
- Every count is "distinct entities that **reached** a step inside the period", taken
  from the audit trail (`workflow_events`), not from current state — a lead that moved
  on is still counted for the steps it passed in the period.
- A conversion is step ÷ previous step of the **same period** (a period ratio, not a
  cohort): with short periods it can exceed 100 % when the earlier step happened before
  the period started.
- Replies are split: *outbound* (CONTACTED → RESPONDED, the reply rate of our outreach)
  and *inbound* (clients who wrote to the bot first and entered at RESPONDED).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.budget import BudgetService
from app.core.config import Settings
from app.domain.agents import PIPELINE, AgentModule
from app.domain.budget import BudgetStatus, UsageKind, day_start
from app.domain.jobs import JobStatus
from app.domain.outreach import Channel, OutreachStatus
from app.infrastructure.database.models import (
    Company,
    Job,
    OutreachEvent,
    Proposal,
    ProviderUsage,
    WorkflowEvent,
)
from app.infrastructure.database.types import utcnow

PERIODS = (1, 7, 30, 0)  # days; 0 = all time


@dataclass(frozen=True)
class FunnelStep:
    key: str
    count: int
    # Conversion from the previous step (None on the first step or when it is 0).
    rate_pct: int | None
    denominator_key: str | None


@dataclass(frozen=True)
class AgentRow:
    module: str
    succeeded: int
    failed: int

    @property
    def success_pct(self) -> int | None:
        done = self.succeeded + self.failed
        return round(100 * self.succeeded / done) if done else None


@dataclass(frozen=True)
class CostRow:
    label: str
    requests: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal


@dataclass
class Report:
    days: int
    since: datetime | None
    funnel: list[FunnelStep]
    inbound: int
    outreach: dict[str, Any]
    agents: list[AgentRow]
    budget: BudgetStatus
    cost_by_module: list[CostRow] = field(default_factory=list)
    cost_by_model: list[CostRow] = field(default_factory=list)
    searches: int = 0

    @property
    def max_funnel(self) -> int:
        return max([s.count for s in self.funnel] + [1])


def _pct(part: int, whole: int) -> int | None:
    return round(100 * part / whole) if whole else None


class AnalyticsService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def report(self, days: int, *, now: datetime | None = None) -> Report:
        now = now or utcnow()
        days = days if days in PERIODS else 7
        since = (
            day_start(now, self.settings.default_timezone) - timedelta(days=days - 1)
            if days
            else None
        )
        found = self._count(select(func.count()).select_from(Company), Company.created_at, since)
        researched = self._reached("company", "RESEARCHED", since)
        qualified = self._reached("lead", "QUALIFIED", since)
        proposals = int(
            self.session.scalar(
                self._period(
                    select(func.count(func.distinct(Proposal.lead_id))), Proposal.created_at, since
                )
            )
            or 0
        )
        approved = self._reached("lead", "APPROVED", since)
        contacted = self._reached("lead", "CONTACTED", since)
        replied = self._reached("lead", "RESPONDED", since, from_state="CONTACTED", match_from=True)
        inbound = self._reached("lead", "RESPONDED", since, from_state=None, match_from=True)
        orders = self._reached("lead", "ORDER_CONFIRMED", since)
        won = self._reached("lead", "WON", since)

        steps: list[tuple[str, int]] = [
            ("found", found),
            ("researched", researched),
            ("qualified", qualified),
            ("proposals", proposals),
            ("approved", approved),
            ("contacted", contacted),
            ("replied", replied),
            ("orders", orders),
            ("won", won),
        ]
        funnel: list[FunnelStep] = []
        for i, (key, count) in enumerate(steps):
            if i == 0:
                funnel.append(FunnelStep(key, count, None, None))
                continue
            prev_key, prev = steps[i - 1]
            if key == "orders":
                # Orders come from outbound replies and inbound chats alike.
                prev_key, prev = "replied_all", replied + inbound
            funnel.append(FunnelStep(key, count, _pct(count, prev), prev_key))

        budget = BudgetService(self.session, self.settings)
        return Report(
            days=days,
            since=since,
            funnel=funnel,
            inbound=inbound,
            outreach=self._outreach(since),
            agents=self._agents(since),
            budget=budget.status(now),
            cost_by_module=self._costs(ProviderUsage.module, since),
            cost_by_model=self._costs(ProviderUsage.model, since),
            searches=self._searches(since),
        )

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _period(stmt: Any, column: Any, since: datetime | None) -> Any:
        return stmt.where(column >= since) if since is not None else stmt

    def _count(self, stmt: Any, column: Any, since: datetime | None) -> int:
        return int(self.session.scalar(self._period(stmt, column, since)) or 0)

    def _reached(
        self,
        entity: str,
        state: str,
        since: datetime | None,
        *,
        from_state: str | None = None,
        match_from: bool = False,
    ) -> int:
        """Distinct entities that reached `state`; `match_from` also pins the previous state
        (`from_state=None` with `match_from` = entities created directly in `state`)."""
        stmt = select(func.count(func.distinct(WorkflowEvent.entity_id))).where(
            WorkflowEvent.entity_type == entity, WorkflowEvent.to_state == state
        )
        if match_from:
            stmt = stmt.where(
                WorkflowEvent.from_state.is_(None)
                if from_state is None
                else WorkflowEvent.from_state == from_state
            )
        return self._count(stmt, WorkflowEvent.created_at, since)

    def _outreach(self, since: datetime | None) -> dict[str, Any]:
        def events(*where: Any, column: Any = OutreachEvent.created_at) -> int:
            return self._count(
                select(func.count()).select_from(OutreachEvent).where(*where), column, since
            )

        sent = events(
            OutreachEvent.channel == Channel.EMAIL,
            OutreachEvent.sent_at.is_not(None),
            column=OutreachEvent.sent_at,
        )
        bounced = events(
            OutreachEvent.channel == Channel.EMAIL, OutreachEvent.status == OutreachStatus.BOUNCED
        )
        replies = events(OutreachEvent.replied_at.is_not(None), column=OutreachEvent.replied_at)
        telegram = events(
            OutreachEvent.channel == Channel.TELEGRAM, OutreachEvent.status == OutreachStatus.DONE
        )
        return {
            "emails_sent": sent,
            "bounced": bounced,
            "bounce_pct": _pct(bounced, sent),
            "replies": replies,
            "reply_pct": _pct(replies, sent + telegram),
            "telegram_sent": telegram,
        }

    def _agents(self, since: datetime | None) -> list[AgentRow]:
        stmt = self._period(
            select(Job.agent_module, Job.status, func.count())
            .where(Job.status.in_([JobStatus.SUCCEEDED, JobStatus.FAILED]))
            .group_by(Job.agent_module, Job.status),
            Job.finished_at,
            since,
        )
        counts: dict[tuple[str, JobStatus], int] = {
            (module, status): int(n) for module, status, n in self.session.execute(stmt).tuples()
        }
        modules = [AgentModule.ORCHESTRATOR, *PIPELINE]
        return [
            AgentRow(
                m.value,
                counts.get((m.value, JobStatus.SUCCEEDED), 0),
                counts.get((m.value, JobStatus.FAILED), 0),
            )
            for m in modules
        ]

    def _costs(self, column: Any, since: datetime | None) -> list[CostRow]:
        stmt = self._period(
            select(
                column,
                func.coalesce(func.sum(ProviderUsage.requests), 0),
                func.coalesce(func.sum(ProviderUsage.tokens_in), 0),
                func.coalesce(func.sum(ProviderUsage.tokens_out), 0),
                func.coalesce(func.sum(ProviderUsage.cost_usd), 0),
            )
            .where(ProviderUsage.kind == UsageKind.AI)
            .group_by(column),
            ProviderUsage.created_at,
            since,
        )
        rows = [
            CostRow(str(label or "—"), int(r), int(ti), int(to), Decimal(str(c or 0)))
            for label, r, ti, to, c in self.session.execute(stmt).tuples()
        ]
        return sorted(rows, key=lambda row: row.cost_usd, reverse=True)

    def _searches(self, since: datetime | None) -> int:
        stmt = select(func.coalesce(func.sum(ProviderUsage.requests), 0)).where(
            ProviderUsage.kind == UsageKind.SEARCH
        )
        return self._count(stmt, ProviderUsage.created_at, since)

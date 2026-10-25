"""AI budget enforcement and usage accounting (CLAUDE.md §12, §12.1; M11).

Before every optional AI call: `ensure_may_spend()` (raises BudgetExhaustedError →
the runner defers the job as BUDGET_DEFERRED). After it: `record()` (one
`provider_usage` row; the job's agent run also gets tokens and cost, so the Control
Center and Virtual Office show it). Crossing 80 % of a budget alerts the owner once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.automation import Alert, AlertService
from app.core.config import Settings
from app.domain.budget import (
    BudgetExhaustedError,
    BudgetStatus,
    BudgetWindow,
    UsageKind,
    day_start,
    limits,
    month_start,
    next_window,
    status,
)
from app.infrastructure.database.models import AgentRun, ProviderUsage
from app.infrastructure.database.types import utcnow

ZERO = Decimal("0")


@dataclass(frozen=True)
class UsageRecord:
    provider: str
    module: str
    kind: UsageKind = UsageKind.AI
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = ZERO
    requests: int = 1
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None


def daily_limit(settings: Settings, now: datetime | None = None) -> Decimal:
    """Effective AI budget for today (explicit daily cap or monthly / days in month)."""
    return limits(
        monthly_usd=settings.monthly_ai_budget_usd,
        daily_usd=settings.daily_ai_budget_usd,
        now=now or utcnow(),
        tz=settings.default_timezone,
    ).daily_usd


class BudgetService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.tz = settings.default_timezone
        self.monthly = settings.monthly_ai_budget_usd
        self.daily = settings.daily_ai_budget_usd

    def spent_since(self, since: datetime, kind: UsageKind = UsageKind.AI) -> Decimal:
        total = self.session.scalar(
            select(func.coalesce(func.sum(ProviderUsage.cost_usd), 0)).where(
                ProviderUsage.kind == kind, ProviderUsage.created_at >= since
            )
        )
        return Decimal(str(total or 0)).quantize(Decimal("0.000001"))

    def status(self, now: datetime | None = None) -> BudgetStatus:
        now = now or utcnow()
        lim = limits(monthly_usd=self.monthly, daily_usd=self.daily, now=now, tz=self.tz)
        return status(
            self.spent_since(day_start(now, self.tz)),
            self.spent_since(month_start(now, self.tz)),
            lim,
        )

    def ensure_may_spend(self, now: datetime | None = None) -> BudgetStatus:
        now = now or utcnow()
        current = self.status(now)
        if current.exhausted is not None:
            raise BudgetExhaustedError(
                current.exhausted, next_window(current.exhausted, now, self.tz)
            )
        return current

    def searches_today(self, provider: str | None = None, now: datetime | None = None) -> int:
        now = now or utcnow()
        stmt = select(func.coalesce(func.sum(ProviderUsage.requests), 0)).where(
            ProviderUsage.kind == UsageKind.SEARCH,
            ProviderUsage.created_at >= day_start(now, self.tz),
        )
        if provider:
            stmt = stmt.where(ProviderUsage.provider == provider)
        return int(self.session.scalar(stmt) or 0)

    def record(self, usage: UsageRecord, *, now: datetime | None = None) -> Alert | None:
        """Store the usage; returns an 80 %/100 % owner alert to send after commit."""
        now = now or utcnow()
        before = self.status(now) if usage.kind is UsageKind.AI else None
        self.session.add(
            ProviderUsage(
                created_at=now,
                kind=usage.kind,
                provider=usage.provider[:32],
                model=(usage.model or None) and usage.model[:64],
                module=usage.module[:32],
                job_id=usage.job_id,
                requests=max(0, usage.requests),
                tokens_in=max(0, usage.tokens_in),
                tokens_out=max(0, usage.tokens_out),
                cost_usd=max(ZERO, usage.cost_usd),
            )
        )
        if usage.run_id is not None:
            run = self.session.get(AgentRun, usage.run_id)
            if run is not None:
                run.tokens_in += max(0, usage.tokens_in)
                run.tokens_out += max(0, usage.tokens_out)
                run.cost_usd = (run.cost_usd or ZERO) + max(ZERO, usage.cost_usd)
        self.session.flush()
        if before is None:
            return None
        return self._threshold_alert(before, self.status(now), now)

    def _threshold_alert(
        self, before: BudgetStatus, after: BudgetStatus, now: datetime
    ) -> Alert | None:
        local = now.astimezone(ZoneInfo(self.tz))
        if after.exhausted is not None and before.exhausted is None:
            window = after.exhausted
            stamp = f"{local:%Y%m%d}" if window is BudgetWindow.DAY else f"{local:%Y%m}"
            return AlertService(self.session).raise_alert(
                f"budget_used:{window.value}:{stamp}",
                _text("🛑", window, after) + "\nAI ishlari keyingi davrga qoldirildi.",
                now=now,
            )
        warn = after.warn_window()
        if warn is not None and before.warn_window() is None:
            stamp = f"{local:%Y%m%d}" if warn is BudgetWindow.DAY else f"{local:%Y%m}"
            return AlertService(self.session).raise_alert(
                f"budget_80:{warn.value}:{stamp}", _text("⚠️", warn, after), now=now
            )
        return None


def _text(icon: str, window: BudgetWindow, st: BudgetStatus) -> str:
    if window is BudgetWindow.MONTH:
        return f"{icon} AI byudjeti (oy): ${st.spent_month_usd:.2f} / ${st.limits.monthly_usd:.2f}"
    return f"{icon} AI byudjeti (kun): ${st.spent_today_usd:.2f} / ${st.limits.daily_usd:.2f}"

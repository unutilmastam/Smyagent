"""AI and search budgets (CLAUDE.md §12, §12.1, ADR-0007). Pure rules, no I/O.

Spending is counted in the owner's time zone: a "day" and a "month" start at local
midnight. When a limit is reached, optional AI work is deferred (job status
BUDGET_DEFERRED) until the next day or month — never silently run over budget.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from app.domain.errors import DomainError

WARN_AT = Decimal("0.8")  # owner bot alert at 80 % of a budget
ZERO = Decimal("0")


class UsageKind(str, Enum):
    AI = "ai"
    SEARCH = "search"


class BudgetWindow(str, Enum):
    DAY = "day"
    MONTH = "month"


@dataclass(frozen=True)
class BudgetLimits:
    daily_usd: Decimal
    monthly_usd: Decimal


@dataclass(frozen=True)
class BudgetStatus:
    limits: BudgetLimits
    spent_today_usd: Decimal
    spent_month_usd: Decimal
    exhausted: BudgetWindow | None  # the window that blocks AI calls, if any

    @property
    def allowed(self) -> bool:
        return self.exhausted is None

    @property
    def month_ratio(self) -> Decimal:
        return _ratio(self.spent_month_usd, self.limits.monthly_usd)

    @property
    def day_ratio(self) -> Decimal:
        return _ratio(self.spent_today_usd, self.limits.daily_usd)

    def warn_window(self) -> BudgetWindow | None:
        """A window at ≥ 80 % (but not exhausted) — the owner is told once."""
        if self.limits.monthly_usd > 0 and self.month_ratio >= WARN_AT:
            return BudgetWindow.MONTH
        if self.limits.daily_usd > 0 and self.day_ratio >= WARN_AT:
            return BudgetWindow.DAY
        return None


class BudgetExhaustedError(DomainError):
    """Optional AI work must wait: the job is deferred to `run_after`, not failed."""

    def __init__(self, window: BudgetWindow, run_after: datetime) -> None:
        super().__init__(f"AI budget for this {window.value} is used up")
        self.window = window
        self.run_after = run_after


def _ratio(spent: Decimal, limit: Decimal) -> Decimal:
    if limit <= 0:
        return Decimal("1") if spent > 0 else ZERO
    return spent / limit


def limits(*, monthly_usd: Decimal, daily_usd: Decimal, now: datetime, tz: str) -> BudgetLimits:
    """`daily_usd` 0 = automatic: the monthly budget spread evenly over the month's days."""
    if daily_usd > 0:
        daily = daily_usd
    else:
        local = now.astimezone(ZoneInfo(tz))
        days = calendar.monthrange(local.year, local.month)[1]
        daily = (monthly_usd / days).quantize(Decimal("0.0001"))
    return BudgetLimits(daily_usd=daily, monthly_usd=monthly_usd)


def status(spent_today: Decimal, spent_month: Decimal, lim: BudgetLimits) -> BudgetStatus:
    exhausted: BudgetWindow | None = None
    if spent_month >= lim.monthly_usd:
        exhausted = BudgetWindow.MONTH
    elif spent_today >= lim.daily_usd:
        exhausted = BudgetWindow.DAY
    return BudgetStatus(lim, spent_today, spent_month, exhausted)


def day_start(now: datetime, tz: str) -> datetime:
    local = now.astimezone(ZoneInfo(tz))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(now.tzinfo)


def month_start(now: datetime, tz: str) -> datetime:
    local = now.astimezone(ZoneInfo(tz))
    first = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first.astimezone(now.tzinfo)


def next_window(window: BudgetWindow, now: datetime, tz: str) -> datetime:
    """When a deferred job may try again: next local midnight / first day of next month."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    if window is BudgetWindow.DAY:
        nxt = (local + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    else:
        year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
        nxt = local.replace(
            year=year, month=month, day=1, hour=0, minute=5, second=0, microsecond=0
        )
    return nxt.astimezone(now.tzinfo)

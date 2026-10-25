"""AI budget rules (CLAUDE.md §12, ADR-0007)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.domain.budget import BudgetLimits, BudgetWindow, limits, next_window, status

TZ = "Asia/Tashkent"
D = Decimal


def test_daily_limit_is_monthly_spread_unless_set() -> None:
    oct25 = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
    assert limits(monthly_usd=D("10"), daily_usd=D("0"), now=oct25, tz=TZ).daily_usd == D("0.3226")
    assert limits(monthly_usd=D("10"), daily_usd=D("1"), now=oct25, tz=TZ).daily_usd == D("1")
    feb = datetime(2027, 2, 10, tzinfo=timezone.utc)
    assert limits(monthly_usd=D("28"), daily_usd=D("0"), now=feb, tz=TZ).daily_usd == D("1")


def test_status_blocks_month_before_day() -> None:
    lim = BudgetLimits(daily_usd=D("1"), monthly_usd=D("10"))
    assert status(D("0.5"), D("5"), lim).allowed
    assert status(D("1"), D("5"), lim).exhausted is BudgetWindow.DAY
    assert status(D("0"), D("10"), lim).exhausted is BudgetWindow.MONTH
    assert status(D("0"), D("0"), BudgetLimits(D("0"), D("0"))).exhausted is BudgetWindow.MONTH


def test_warning_at_80_percent() -> None:
    lim = BudgetLimits(daily_usd=D("1"), monthly_usd=D("10"))
    assert status(D("0.5"), D("7.9"), lim).warn_window() is None
    assert status(D("0.5"), D("8"), lim).warn_window() is BudgetWindow.MONTH
    assert status(D("0.8"), D("1"), lim).warn_window() is BudgetWindow.DAY


def test_next_window_in_local_time() -> None:
    # 21:00 UTC on Oct 25 is 02:00 on Oct 26 in Tashkent (UTC+5).
    now = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)
    assert next_window(BudgetWindow.DAY, now, TZ) == datetime(
        2026, 10, 26, 19, 5, tzinfo=timezone.utc
    )
    dec = datetime(2026, 12, 20, 12, tzinfo=timezone.utc)
    assert next_window(BudgetWindow.MONTH, dec, TZ) == datetime(
        2026, 12, 31, 19, 5, tzinfo=timezone.utc
    )

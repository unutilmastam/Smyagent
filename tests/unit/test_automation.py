"""M10 rules: cron liveness, error grouping, alert dedup window, per-job time limit."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.automation import (
    ALERT_WINDOW,
    LATE_AFTER,
    CronHealth,
    alert_due,
    cron_health,
    error_category,
    failure_alert_key,
)
from app.jobs.context import JobTimeoutError, RetryableTaskError, time_limit

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def test_cron_never_ok_late() -> None:
    assert cron_health(None, NOW).health is CronHealth.NEVER
    ok = cron_health(NOW - timedelta(minutes=4), NOW)
    assert ok.health is CronHealth.OK and ok.minutes_ago == 4
    assert cron_health(NOW - LATE_AFTER, NOW).health is CronHealth.OK  # boundary
    late = cron_health(NOW - LATE_AFTER - timedelta(seconds=1), NOW)
    assert late.health is CronHealth.LATE and late.minutes_ago == 15
    assert cron_health(NOW + timedelta(minutes=1), NOW).minutes_ago == 0  # clock skew


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, "unknown"),
        ("", "unknown"),
        ("OpenStreetMap: HTTP 429", "OpenStreetMap"),
        ("TimeoutError", "TimeoutError"),
        ("timeout: job ran longer than 120 s", "timeout"),
        ("no lead 7f0c2a51-1b2c-4d3e-8f9a-0123456789ab", "no lead <id>"),
    ],
)
def test_error_category(error: str | None, expected: str) -> None:
    assert error_category(error) == expected


def test_same_failure_gets_same_key() -> None:
    a = failure_alert_key("research.audit", "dns: lookup failed for a.uz after 3 tries")
    b = failure_alert_key("research.audit", "dns: lookup failed for b.uz after 5 tries")
    assert a == b == "job_failed:research.audit:dns"
    assert failure_alert_key("outbound.email", "dns: x") != a


def test_alert_window() -> None:
    assert alert_due(None, NOW)
    assert not alert_due(NOW - ALERT_WINDOW + timedelta(seconds=1), NOW)
    assert alert_due(NOW - ALERT_WINDOW, NOW)


def test_time_limit_interrupts_a_hanging_job() -> None:
    started = time.monotonic()
    with pytest.raises(JobTimeoutError) as exc, time_limit(0.2):
        time.sleep(5)
    assert time.monotonic() - started < 2
    assert isinstance(exc.value, RetryableTaskError)  # retried with backoff


def test_time_limit_is_cleared_after_the_block() -> None:
    with time_limit(0.2):
        pass
    time.sleep(0.4)  # no stray alarm fires later


def test_time_limit_zero_disables() -> None:
    with time_limit(0):
        time.sleep(0.01)

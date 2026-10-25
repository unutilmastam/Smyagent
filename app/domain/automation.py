"""Background automation rules (M10): cron liveness, failure alerts, retention.

Pure functions: the runner, dashboard and owner bot share them, so "is cron alive?"
and "should the owner be told again?" have one answer everywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# cPanel cron runs the runner every 5 minutes (docs/deployment-cpanel.md §7).
CRON_INTERVAL = timedelta(minutes=5)
# Missing 3 runs in a row means cron is not configured, broken or the host is down.
LATE_AFTER = 3 * CRON_INTERVAL
# The same failure is reported at most once per window; repeats are counted.
ALERT_WINDOW = timedelta(hours=6)
# Finished jobs, agent runs and runner records older than this are deleted daily.
RETENTION = timedelta(days=30)
RUNNER_RUN_RETENTION = timedelta(days=14)

CLEANUP_EVERY = timedelta(hours=24)


class RunnerStatus(str, Enum):
    RUNNING = "RUNNING"
    OK = "OK"
    LOCKED = "LOCKED"  # another runner held the lock: this invocation did nothing
    STOPPED = "STOPPED"  # global STOP: exited early
    ERROR = "ERROR"  # the runner itself crashed (not a single job)


class CronHealth(str, Enum):
    OK = "ok"
    LATE = "late"
    NEVER = "never"


@dataclass(frozen=True)
class CronView:
    health: CronHealth
    last_run_at: datetime | None
    minutes_ago: int | None


def cron_health(last_run_at: datetime | None, now: datetime) -> CronView:
    """`last_run_at` = start of the latest runner invocation (any status)."""
    if last_run_at is None:
        return CronView(CronHealth.NEVER, None, None)
    age = max(timedelta(0), now - last_run_at)
    minutes = int(age.total_seconds() // 60)
    health = CronHealth.LATE if age > LATE_AFTER else CronHealth.OK
    return CronView(health, last_run_at, minutes)


_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_NUMBER = re.compile(r"\d+")
_SPACE = re.compile(r"\s+")


def error_category(error: str | None) -> str:
    """Stable, short label of an error: ids and numbers removed so repeats group together."""
    if not error:
        return "unknown"
    text = _UUID.sub("<id>", error)
    text = _NUMBER.sub("N", text)
    text = _SPACE.sub(" ", text).strip()
    head = text.split(":", 1)[0].strip() if ":" in text[:40] else text
    return (head or "unknown")[:60]


def failure_alert_key(job_type: str, error: str | None) -> str:
    return f"job_failed:{job_type}:{error_category(error)}"[:191]


def alert_due(
    last_sent_at: datetime | None, now: datetime, window: timedelta = ALERT_WINDOW
) -> bool:
    return last_sent_at is None or now - last_sent_at >= window

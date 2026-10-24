"""Job queue rules (ADR-0004)."""

from __future__ import annotations

import random
from datetime import timedelta
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BUDGET_DEFERRED = "BUDGET_DEFERRED"


FINISHED_STATUSES = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED})

BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 6 * 3600


def retry_delay(attempt: int, *, rng: random.Random | None = None) -> timedelta:
    """Exponential backoff with full jitter; `attempt` starts at 1."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    cap = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * 2 ** (attempt - 1))
    jitter = (rng or random).uniform(0.5, 1.0)
    return timedelta(seconds=cap * jitter)

"""Runner invocations and deduplicated owner alerts (M10)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.automation import RunnerStatus
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import UTCDateTime, utcnow


class RunnerRun(UUIDPrimaryKey, Base):
    """One cron invocation of `app.jobs.runner`: proves cron is alive, explains what it did."""

    __tablename__ = "runner_runs"

    worker_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[RunnerStatus] = mapped_column(
        enum_column(RunnerStatus), default=RunnerStatus.RUNNING
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    scheduled: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    retried: Mapped[int] = mapped_column(Integer, default=0)
    halted: Mapped[int] = mapped_column(Integer, default=0)
    requeued_stale: Mapped[int] = mapped_column(Integer, default=0)
    # Retention cleanup ran in this invocation (once per CLEANUP_EVERY).
    cleaned_up: Mapped[bool] = mapped_column(Boolean, default=False)
    # Error class only (never a message that could carry a secret or personal data).
    error: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (Index("ix_runner_runs_started", "started_at"),)


class OwnerAlert(UUIDPrimaryKey, Timestamps, Base):
    """Dedup state of an owner alert key: sent at most once per window, repeats counted."""

    __tablename__ = "owner_alerts"

    alert_key: Mapped[str] = mapped_column(String(191), unique=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    total: Mapped[int] = mapped_column(Integer, default=0)
    # Occurrences since the last notification (shown as "+N more" next time).
    pending: Mapped[int] = mapped_column(Integer, default=0)

"""DB-backed job queue and overlap locks (ADR-0004)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.jobs import JobStatus
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import UTCDateTime, utcnow


class Job(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(64))
    agent_module: Mapped[str] = mapped_column(String(32))
    status: Mapped[JobStatus] = mapped_column(enum_column(JobStatus), default=JobStatus.QUEUED)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Same key => same job; retries and duplicate enqueues never create a second job.
    idempotency_key: Mapped[str | None] = mapped_column(String(191), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    claimed_by: Mapped[str | None] = mapped_column(String(64))
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("ix_jobs_status_run_after", "status", "run_after"),
        Index("ix_jobs_module_status", "agent_module", "status"),
    )


class JobLock(Base):
    """Named lock with expiry; prevents overlapping cron runner invocations."""

    __tablename__ = "job_locks"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    holder: Mapped[str] = mapped_column(String(64))
    acquired_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())

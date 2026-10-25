"""Agent Control Center: kill switch enforcement and state changes (CLAUDE.md §13A.2).

Enforcement points (all go through `ControlGate`):
1. job runner, before claiming a job          -> `eligible_modules()`
2. each agent, between steps                  -> `checkpoint()`
3. every outbound send, right before the call -> `ensure_may_send()`
4. every AI call                              -> `ensure_may_call_ai()`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.agents import (
    GLOBAL_CONTROL,
    OUTBOUND_JOB_PREFIX,
    AgentHaltedError,
    AgentModule,
    ControlState,
    SendingBlockedError,
    may_take_new_work,
)
from app.domain.errors import DomainError
from app.domain.jobs import JobStatus
from app.infrastructure.database.models import AgentRun, AgentRunStatus, Job
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.controls import ALL_CONTROL_KEYS, AgentControlRepository
from app.infrastructure.repositories.jobs import JobRepository
from app.infrastructure.repositories.workflow import AuditLogRepository

logger = logging.getLogger("app.controls")


class ControlGate:
    """Read-side checks. Each call re-reads the DB so a STOP is seen at the next check."""

    def __init__(self, session: Session, *, outbound_sending_enabled: bool) -> None:
        self.repo = AgentControlRepository(session)
        self.outbound_sending_enabled = outbound_sending_enabled

    def state(self, module: AgentModule) -> ControlState:
        return self.repo.effective(module)

    def eligible_modules(self) -> list[str]:
        """Modules allowed to claim new jobs right now (effective state ACTIVE)."""
        return [m.value for m in AgentModule if may_take_new_work(self.repo.effective(m))]

    def checkpoint(self, module: AgentModule) -> None:
        state = self.repo.effective(module)
        if state is not ControlState.ACTIVE:
            raise AgentHaltedError(module, state)

    def ensure_may_send(self, module: AgentModule) -> None:
        if not self.outbound_sending_enabled:
            raise SendingBlockedError("outbound sending is disabled (OUTBOUND_SENDING_ENABLED)")
        state = self.repo.effective(module)
        if state is not ControlState.ACTIVE:
            raise SendingBlockedError(f"{module.value} is {state.value}; send blocked")

    def ensure_may_call_ai(self, module: AgentModule) -> None:
        # Budget checks join here in M11 (CLAUDE.md §12 BUDGET_DEFERRED).
        self.checkpoint(module)


class OwnerNotifier(Protocol):
    def notify(self, text: str) -> None: ...


class NullNotifier:
    def notify(self, text: str) -> None:
        logger.info("owner_notification_skipped", extra={"reason": "bot not configured"})


@dataclass(frozen=True)
class ControlChange:
    key: str
    previous: ControlState
    state: ControlState
    cancelled_running: int
    cancelled_outbound: int


STATE_LABELS_UZ = {
    ControlState.ACTIVE: "🟢 faol",
    ControlState.PAUSED: "🟡 pauza",
    ControlState.STOPPED: "🔴 to'xtatildi",
}


class AgentControlService:
    """State changes. Callers must already have verified the actor is the owner."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = AgentControlRepository(session)
        self.jobs = JobRepository(session)
        self.audit = AuditLogRepository(session)

    def set_state(
        self, key: str, state: ControlState, actor: Actor, reason: str | None = None
    ) -> ControlChange:
        if key not in ALL_CONTROL_KEYS:
            raise DomainError(f"unknown agent: {key}")
        previous = self.repo.states().get(key, ControlState.STOPPED)
        self.repo.set_state(key, state, actor, reason)

        cancelled_running = cancelled_outbound = 0
        if state is ControlState.STOPPED:
            modules = [m.value for m in AgentModule] if key == GLOBAL_CONTROL else [key]
            # STOP: running work is cancelled; agents also abort at their next checkpoint.
            cancelled_running = self.jobs.cancel_running(modules)
            self._cancel_runs(modules)
            if key == GLOBAL_CONTROL:
                cancelled_outbound = self._cancel_queued_outbound()
        self.audit.add(
            actor=actor,
            action="agent_control.set",
            details={
                "key": key,
                "from": previous.value,
                "to": state.value,
                "reason": (reason or "")[:200],
                "cancelled_running": cancelled_running,
                "cancelled_outbound": cancelled_outbound,
            },
        )
        return ControlChange(key, previous, state, cancelled_running, cancelled_outbound)

    def _cancel_queued_outbound(self) -> int:
        result = self.session.execute(
            update(Job)
            .where(Job.status == JobStatus.QUEUED, Job.job_type.like(OUTBOUND_JOB_PREFIX + "%"))
            .values(status=JobStatus.CANCELLED, finished_at=utcnow(), last_error="global stop")
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def _cancel_runs(self, modules: list[str]) -> None:
        self.session.execute(
            update(AgentRun)
            .where(AgentRun.status == AgentRunStatus.RUNNING, AgentRun.module.in_(modules))
            .values(status=AgentRunStatus.CANCELLED, finished_at=utcnow())
            .execution_options(synchronize_session=False)
        )


def describe_change(change: ControlChange) -> str:
    """Owner-facing (Uzbek) summary, used by the bot and dashboard notifications."""
    name = "Barcha agentlar" if change.key == GLOBAL_CONTROL else change.key
    text = f"{name}: {STATE_LABELS_UZ[change.state]}"
    if change.cancelled_running:
        text += f"\nBekor qilingan ishlayotgan ishlar: {change.cancelled_running}"
    if change.cancelled_outbound:
        text += f"\nBekor qilingan yuborilishi kutilgan xabarlar: {change.cancelled_outbound}"
    return text

"""Virtual Office scene state (CLAUDE.md §13A.3, ADR-0009). Pure functions, no I/O.

Every character pose and animation is derived from real database facts collected by
`app.application.office`. Nothing is simulated: no fact → no animation. In particular a
character is shown working only while a run is RUNNING with a fresh heartbeat.

| real state                                        | mode       | scene                         |
|---------------------------------------------------|------------|-------------------------------|
| agent or global STOP                              | STOP       | leaves the desk, light off    |
| run RUNNING, heartbeat fresh                      | WORK       | typing, monitor shows step    |
| PAUSED, nothing running                           | PAUSE      | lounge, "Pauza" sign          |
| run RUNNING, heartbeat stale                      | ERROR      | at desk, "!" (stalled)        |
| job failed recently                               | ERROR      | at desk, "!" + error class    |
| only not-yet-due jobs (backoff, limit, budget)    | WAIT       | restroom, reason + retry time |
| due jobs queued, none running (next cron)         | QUEUED     | at desk, monitor off, count   |
| nothing queued                                    | IDLE       | kitchen, coffee               |
| outbound email sent                               | event      | envelope to the mail desk     |
| ORDER_CONFIRMED                                   | event      | folder to the director        |
| work handed to the next module                    | event      | paper flies desk to desk      |
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from app.domain.agents import AgentModule, ControlState
from app.domain.control_view import HEARTBEAT_STALE_AFTER

# A failed job keeps the "!" bubble this long (unless the agent is busy again).
ERROR_SHOWN_FOR = timedelta(minutes=10)
# Events newer than this are sent to the page; the page animates each id once.
EVENT_WINDOW = timedelta(minutes=3)


class Mode(str, Enum):
    WORK = "work"
    IDLE = "idle"
    QUEUED = "queued"
    WAIT = "wait"
    PAUSE = "pause"
    STOP = "stop"
    ERROR = "error"


class WaitKind(str, Enum):
    RATE_LIMIT = "rate_limit"  # provider said "too many requests"
    BACKOFF = "backoff"  # retry after a temporary error
    BUDGET = "budget"  # BUDGET_DEFERRED (AI budget used up)
    DEFERRED = "deferred"  # daily cap / spacing (not an error)


class EventKind(str, Enum):
    EMAIL_SENT = "email_sent"
    ORDER_CONFIRMED = "order_confirmed"
    HANDOFF = "handoff"


@dataclass(frozen=True)
class RunFact:
    step: str | None
    progress_pct: int
    heartbeat_at: datetime


@dataclass(frozen=True)
class WaitFact:
    kind: WaitKind
    reason: str
    retry_at: datetime


@dataclass(frozen=True)
class FailureFact:
    at: datetime
    category: str
    job_id: str


@dataclass(frozen=True)
class AgentFacts:
    module: AgentModule
    effective: ControlState  # already includes the global state
    global_stopped: bool
    run: RunFact | None = None
    due_jobs: int = 0
    waiting: WaitFact | None = None  # the earliest not-yet-due job, if any
    last_failure: FailureFact | None = None


@dataclass(frozen=True)
class CharacterState:
    module: str
    mode: Mode
    # Short real text for the monitor / bubble: step, error class, wait reason, queue size.
    detail: str
    progress_pct: int | None = None
    retry_at: datetime | None = None
    job_id: str | None = None  # tap → job drill-down (errors)
    stalled: bool = False


def character_state(facts: AgentFacts, now: datetime) -> CharacterState:
    key = facts.module.value
    if facts.global_stopped or facts.effective is ControlState.STOPPED:
        return CharacterState(key, Mode.STOP, "")
    run = facts.run
    if run is not None and now - run.heartbeat_at <= HEARTBEAT_STALE_AFTER:
        # PAUSED still finishes the current step, so a fresh run is still work.
        pct = max(0, min(100, run.progress_pct))
        return CharacterState(key, Mode.WORK, run.step or "", progress_pct=pct)
    if facts.effective is ControlState.PAUSED:
        return CharacterState(key, Mode.PAUSE, "")
    if run is not None:  # RUNNING but silent: never shown as working
        return CharacterState(key, Mode.ERROR, run.step or "", stalled=True)
    failure = facts.last_failure
    if failure is not None and now - failure.at <= ERROR_SHOWN_FOR:
        return CharacterState(key, Mode.ERROR, failure.category, job_id=failure.job_id)
    if facts.due_jobs > 0:
        return CharacterState(key, Mode.QUEUED, str(facts.due_jobs))
    if facts.waiting is not None:
        wait = facts.waiting
        return CharacterState(key, Mode.WAIT, wait.reason, retry_at=wait.retry_at)
    return CharacterState(key, Mode.IDLE, "")


def wait_kind(*, budget_deferred: bool, last_error: str | None, deferred: bool) -> WaitKind:
    """Why a job is not due yet. `deferred`: requeued by DeferTaskError (caps, spacing)."""
    if budget_deferred:
        return WaitKind.BUDGET
    if deferred and not last_error:
        return WaitKind.DEFERRED
    text = (last_error or "").lower()
    if "429" in text or "rate" in text or "limit" in text or "too many" in text:
        return WaitKind.RATE_LIMIT
    return WaitKind.BACKOFF


# Workflow transitions that mean "this module passed the work to the next one".
_HANDOFFS: dict[tuple[str, str], tuple[AgentModule, AgentModule]] = {
    ("company", "NEW"): (AgentModule.DISCOVERY, AgentModule.RESEARCH_AUDIT),
    ("company", "RESEARCHED"): (AgentModule.RESEARCH_AUDIT, AgentModule.OPPORTUNITY_SCORING),
    ("lead", "QUALIFIED"): (AgentModule.OPPORTUNITY_SCORING, AgentModule.PROPOSAL_REQUIREMENTS),
    ("lead", "PROPOSAL_DRAFTED"): (AgentModule.PROPOSAL_REQUIREMENTS, AgentModule.QUALITY_GATE),
    ("lead", "APPROVED"): (AgentModule.QUALITY_GATE, AgentModule.CONVERSATION),
}


def handoff(entity_type: str, to_state: str) -> tuple[AgentModule, AgentModule] | None:
    return _HANDOFFS.get((entity_type, to_state))


def is_night(local_hour: int) -> bool:
    """Night lighting 20:00-06:00 in DEFAULT_TIMEZONE."""
    return local_hour >= 20 or local_hour < 6

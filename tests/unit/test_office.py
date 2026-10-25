"""Virtual Office scene mapping (CLAUDE.md §13A.3): one test per row of the state table."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.agents import AgentModule, ControlState
from app.domain.office import (
    ERROR_SHOWN_FOR,
    AgentFacts,
    FailureFact,
    Mode,
    RunFact,
    WaitFact,
    WaitKind,
    character_state,
    handoff,
    is_night,
    wait_kind,
)

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
FRESH = RunFact(step="lazzat.uz saytini tekshiryapman (3/5)", progress_pct=60, heartbeat_at=NOW)
STALE = RunFact(step="x", progress_pct=10, heartbeat_at=NOW - timedelta(minutes=5))
WAIT = WaitFact(WaitKind.RATE_LIMIT, "OpenStreetMap: HTTP 429", NOW + timedelta(minutes=3))
FAIL = FailureFact(NOW - timedelta(minutes=1), "TimeoutError", "job-1")


def _facts(**kw: object) -> AgentFacts:
    base: dict[str, object] = {
        "module": AgentModule.RESEARCH_AUDIT,
        "effective": ControlState.ACTIVE,
        "global_stopped": False,
    }
    base.update(kw)
    return AgentFacts(**base)  # type: ignore[arg-type]


def test_fresh_running_job_is_work_with_step_and_progress() -> None:
    s = character_state(_facts(run=FRESH), NOW)
    assert s.mode is Mode.WORK and s.progress_pct == 60 and "lazzat.uz" in s.detail


def test_stale_heartbeat_is_never_work() -> None:
    s = character_state(_facts(run=STALE), NOW)
    assert s.mode is Mode.ERROR and s.stalled


def test_empty_queue_is_idle_coffee() -> None:
    assert character_state(_facts(), NOW).mode is Mode.IDLE


def test_waiting_goes_to_restroom_with_reason_and_retry_time() -> None:
    s = character_state(_facts(waiting=WAIT), NOW)
    assert s.mode is Mode.WAIT and s.detail == "OpenStreetMap: HTTP 429"
    assert s.retry_at == WAIT.retry_at


def test_due_jobs_without_a_run_wait_for_the_next_cron_at_the_desk() -> None:
    s = character_state(_facts(due_jobs=4, waiting=WAIT), NOW)
    assert s.mode is Mode.QUEUED and s.detail == "4"


def test_paused_sits_in_lounge_but_finishes_current_step() -> None:
    assert character_state(_facts(effective=ControlState.PAUSED), NOW).mode is Mode.PAUSE
    busy = character_state(_facts(effective=ControlState.PAUSED, run=FRESH), NOW)
    assert busy.mode is Mode.WORK


@pytest.mark.parametrize(
    ("effective", "global_stopped"),
    [(ControlState.STOPPED, False), (ControlState.ACTIVE, True), (ControlState.PAUSED, True)],
)
def test_stopped_leaves_desk_even_with_a_run(effective: ControlState, global_stopped: bool) -> None:
    s = character_state(_facts(effective=effective, global_stopped=global_stopped, run=FRESH), NOW)
    assert s.mode is Mode.STOP


def test_recent_failure_shows_error_and_links_the_job() -> None:
    s = character_state(_facts(last_failure=FAIL), NOW)
    assert s.mode is Mode.ERROR and s.detail == "TimeoutError" and s.job_id == "job-1"
    old = FailureFact(NOW - ERROR_SHOWN_FOR - timedelta(seconds=1), "x", "j")
    assert character_state(_facts(last_failure=old), NOW).mode is Mode.IDLE
    # Busy again: work wins over an old "!".
    assert character_state(_facts(last_failure=FAIL, run=FRESH), NOW).mode is Mode.WORK


def test_no_state_maps_to_work_without_a_fresh_run() -> None:
    for effective in ControlState:
        for stopped in (False, True):
            for kw in (
                {},
                {"waiting": WAIT},
                {"due_jobs": 3},
                {"last_failure": FAIL},
                {"run": STALE},
            ):
                facts = _facts(effective=effective, global_stopped=stopped, **kw)
                assert character_state(facts, NOW).mode is not Mode.WORK


@pytest.mark.parametrize(
    ("budget", "error", "deferred", "kind"),
    [
        (True, None, False, WaitKind.BUDGET),
        (False, None, True, WaitKind.DEFERRED),
        (False, "OpenStreetMap: HTTP 429", False, WaitKind.RATE_LIMIT),
        (False, "timeout: job ran longer than 120 s", False, WaitKind.BACKOFF),
    ],
)
def test_wait_kind(budget: bool, error: str | None, deferred: bool, kind: WaitKind) -> None:
    assert wait_kind(budget_deferred=budget, last_error=error, deferred=deferred) is kind


def test_handoffs_follow_the_pipeline() -> None:
    assert handoff("company", "RESEARCHED") == (
        AgentModule.RESEARCH_AUDIT,
        AgentModule.OPPORTUNITY_SCORING,
    )
    assert handoff("lead", "APPROVED") == (AgentModule.QUALITY_GATE, AgentModule.CONVERSATION)
    assert handoff("lead", "WON") is None


def test_night() -> None:
    assert is_night(21) and is_night(3) and not is_night(6) and not is_night(19)

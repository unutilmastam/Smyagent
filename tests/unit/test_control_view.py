from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.control_snapshot import start_of_local_day
from app.domain.agents import GRAPH_EDGES, PIPELINE, AgentModule, ControlState, is_outbound_job
from app.domain.control_view import HEARTBEAT_STALE_AFTER, NodeStatus, node_status

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
C = ControlState


@pytest.mark.parametrize(
    ("effective", "heartbeat", "failures", "expected"),
    [
        (C.ACTIVE, NOW - timedelta(seconds=10), 0, NodeStatus.RUNNING),
        (C.ACTIVE, NOW - HEARTBEAT_STALE_AFTER - timedelta(seconds=1), 0, NodeStatus.STALLED),
        (C.ACTIVE, None, 0, NodeStatus.IDLE),
        (C.ACTIVE, None, 2, NodeStatus.ERROR),
        (C.PAUSED, None, 0, NodeStatus.PAUSED),
        (C.PAUSED, NOW, 0, NodeStatus.RUNNING),  # PAUSED finishes the current step
        (C.STOPPED, NOW, 0, NodeStatus.STOPPED),  # STOPPED wins even with a fresh heartbeat
        (C.STOPPED, None, 5, NodeStatus.STOPPED),
    ],
)
def test_node_status(
    effective: ControlState, heartbeat: datetime | None, failures: int, expected: NodeStatus
) -> None:
    assert (
        node_status(
            effective=effective, running_heartbeat=heartbeat, recent_failures=failures, now=NOW
        )
        is expected
    )


def test_never_running_without_a_heartbeat() -> None:
    for state in ControlState:
        for failures in (0, 3):
            status = node_status(
                effective=state, running_heartbeat=None, recent_failures=failures, now=NOW
            )
            assert status is not NodeStatus.RUNNING


def test_graph_covers_pipeline_in_order() -> None:
    assert GRAPH_EDGES[0] == (AgentModule.DISCOVERY, AgentModule.RESEARCH_AUDIT)
    assert GRAPH_EDGES[-1] == (AgentModule.QUALITY_GATE, AgentModule.CONVERSATION)
    assert len(GRAPH_EDGES) == len(PIPELINE) - 1


def test_outbound_job_prefix() -> None:
    assert is_outbound_job("outbound.email")
    assert not is_outbound_job("research.audit")


def test_local_day_start_in_tashkent() -> None:
    # 2026-10-24 20:30 UTC is already 2026-10-25 01:30 in Tashkent (UTC+5).
    now = datetime(2026, 10, 24, 20, 30, tzinfo=timezone.utc)
    assert start_of_local_day(now, "Asia/Tashkent") == datetime(
        2026, 10, 24, 19, 0, tzinfo=timezone.utc
    )

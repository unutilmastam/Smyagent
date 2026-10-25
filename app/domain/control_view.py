"""How a module is shown on the Control Center graph. Pure: derived only from real state.

Never shows "running" unless a run is RUNNING with a fresh heartbeat (CLAUDE.md §13A.1).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from app.domain.agents import ControlState

HEARTBEAT_STALE_AFTER = timedelta(minutes=2)


class NodeStatus(str, Enum):
    RUNNING = "running"
    IDLE = "idle"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    STALLED = "stalled"  # a run claims RUNNING but its heartbeat is old


def node_status(
    *,
    effective: ControlState,
    running_heartbeat: datetime | None,
    recent_failures: int,
    now: datetime,
) -> NodeStatus:
    if effective is ControlState.STOPPED:
        return NodeStatus.STOPPED
    if running_heartbeat is not None:
        if now - running_heartbeat <= HEARTBEAT_STALE_AFTER:
            return NodeStatus.RUNNING
        return NodeStatus.STALLED
    if effective is ControlState.PAUSED:
        return NodeStatus.PAUSED
    if recent_failures > 0:
        return NodeStatus.ERROR
    return NodeStatus.IDLE

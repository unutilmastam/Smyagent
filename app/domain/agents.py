"""Agent modules and kill-switch rules (CLAUDE.md §8, §13A, ADR-0006)."""

from __future__ import annotations

from enum import Enum
from itertools import pairwise


class AgentModule(str, Enum):
    ORCHESTRATOR = "orchestrator"
    DISCOVERY = "discovery"
    RESEARCH_AUDIT = "research_audit"
    OPPORTUNITY_SCORING = "opportunity_scoring"
    PROPOSAL_REQUIREMENTS = "proposal_requirements"
    CONVERSATION = "conversation"
    QUALITY_GATE = "quality_gate"


GLOBAL_CONTROL = "global"


class ControlState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


_SEVERITY = {ControlState.ACTIVE: 0, ControlState.PAUSED: 1, ControlState.STOPPED: 2}


def effective_state(global_state: ControlState, module_state: ControlState) -> ControlState:
    """The stricter of the global and per-module states wins."""
    return max(global_state, module_state, key=_SEVERITY.__getitem__)


def may_take_new_work(state: ControlState) -> bool:
    return state is ControlState.ACTIVE


# Workflow order shown on the Control Center graph (CLAUDE.md §13A.1).
PIPELINE: tuple[AgentModule, ...] = (
    AgentModule.DISCOVERY,
    AgentModule.RESEARCH_AUDIT,
    AgentModule.OPPORTUNITY_SCORING,
    AgentModule.PROPOSAL_REQUIREMENTS,
    AgentModule.QUALITY_GATE,
    AgentModule.CONVERSATION,
)
GRAPH_EDGES: tuple[tuple[AgentModule, AgentModule], ...] = tuple(pairwise(PIPELINE))

# Jobs whose type starts with this prefix send something outside the system
# (email, Telegram, ...). A global STOP cancels them while still queued.
OUTBOUND_JOB_PREFIX = "outbound."


def is_outbound_job(job_type: str) -> bool:
    return job_type.startswith(OUTBOUND_JOB_PREFIX)


class AgentHaltedError(RuntimeError):
    """Raised at a checkpoint when the module may not continue (PAUSED or STOPPED)."""

    def __init__(self, module: AgentModule, state: ControlState) -> None:
        super().__init__(f"{module.value} is {state.value}")
        self.module = module
        self.state = state


class SendingBlockedError(RuntimeError):
    """Raised immediately before an outbound provider call that must not happen."""

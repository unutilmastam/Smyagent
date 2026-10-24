"""Agent modules and kill-switch rules (CLAUDE.md §8, §13A, ADR-0006)."""

from __future__ import annotations

from enum import Enum


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

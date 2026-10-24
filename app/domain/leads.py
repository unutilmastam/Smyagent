"""Lead / deal pipeline state machine (CLAUDE.md §9.2)."""

from __future__ import annotations

from enum import Enum

from app.domain.errors import InvalidTransitionError


class LeadStage(str, Enum):
    CANDIDATE = "CANDIDATE"
    QUALIFIED = "QUALIFIED"
    PROPOSAL_DRAFTED = "PROPOSAL_DRAFTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    CONTACTED = "CONTACTED"
    RESPONDED = "RESPONDED"
    # Client confirmed the Order Brief (CLAUDE.md §8.2, ADR-0008). The service that
    # enters this stage must also require a confirmed brief (M8); the domain only
    # governs which stages may precede and follow it.
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    MEETING = "MEETING"
    WON = "WON"
    CLOSED = "CLOSED"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


S = LeadStage

# Forward path plus the explicitly allowed skips/back-steps. PAUSED, ERROR,
# LOST, DISQUALIFIED and DO_NOT_CONTACT are handled by the rules below.
_FLOW: dict[LeadStage, frozenset[LeadStage]] = {
    S.CANDIDATE: frozenset({S.QUALIFIED, S.RESPONDED}),
    S.QUALIFIED: frozenset({S.PROPOSAL_DRAFTED, S.RESPONDED}),
    S.PROPOSAL_DRAFTED: frozenset({S.AWAITING_APPROVAL, S.QUALIFIED}),
    S.AWAITING_APPROVAL: frozenset({S.APPROVED, S.PROPOSAL_DRAFTED}),
    S.APPROVED: frozenset({S.CONTACTED, S.PROPOSAL_DRAFTED}),
    S.CONTACTED: frozenset({S.RESPONDED}),
    S.RESPONDED: frozenset({S.QUALIFIED, S.PROPOSAL_DRAFTED, S.ORDER_CONFIRMED, S.MEETING, S.WON}),
    # Owner reviews the confirmed order: meet (optional), accept (WON), or ask the
    # client more questions (back to RESPONDED). Rejecting goes to LOST.
    S.ORDER_CONFIRMED: frozenset({S.MEETING, S.WON, S.RESPONDED}),
    S.MEETING: frozenset({S.PROPOSAL_DRAFTED, S.WON}),
    S.WON: frozenset({S.CLOSED}),
    S.CLOSED: frozenset(),
    S.LOST: frozenset({S.CANDIDATE}),
    S.DISQUALIFIED: frozenset({S.CANDIDATE}),
    S.DO_NOT_CONTACT: frozenset(),
}

# Stages from which a deal can be abandoned / paused / fail.
_ACTIVE = frozenset(
    {
        S.CANDIDATE,
        S.QUALIFIED,
        S.PROPOSAL_DRAFTED,
        S.AWAITING_APPROVAL,
        S.APPROVED,
        S.CONTACTED,
        S.RESPONDED,
        S.ORDER_CONFIRMED,
        S.MEETING,
    }
)

# Inbound clients (who message the bot first) start here.
INBOUND_ENTRY_STAGE = S.RESPONDED


def is_terminal(stage: LeadStage) -> bool:
    return stage in (S.CLOSED, S.DO_NOT_CONTACT)


def can_transition(
    current: LeadStage, target: LeadStage, *, resume_stage: LeadStage | None = None
) -> bool:
    """Whether `current -> target` is allowed.

    `resume_stage` is the stage a PAUSED/ERROR lead came from; it may only
    return there (or be abandoned).
    """
    if current == target:
        return False
    if target is S.DO_NOT_CONTACT:
        return current is not S.DO_NOT_CONTACT  # opt-out overrides everything
    if current is S.DO_NOT_CONTACT:
        return False
    if current in (S.PAUSED, S.ERROR):
        return target in (S.LOST, S.DISQUALIFIED) or target == resume_stage
    if target in (S.PAUSED, S.ERROR, S.LOST, S.DISQUALIFIED):
        return current in _ACTIVE
    return target in _FLOW.get(current, frozenset())


def ensure_transition(
    current: LeadStage, target: LeadStage, *, resume_stage: LeadStage | None = None
) -> None:
    if not can_transition(current, target, resume_stage=resume_stage):
        raise InvalidTransitionError("lead", current.value, target.value)

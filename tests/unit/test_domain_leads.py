from __future__ import annotations

import pytest

from app.domain.errors import InvalidTransitionError
from app.domain.leads import INBOUND_ENTRY_STAGE, LeadStage, can_transition, ensure_transition

S = LeadStage


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.CANDIDATE, S.QUALIFIED),
        (S.QUALIFIED, S.PROPOSAL_DRAFTED),
        (S.PROPOSAL_DRAFTED, S.AWAITING_APPROVAL),
        (S.AWAITING_APPROVAL, S.APPROVED),
        (S.APPROVED, S.CONTACTED),
        (S.CONTACTED, S.RESPONDED),
        (S.RESPONDED, S.MEETING),
        (S.MEETING, S.WON),
        (S.WON, S.CLOSED),
        (S.AWAITING_APPROVAL, S.PROPOSAL_DRAFTED),  # owner rejects -> redraft
        (S.RESPONDED, S.WON),  # allowed skip
        (S.LOST, S.CANDIDATE),  # reopen
    ],
)
def test_allowed_transitions(current: LeadStage, target: LeadStage) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.CANDIDATE, S.CONTACTED),  # cannot contact without approval
        (S.PROPOSAL_DRAFTED, S.APPROVED),  # approval cannot be skipped
        (S.QUALIFIED, S.APPROVED),
        (S.CLOSED, S.CANDIDATE),
        (S.WON, S.LOST),
        (S.CANDIDATE, S.CANDIDATE),
    ],
)
def test_forbidden_transitions(current: LeadStage, target: LeadStage) -> None:
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransitionError):
        ensure_transition(current, target)


@pytest.mark.parametrize("stage", [s for s in LeadStage if s is not S.DO_NOT_CONTACT])
def test_do_not_contact_reachable_from_every_stage(stage: LeadStage) -> None:
    assert can_transition(stage, S.DO_NOT_CONTACT)


@pytest.mark.parametrize("target", [s for s in LeadStage if s is not S.DO_NOT_CONTACT])
def test_do_not_contact_is_terminal(target: LeadStage) -> None:
    assert not can_transition(S.DO_NOT_CONTACT, target, resume_stage=target)


def test_paused_only_resumes_to_previous_stage() -> None:
    assert can_transition(S.QUALIFIED, S.PAUSED)
    assert can_transition(S.PAUSED, S.QUALIFIED, resume_stage=S.QUALIFIED)
    assert not can_transition(S.PAUSED, S.APPROVED, resume_stage=S.QUALIFIED)
    assert can_transition(S.PAUSED, S.LOST, resume_stage=S.QUALIFIED)


def test_finished_deals_cannot_be_paused() -> None:
    assert not can_transition(S.WON, S.PAUSED)
    assert not can_transition(S.CLOSED, S.ERROR)


def test_inbound_clients_enter_at_responded() -> None:
    assert INBOUND_ENTRY_STAGE is S.RESPONDED

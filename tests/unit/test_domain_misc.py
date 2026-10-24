from __future__ import annotations

import random
from datetime import timedelta

import pytest

from app.domain.actors import Actor, ActorKind
from app.domain.agents import ControlState, effective_state, may_take_new_work
from app.domain.errors import DomainError
from app.domain.jobs import MAX_BACKOFF_SECONDS, retry_delay

C = ControlState


def test_actor_roundtrip() -> None:
    assert str(Actor.agent("discovery")) == "agent:discovery"
    assert Actor.parse("user:42") == Actor(ActorKind.USER, "42")


@pytest.mark.parametrize("raw", ["nobody", "robot:x", "user:", "user:a b"])
def test_actor_rejects_invalid(raw: str) -> None:
    with pytest.raises(DomainError):
        Actor.parse(raw)


@pytest.mark.parametrize(
    ("glob", "module", "expected"),
    [
        (C.ACTIVE, C.ACTIVE, C.ACTIVE),
        (C.ACTIVE, C.PAUSED, C.PAUSED),
        (C.PAUSED, C.ACTIVE, C.PAUSED),
        (C.STOPPED, C.ACTIVE, C.STOPPED),
        (C.PAUSED, C.STOPPED, C.STOPPED),
    ],
)
def test_effective_state_stricter_wins(glob: C, module: C, expected: C) -> None:
    assert effective_state(glob, module) is expected


def test_only_active_takes_new_work() -> None:
    assert may_take_new_work(C.ACTIVE)
    assert not may_take_new_work(C.PAUSED)
    assert not may_take_new_work(C.STOPPED)


def test_retry_delay_grows_and_is_capped() -> None:
    rng = random.Random(1)
    first = retry_delay(1, rng=rng)
    assert timedelta(seconds=15) <= first <= timedelta(seconds=30)
    assert retry_delay(50, rng=rng) <= timedelta(seconds=MAX_BACKOFF_SECONDS)
    with pytest.raises(ValueError):
        retry_delay(0)

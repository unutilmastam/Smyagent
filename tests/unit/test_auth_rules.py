from __future__ import annotations

import pytest

from app.core.security import hash_password, keyed_hash, tokens_equal, verify_password
from app.domain.auth import (
    MAX_FAILURES_PER_IP,
    MAX_FAILURES_PER_USERNAME,
    PasswordPolicyError,
    check_password_policy,
    is_throttled,
    normalize_username,
)
from app.domain.errors import DomainError
from app.web.auth import safe_next_path


@pytest.mark.parametrize(
    "password", ["short", "aaaaaaaaaaaaaaaa", " leading-space-pass", "bahrullo-2026-secret"]
)
def test_password_policy_rejects(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        check_password_policy(password, username="bahrullo")


def test_password_policy_accepts_strong() -> None:
    check_password_policy("Denov-ITcoDe-2026!", username="bahrullo")


def test_username_normalization() -> None:
    assert normalize_username("  Bahrullo ") == "bahrullo"
    with pytest.raises(DomainError):
        normalize_username("@ITcoDe_Uz")


def test_throttle_thresholds() -> None:
    assert not is_throttled(MAX_FAILURES_PER_USERNAME - 1, 0)
    assert is_throttled(MAX_FAILURES_PER_USERNAME, 0)
    assert is_throttled(0, MAX_FAILURES_PER_IP)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Denov-ITcoDe-2026!")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "Denov-ITcoDe-2026!")
    assert not verify_password(hashed, "wrong")
    assert not verify_password("not-a-hash", "x")


def test_tokens_equal_and_keyed_hash() -> None:
    assert tokens_equal("abc", "abc")
    assert not tokens_equal("abc", "abd")
    assert not tokens_equal(None, "abc")
    assert not tokens_equal("", "")
    assert keyed_hash("k", "1.2.3.4") != "1.2.3.4"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/companies?page=2", "/companies?page=2"),
        ("//evil.example", "/"),
        ("https://evil.example", "/"),
        ("/\\evil", "/"),
        (None, "/"),
    ],
)
def test_safe_next_path(value: str | None, expected: str) -> None:
    assert safe_next_path(value) == expected

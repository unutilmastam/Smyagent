"""Authentication rules: roles, password policy, login throttling (CLAUDE.md §15.1)."""

from __future__ import annotations

import re
from datetime import timedelta
from enum import Enum

from app.domain.errors import DomainError


class Role(str, Enum):
    OWNER = "owner"
    VIEWER = "viewer"


MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")

# Throttling windows. Failures are counted per username and per client IP.
LOGIN_WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_USERNAME = 5
MAX_FAILURES_PER_IP = 20

SESSION_ABSOLUTE_LIFETIME = timedelta(days=30)
SESSION_IDLE_TIMEOUT = timedelta(days=7)
# Avoid a DB write on every request: refresh `last_seen_at` at most this often.
SESSION_TOUCH_INTERVAL = timedelta(minutes=5)


class PasswordPolicyError(DomainError):
    pass


def normalize_username(username: str) -> str:
    value = username.strip().lower()
    if not _USERNAME.match(value):
        raise DomainError("username must be 3-32 chars: a-z, 0-9, '_', '.', '-'")
    return value


def check_password_policy(password: str, *, username: str | None = None) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"password must be at most {MAX_PASSWORD_LENGTH} characters")
    if password.strip() != password:
        raise PasswordPolicyError("password must not start or end with whitespace")
    if len(set(password)) < 6:
        raise PasswordPolicyError("password is too repetitive")
    if username and username.lower() in password.lower():
        raise PasswordPolicyError("password must not contain the username")


def is_throttled(failures_for_username: int, failures_for_ip: int) -> bool:
    return (
        failures_for_username >= MAX_FAILURES_PER_USERNAME or failures_for_ip >= MAX_FAILURES_PER_IP
    )

"""Security primitives: password hashing, opaque tokens, constant-time compare."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Moderate parameters: shared hosting has little RAM/CPU; still well above OWASP minimum
# (m=19 MiB, t=2). Rehash-on-login upgrades old hashes if these change.
_hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)

TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# Verified against when the username does not exist, so response time does not
# reveal which usernames are valid.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def new_token() -> str:
    """Opaque random token for cookies / CSRF (256 bits)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Session tokens are stored hashed: a DB leak does not yield usable cookies."""
    return hashlib.sha256(token.encode()).hexdigest()


def keyed_hash(secret: str, value: str) -> str:
    """HMAC used to store IP addresses without keeping them in clear text."""
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def tokens_equal(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode(), b.encode())

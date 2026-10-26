"""RFC 6238 TOTP and secret encryption (M3-totp)."""

from __future__ import annotations

import base64

import pytest

from app.core import totp
from app.core.crypto import DecryptionError, decrypt, encrypt

# RFC 6238 Appendix B, SHA-1 secret "12345678901234567890", last 6 digits.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("unix", "code"),
    [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037")],
)
def test_rfc6238_vectors(unix: int, code: str) -> None:
    assert totp.code_at(RFC_SECRET, unix // totp.PERIOD) == code
    assert totp.verify(RFC_SECRET, code, now=unix) == unix // totp.PERIOD


def test_window_replay_and_format() -> None:
    now = 1_760_000_000.0
    step = totp.current_step(now)
    prev = totp.code_at(RFC_SECRET, step - 1)
    assert totp.verify(RFC_SECRET, prev, now=now) == step - 1  # 30 s clock drift ok
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step - 2), now=now) is None
    current = totp.code_at(RFC_SECRET, step)
    assert totp.verify(RFC_SECRET, current, now=now, last_step=step) is None  # replay
    assert totp.verify(RFC_SECRET, f"{current[:3]} {current[3:]}", now=now) == step
    assert totp.verify(RFC_SECRET, "12345", now=now) is None


def test_secret_and_uri() -> None:
    secret = totp.new_secret()
    assert len(secret) == 32 and secret.isalnum()
    uri = totp.provisioning_uri(secret, account="bahrullo")
    assert uri.startswith("otpauth://totp/SMY%20Agent%3Abahrullo?secret=")
    assert "issuer=SMY%20Agent" in uri and "digits=6" in uri and "period=30" in uri
    assert totp.group("ABCDEFGH") == "ABCD EFGH"


def test_encryption_roundtrip_and_wrong_key() -> None:
    token = encrypt("k" * 40, "totp", "SECRET")
    assert "SECRET" not in token and decrypt("k" * 40, "totp", token) == "SECRET"
    with pytest.raises(DecryptionError):
        decrypt("x" * 40, "totp", token)
    with pytest.raises(DecryptionError):
        decrypt("k" * 40, "other-purpose", token)

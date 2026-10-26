"""RFC 6238 TOTP (30 s, 6 digits, SHA-1): what Google / Microsoft Authenticator use.

Standard library only. `verify` returns the matched time step so callers can refuse a
code that was already used (replay protection).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

PERIOD = 30
DIGITS = 6
SECRET_BYTES = 20  # 160 bits, RFC 4226 recommendation


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // PERIOD)


def verify(
    secret: str,
    code: str,
    *,
    now: float | None = None,
    last_step: int | None = None,
    window: int = 1,
) -> int | None:
    """Matched step (±`window` steps for clock drift) newer than `last_step`, else None."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != DIGITS:
        return None
    step = current_step(now)
    for candidate in range(step - window, step + window + 1):
        if last_step is not None and candidate <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(secret: str, *, account: str, issuer: str = "SMY Agent") -> str:
    """otpauth:// URI encoded in the QR code."""
    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD}"
    )


def group(secret: str) -> str:
    """Manual-entry form: groups of four characters."""
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))

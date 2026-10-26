"""Encryption of small secrets stored in the database (e.g. TOTP seeds).

The key is derived from APP_SECRET_KEY, so a database dump alone cannot produce login
codes. Changing APP_SECRET_KEY makes stored seeds unreadable: TOTP must then be set up
again (or disabled with `python -m app.cli disable-totp`).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class DecryptionError(ValueError):
    pass


def _fernet(secret_key: str, purpose: str) -> Fernet:
    raw = hashlib.sha256(f"smy-agent:{purpose}:".encode() + secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt(secret_key: str, purpose: str, value: str) -> str:
    return _fernet(secret_key, purpose).encrypt(value.encode()).decode()


def decrypt(secret_key: str, purpose: str, token: str) -> str:
    try:
        return _fernet(secret_key, purpose).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("cannot decrypt (APP_SECRET_KEY changed?)") from exc

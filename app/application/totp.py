"""Two-factor login with an authenticator app (M3-totp, CLAUDE.md §15.1).

Setup: `begin_setup` stores a new seed as *pending* and returns the QR code; `confirm`
needs one valid code from the app, then enables TOTP and returns 10 one-time recovery
codes (shown once, stored as Argon2 hashes). Login: `verify_login` accepts a fresh TOTP
code (never the same 30 s step twice) or an unused recovery code. Disabling from the
dashboard needs the password and a code; from cPanel Terminal: `disable-totp` CLI.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

import segno
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import totp
from app.core.crypto import DecryptionError, decrypt, encrypt
from app.core.security import hash_password, verify_password
from app.domain.actors import Actor
from app.domain.errors import DomainError
from app.infrastructure.database.models import TotpRecoveryCode, User
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.workflow import AuditLogRepository

PURPOSE = "totp"
RECOVERY_CODES = 10
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o/1/l/i: easy to read and type


class TotpError(DomainError):
    pass


@dataclass(frozen=True)
class Setup:
    secret_grouped: str  # for manual entry
    uri: str
    qr_svg_data_uri: str  # <img src> (CSP allows data: images)


def new_recovery_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _normalize_recovery(code: str) -> str:
    raw = "".join(ch for ch in code.lower() if ch.isalnum())
    return f"{raw[:5]}-{raw[5:]}" if len(raw) == 10 else ""


class TotpService:
    def __init__(self, session: Session, *, secret_key: str) -> None:
        self.session = session
        self.secret_key = secret_key
        self.audit = AuditLogRepository(session)

    # -- setup -------------------------------------------------------------------

    def begin_setup(self, user: User) -> Setup:
        if user.totp_enabled:
            raise TotpError("TOTP is already enabled")
        secret = totp.new_secret()
        user.totp_pending_enc = encrypt(self.secret_key, PURPOSE, secret)
        self.session.flush()
        return self._setup(user, secret)

    def pending_setup(self, user: User) -> Setup | None:
        """The QR again (page reload) without generating a new seed."""
        if user.totp_pending_enc is None or user.totp_enabled:
            return None
        try:
            secret = decrypt(self.secret_key, PURPOSE, user.totp_pending_enc)
        except DecryptionError:
            return None
        return self._setup(user, secret)

    def _setup(self, user: User, secret: str) -> Setup:
        uri = totp.provisioning_uri(secret, account=user.username)
        # A complete SVG document (with xmlns) as a data: URI, so <img> can display it.
        data_uri = segno.make(uri, error="m").svg_data_uri(
            scale=5, border=2, dark="#111827", light="#ffffff"
        )
        return Setup(totp.group(secret), uri, data_uri)

    def confirm(self, user: User, code: str, *, now: datetime | None = None) -> list[str]:
        if user.totp_pending_enc is None:
            raise TotpError("start the setup first")
        secret = decrypt(self.secret_key, PURPOSE, user.totp_pending_enc)
        step = totp.verify(secret, code, now=(now or utcnow()).timestamp())
        if step is None:
            raise TotpError("wrong code")
        user.totp_secret_enc = user.totp_pending_enc
        user.totp_pending_enc = None
        user.totp_enabled_at = now or utcnow()
        user.totp_last_step = step
        codes = self._replace_recovery_codes(user)
        self._log(user, "auth.totp_enabled")
        return codes

    # -- login -------------------------------------------------------------------

    def verify_login(self, user: User, code: str, *, now: datetime | None = None) -> str | None:
        """'totp' or 'recovery' when the code is accepted, else None."""
        if not user.totp_enabled or user.totp_secret_enc is None:
            return None
        now = now or utcnow()
        try:
            secret = decrypt(self.secret_key, PURPOSE, user.totp_secret_enc)
        except DecryptionError:
            return None
        step = totp.verify(secret, code, now=now.timestamp(), last_step=user.totp_last_step)
        if step is not None:
            user.totp_last_step = step
            self.session.flush()
            return "totp"
        recovery = _normalize_recovery(code)
        if recovery:
            for row in self._unused_codes(user):
                if verify_password(row.code_hash, recovery):
                    row.used_at = now
                    self._log(user, "auth.totp_recovery_used", left=self.remaining(user))
                    return "recovery"
        return None

    def remaining(self, user: User) -> int:
        return len(self._unused_codes(user))

    # -- maintenance -------------------------------------------------------------

    def regenerate_codes(self, user: User, code: str) -> list[str]:
        if self.verify_login(user, code) != "totp":
            raise TotpError("wrong code")
        codes = self._replace_recovery_codes(user)
        self._log(user, "auth.totp_codes_regenerated")
        return codes

    def disable(self, user: User, *, password: str, code: str) -> None:
        if not verify_password(user.password_hash, password):
            raise TotpError("wrong password")
        if self.verify_login(user, code) is None:
            raise TotpError("wrong code")
        self._clear(user)
        self._log(user, "auth.totp_disabled")

    def disable_by_operator(self, user: User) -> None:
        """cPanel Terminal recovery (`python -m app.cli disable-totp`)."""
        self._clear(user)
        self._log(user, "auth.totp_disabled_cli", actor=Actor.system("cli"))

    # -- helpers -----------------------------------------------------------------

    def _clear(self, user: User) -> None:
        user.totp_secret_enc = user.totp_pending_enc = None
        user.totp_enabled_at = None
        user.totp_last_step = None
        for row in self.session.scalars(
            select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id)
        ):
            self.session.delete(row)
        self.session.flush()

    def _replace_recovery_codes(self, user: User) -> list[str]:
        for row in self.session.scalars(
            select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id)
        ):
            self.session.delete(row)
        codes = [new_recovery_code() for _ in range(RECOVERY_CODES)]
        for code in codes:
            self.session.add(TotpRecoveryCode(user_id=user.id, code_hash=hash_password(code)))
        self.session.flush()
        return codes

    def _unused_codes(self, user: User) -> list[TotpRecoveryCode]:
        return list(
            self.session.scalars(
                select(TotpRecoveryCode).where(
                    TotpRecoveryCode.user_id == user.id, TotpRecoveryCode.used_at.is_(None)
                )
            )
        )

    def _log(
        self, user: User, action: str, *, actor: Actor | None = None, **details: object
    ) -> None:
        self.audit.add(
            actor=actor or Actor.user(str(user.id)),
            action=action,
            entity_type="user",
            entity_id=user.id,
            details={"username": user.username, **details},
        )

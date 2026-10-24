"""Login, logout, session resolution and owner bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_token,
    keyed_hash,
    needs_rehash,
    new_token,
    verify_password,
)
from app.domain.actors import Actor
from app.domain.auth import (
    LOGIN_WINDOW,
    SESSION_ABSOLUTE_LIFETIME,
    SESSION_IDLE_TIMEOUT,
    SESSION_TOUCH_INTERVAL,
    Role,
    check_password_policy,
    is_throttled,
    normalize_username,
)
from app.domain.errors import DomainError
from app.infrastructure.database.models import User, UserSession
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.auth import (
    LoginAttemptRepository,
    SessionRepository,
    UserRepository,
)
from app.infrastructure.repositories.workflow import AuditLogRepository

# Single generic message: never reveal whether the username exists.
INVALID_CREDENTIALS = "Invalid username or password"


class AuthError(DomainError):
    pass


class ThrottledError(AuthError):
    pass


class OwnerExistsError(DomainError):
    pass


@dataclass(frozen=True)
class LoginResult:
    user: User
    session: UserSession
    token: str  # raw cookie value; never stored or logged


class AuthService:
    def __init__(self, session: Session, *, secret_key: str) -> None:
        self.session = session
        self.secret_key = secret_key
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)
        self.attempts = LoginAttemptRepository(session)
        self.audit = AuditLogRepository(session)

    # -- bootstrap ---------------------------------------------------------

    def create_owner(self, username: str, password: str) -> User:
        """One-time owner creation (CLI). Refuses if an owner already exists."""
        name = normalize_username(username)
        if self.users.count_owners() > 0:
            raise OwnerExistsError("an owner account already exists")
        check_password_policy(password, username=name)
        user = self.users.add(
            User(username=name, password_hash=hash_password(password), role=Role.OWNER)
        )
        self.audit.add(
            actor=Actor.system("cli"),
            action="user.create_owner",
            entity_type="user",
            entity_id=user.id,
            details={"username": name},
        )
        return user

    # -- login / logout ----------------------------------------------------

    def login(
        self, username: str, password: str, *, client_ip: str, now: datetime | None = None
    ) -> LoginResult:
        now = now or utcnow()
        name = username.strip().lower()[:64]
        ip_hash = keyed_hash(self.secret_key, client_ip or "unknown")
        since = now - LOGIN_WINDOW
        if is_throttled(
            self.attempts.failures_since(since, username=name),
            self.attempts.failures_since(since, ip_hash=ip_hash),
        ):
            self.audit.add(
                actor=Actor.system("auth"),
                action="auth.login_throttled",
                details={"username": name},
            )
            raise ThrottledError("Too many failed attempts. Try again in 15 minutes.")

        user = self.users.by_username(name)
        # Always run one Argon2 verification so timing does not reveal valid usernames.
        valid = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, password)
        if user is None or not valid or not user.is_active:
            self.attempts.record(username=name, ip_hash=ip_hash, success=False, now=now)
            self.audit.add(
                actor=Actor.system("auth"), action="auth.login_failed", details={"username": name}
            )
            raise AuthError(INVALID_CREDENTIALS)

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = now
        self.attempts.record(username=name, ip_hash=ip_hash, success=True, now=now)
        self.sessions.delete_expired(now)
        token = new_token()
        user_session = self.sessions.add(
            UserSession(
                user_id=user.id,
                token_hash=hash_token(token),
                csrf_token=new_token(),
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_ABSOLUTE_LIFETIME,
            )
        )
        self.audit.add(
            actor=Actor.user(str(user.id)),
            action="auth.login",
            entity_type="user",
            entity_id=user.id,
        )
        return LoginResult(user=user, session=user_session, token=token)

    def logout(self, token: str) -> None:
        user_session = self.sessions.by_token_hash(hash_token(token))
        if user_session is None:
            return
        self.audit.add(
            actor=Actor.user(str(user_session.user_id)),
            action="auth.logout",
            entity_type="user",
            entity_id=user_session.user_id,
        )
        self.sessions.delete(user_session)

    # -- per request -------------------------------------------------------

    def resolve(self, token: str | None, *, now: datetime | None = None) -> UserSession | None:
        """Return the live session for a cookie token, or None (expired/unknown/inactive)."""
        if not token or len(token) > 128:
            return None
        now = now or utcnow()
        user_session = self.sessions.by_token_hash(hash_token(token))
        if user_session is None:
            return None
        expired = (
            user_session.expires_at <= now
            or user_session.last_seen_at + SESSION_IDLE_TIMEOUT <= now
        )
        if expired or not user_session.user.is_active:
            self.sessions.delete(user_session)
            return None
        if now - user_session.last_seen_at >= SESSION_TOUCH_INTERVAL:
            user_session.last_seen_at = now
            self.session.flush()
        return user_session

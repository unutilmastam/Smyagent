"""Users, sessions and login attempts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domain.auth import Role
from app.infrastructure.database.models import LoginAttempt, User, UserSession


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def by_username(self, username: str) -> User | None:
        return self.session.scalars(select(User).where(User.username == username)).first()

    def count_owners(self) -> int:
        stmt = select(func.count()).select_from(User).where(User.role == Role.OWNER)
        return int(self.session.scalar(stmt) or 0)

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        self.session.flush()
        return user_session

    def by_token_hash(self, token_hash: str) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.token_hash == token_hash)
        return self.session.scalars(stmt).first()

    def delete(self, user_session: UserSession) -> None:
        self.session.delete(user_session)
        self.session.flush()

    def delete_expired(self, now: datetime) -> int:
        result = self.session.execute(
            delete(UserSession)
            .where(UserSession.expires_at < now)
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0)


class LoginAttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, *, username: str, ip_hash: str, success: bool, now: datetime) -> None:
        self.session.add(
            LoginAttempt(username=username, ip_hash=ip_hash, success=success, created_at=now)
        )
        self.session.flush()

    def failures_since(
        self, since: datetime, *, username: str | None = None, ip_hash: str | None = None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.success.is_(False), LoginAttempt.created_at >= since)
        )
        if username is not None:
            stmt = stmt.where(LoginAttempt.username == username)
        if ip_hash is not None:
            stmt = stmt.where(LoginAttempt.ip_hash == ip_hash)
        return int(self.session.scalar(stmt) or 0)

    def prune(self, before: datetime) -> int:
        result = self.session.execute(
            delete(LoginAttempt)
            .where(LoginAttempt.created_at < before)
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0)

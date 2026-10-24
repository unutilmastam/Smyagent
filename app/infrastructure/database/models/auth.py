"""Users, login sessions and login attempts (CLAUDE.md §10 Identity, §15.1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.auth import Role
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID, UTCDateTime, utcnow


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Two roles for now (owner, viewer); a roles table arrives with full RBAC.
    role: Mapped[Role] = mapped_column(enum_column(Role, length=16), default=Role.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(UUIDPrimaryKey, Base):
    """Server-side session. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (Index("ix_sessions_expires", "expires_at"),)


class LoginAttempt(UUIDPrimaryKey, Base):
    """Recent login attempts for throttling. IP stored only as a keyed hash."""

    __tablename__ = "login_attempts"

    username: Mapped[str] = mapped_column(String(64))
    ip_hash: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (
        Index("ix_login_attempts_username_created", "username", "created_at"),
        Index("ix_login_attempts_ip_created", "ip_hash", "created_at"),
    )

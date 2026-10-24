"""Engine and session factory."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

# Shared-hosting MySQL often has a short wait_timeout; recycle before it.
MYSQL_POOL_RECYCLE_SECONDS = 280


def build_engine(url: str, *, echo: bool = False) -> Engine:
    parsed = make_url(url)
    kwargs: dict[str, Any] = {"echo": echo, "pool_pre_ping": True, "future": True}
    if parsed.get_backend_name() == "mysql":
        kwargs["pool_recycle"] = MYSQL_POOL_RECYCLE_SECONDS
        # Small pool: shared hosting limits processes/connections.
        kwargs["pool_size"] = 3
        kwargs["max_overflow"] = 2
        query = dict(parsed.query)
        query.setdefault("charset", "utf8mb4")
        parsed = parsed.set(query=query)
    engine = create_engine(parsed, **kwargs)
    if parsed.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _sqlite_on_connect)
    return engine


def _sqlite_on_connect(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Database:
    """Owns the engine and hands out sessions. One instance per process."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = build_engine(url, echo=echo)
        self._sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._sessionmaker()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Session committed on success, rolled back on any exception."""
        session = self._sessionmaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def dispose(self) -> None:
        self.engine.dispose()

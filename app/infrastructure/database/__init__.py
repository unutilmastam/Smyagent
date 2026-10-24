"""SQLAlchemy setup portable across MySQL/MariaDB, SQLite and PostgreSQL (ADR-0002)."""

from app.infrastructure.database.base import Base
from app.infrastructure.database.session import Database

__all__ = ["Base", "Database"]

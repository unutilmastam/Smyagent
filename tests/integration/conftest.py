"""Database fixtures.

Default: a fresh SQLite file per test session. Set TEST_DATABASE_URL (e.g.
`mysql+pymysql://root:root@127.0.0.1:3306/smy_test`) to run the same tests on
MariaDB/MySQL, as CI does. The schema is always created by Alembic migrations,
never by `metadata.create_all`, so these tests also exercise the migrations.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.infrastructure.database import Base, Database
from app.infrastructure.repositories.controls import AgentControlRepository

ROOT = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    return f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> Iterator[Database]:
    cfg = alembic_config(database_url)
    command.downgrade(cfg, "base")  # clean slate if a previous run left tables
    command.upgrade(cfg, "head")
    database = Database(database_url)
    yield database
    database.dispose()


@pytest.fixture
def db(migrated_database: Database) -> Iterator[Database]:
    """Empty tables (controls reseeded ACTIVE) before each test."""
    with migrated_database.transaction() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        AgentControlRepository(session).ensure_rows(Actor.system("test"))
    yield migrated_database


@pytest.fixture
def session(db: Database) -> Iterator[Session]:
    s = db.session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()

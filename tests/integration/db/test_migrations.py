"""Migrations must build exactly the schema the models describe (ADR-0002)."""

from __future__ import annotations

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select

from app.infrastructure.database import Base, Database
from app.infrastructure.database.models import AgentControl
from tests.integration.conftest import alembic_config


def test_upgrade_matches_models_and_downgrade_is_clean(database_url: str) -> None:
    cfg = alembic_config(database_url)
    database = Database(database_url)
    try:
        command.downgrade(cfg, "base")
        with database.engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) <= {"alembic_version"}

        command.upgrade(cfg, "head")
        with database.engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], f"models and migrations differ: {diff}"

        with database.transaction() as session:
            modules = set(session.scalars(select(AgentControl.module)))
        assert "global" in modules and "discovery" in modules and len(modules) == 8
    finally:
        command.upgrade(cfg, "head")  # leave schema for the other tests
        database.dispose()


def test_mysql_tables_are_utf8mb4_innodb(db: Database) -> None:
    if db.engine.dialect.name != "mysql":
        return
    with db.engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME <> 'alembic_version'"
        ).all()
    assert rows
    for name, engine, collation in rows:
        assert engine == "InnoDB", name
        assert collation.startswith("utf8mb4"), name

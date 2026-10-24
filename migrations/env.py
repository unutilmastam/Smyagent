"""Alembic environment. URL comes from app settings, never from alembic.ini."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

import app.infrastructure.database.models  # noqa: F401  (registers tables)
from app.core.config import get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import build_engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # Tests pass an explicit URL; otherwise use DATABASE_URL from settings.
    override = config.attributes.get("database_url")
    if override:
        return str(override)
    return get_settings().database_url.get_secret_value()


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = build_engine(_url())
    try:
        with engine.connect() as conn:
            _configure(conn)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

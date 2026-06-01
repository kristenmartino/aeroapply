"""Alembic environment.

The DB URL comes from DATABASE_URL / aeroapply.config (not alembic.ini). Migrations
are raw-DDL for now (``target_metadata = None``); ``--autogenerate`` is enabled once
SQLAlchemy ORM models land (EPIC-GRAPH).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    try:
        from aeroapply.config import get_settings

        url = get_settings().database_url
    except Exception:
        url = os.environ.get(
            "DATABASE_URL", "postgresql://aeroapply:aeroapply@localhost:5432/aeroapply"
        )
    # SQLAlchemy needs an explicit psycopg3 driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


config.set_main_option("sqlalchemy.url", _database_url())
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

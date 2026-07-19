"""Alembic migration environment.

This file is executed by Alembic every time a migration command is run.
It connects ``Base.metadata`` to Alembic so that ``--autogenerate`` can diff
the declared ORM models against the current database schema.

DATABASE_URL is read from the environment (or ``backend/.env``) and injected
into the Alembic ``Config`` at runtime, overriding the placeholder value in
``alembic.ini``.

Usage::

    # From the backend/ directory:
    alembic upgrade head
    alembic downgrade -1
    alembic revision --autogenerate -m "add products table"

sys.path note:
    ``alembic.ini`` sets ``prepend_sys_path = .`` which adds the ``backend/``
    directory to ``sys.path`` before this file is executed, enabling
    ``from core.database.base import Base`` to resolve correctly.
"""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

# Import Base so its metadata is populated with all registered models.
# Any module that defines ORM models must be imported somewhere in the
# application's import tree before this point, otherwise Alembic will not
# see those models during autogenerate.
#
# For Epic 1 there are no concrete tables, so only Base.metadata is needed.
# Epic 002 (Authentication): import auth models so Alembic discovers all 7 tables.
# Epic 003 (Companies): import companies models so Alembic discovers all company tables.
import core.events.outbox  # noqa: E402, F401
import modules.auth.models  # noqa: E402, F401
import modules.companies.models  # noqa: E402, F401
from core.database.base import Base  # noqa: E402

_database_url = os.getenv("DATABASE_URL")

if not _database_url:
    raise RuntimeError("DATABASE_URL is not set. Check backend/.env")

# ── Alembic Config object ──────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from the environment so that alembic.ini never
# stores a real database URL (which could be committed to version control).
_database_url = os.environ.get("DATABASE_URL") or os.getenv("DATABASE_URL", "")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)

# ── Logging ────────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# ── Target metadata ────────────────────────────────────────────────────────
# ``Base.metadata`` is the single source of truth for the schema.
# Alembic compares it against the live database to generate migrations.
target_metadata = Base.metadata


# ── Migration runners ──────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Run migrations without an active database connection.

    Used when generating SQL scripts for review before applying them,
    e.g. ``alembic upgrade head --sql``.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with an active database connection.

    This is the standard path for ``alembic upgrade head`` and
    ``alembic downgrade``.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

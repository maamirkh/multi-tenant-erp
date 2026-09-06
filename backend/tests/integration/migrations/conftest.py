"""Shared fixtures for Epic 9A real-PostgreSQL migration tests (Gate A).

Partial unique indexes and CHECK constraints introduced by migrations
057-061 are PostgreSQL-specific; the project-wide SQLite in-memory
``conftest.py`` fixtures (``db_session``/``test_client``) cannot substitute
here (plan.md §32). Every test in this package therefore gets its own
throwaway, uniquely-named database on the SAME running ``db`` Docker
Compose service the application uses — never the live ``devsphere_dev``
database — created and dropped per test so tests are isolated and
repeatable.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _real_database_url() -> str:
    """The application's real DATABASE_URL (points at ``db``, real Postgres)."""
    url = os.environ.get("DATABASE_URL", "")
    if not url or "sqlite" in url:
        pytest.skip(
            "DATABASE_URL is not a real PostgreSQL URL — skipping "
            "real-Postgres migration test (see conftest.py note)."
        )
    return url


def _with_dbname(url: str, dbname: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", "", ""))


def _admin_engine() -> sa.engine.Engine:
    """Engine connected to the ``postgres`` maintenance database.

    ``CREATE DATABASE``/``DROP DATABASE`` cannot run inside a transaction
    block, hence ``isolation_level="AUTOCOMMIT"``.
    """
    admin_url = _with_dbname(_real_database_url(), "postgres")
    return sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")


@pytest.fixture
def pg_test_db() -> Generator[str, None, None]:
    """Create a uniquely-named, empty PostgreSQL database; drop it after.

    Yields the database's ``DATABASE_URL``. The caller is responsible for
    running whatever Alembic migrations the test needs against it.
    """
    dbname = f"test_9a_{uuid.uuid4().hex[:12]}"
    admin = _admin_engine()
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{dbname}"'))

    test_url = _with_dbname(_real_database_url(), dbname)
    try:
        yield test_url
    finally:
        # Terminate any lingering backends (Alembic uses NullPool and closes
        # its connections, but be defensive) before dropping.
        with admin.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :dbname AND pid <> pg_backend_pid()"
                ),
                {"dbname": dbname},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        admin.dispose()


def alembic_upgrade(database_url: str, revision: str = "head") -> None:
    """Run ``alembic upgrade <revision>`` against ``database_url``.

    Mirrors ``migrations/env.py``, which reads ``DATABASE_URL`` fresh from
    the environment on every invocation.
    """
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        cfg = Config(str(ALEMBIC_INI))
        command.upgrade(cfg, revision)
    finally:
        if previous is not None:
            os.environ["DATABASE_URL"] = previous


def alembic_downgrade(database_url: str, revision: str) -> None:
    """Run ``alembic downgrade <revision>`` against ``database_url``."""
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        cfg = Config(str(ALEMBIC_INI))
        command.downgrade(cfg, revision)
    finally:
        if previous is not None:
            os.environ["DATABASE_URL"] = previous


def db_engine(database_url: str) -> sa.engine.Engine:
    """A plain SQLAlchemy engine for making assertions against a test DB."""
    return sa.create_engine(database_url)

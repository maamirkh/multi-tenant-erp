"""Shared pytest fixtures for the DevSphere ERP backend test suite.

Fixture hierarchy:
    test_settings  (function-scoped)   — isolated Settings for each test
    test_db_engine (session-scoped)    — in-memory SQLite engine, schema created once
    db_session     (function-scoped)   — single session per test, rolled back after
    test_client    (function-scoped)   — FastAPI TestClient with db override injected
"""

import os

# Set required env vars BEFORE any application modules are imported.
# core/database/engine.py calls get_settings() at module level and creates
# an engine with pool_size/max_overflow — args that SQLite rejects.
# We point it at a dummy PostgreSQL URL (QueuePool, which accepts those args)
# so the module-level create_engine() succeeds without making a real connection.
# Tests override get_db with their own SQLite session so this engine is never used.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_dummy")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-ok")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-min-32-chars-ok!")

import uuid as _uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, StaticPool, create_engine, event
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session

# Register all ORM models with Base.metadata so that create_all() can resolve
# cross-table foreign keys (e.g. companies.owner_id → users.id).
import core.events.outbox  # noqa: E402, F401
import modules.accounting.models  # noqa: E402, F401
import modules.auth.models  # noqa: E402, F401
import modules.companies.models  # noqa: E402, F401
import modules.crm.models  # noqa: E402, F401
import modules.inventory.models  # noqa: E402, F401
import modules.platform_admin.models  # noqa: E402, F401
import modules.purchase.models  # noqa: E402, F401
import modules.sales.models  # noqa: E402, F401
import modules.users_roles.models  # noqa: E402, F401
from core.config.settings import Settings
from core.database.base import Base

# ---------------------------------------------------------------------------
# SQLite JSONB compatibility — JSONB is PostgreSQL-specific.
# Patch the SQLite type compiler to treat JSONB as TEXT so that
# Base.metadata.create_all() succeeds on SQLite test databases.
# ---------------------------------------------------------------------------
try:
    from sqlalchemy.dialects.postgresql import JSONB as _JSONB  # noqa: F401

    def _visit_jsonb(self, type_: object, **kw: object) -> str:  # type: ignore[override]
        return "TEXT"

    SQLiteTypeCompiler.visit_JSONB = _visit_jsonb  # type: ignore[attr-defined]
except ImportError:
    pass

try:
    from sqlalchemy.dialects.postgresql import INET as _INET  # noqa: F401

    def _visit_inet(self, type_: object, **kw: object) -> str:  # type: ignore[override]
        return "TEXT"

    SQLiteTypeCompiler.visit_INET = _visit_inet  # type: ignore[attr-defined]
except ImportError:
    pass

try:
    from sqlalchemy.dialects.postgresql import TSVECTOR as _TSVECTOR  # noqa: F401

    def _visit_tsvector(self, type_: object, **kw: object) -> str:  # type: ignore[override]
        return "TEXT"

    SQLiteTypeCompiler.visit_TSVECTOR = _visit_tsvector  # type: ignore[attr-defined]
except ImportError:
    pass

# NOTE: core.database.session (and its engine) must NOT be imported at module
# level here because engine.py calls create_engine() with PostgreSQL-specific
# pool args (pool_size, max_overflow) which SQLite rejects.  Import get_db
# lazily inside the test_client fixture instead.


def _add_sqlite_functions(dbapi_connection: object, _connection_record: object) -> None:
    """Register PostgreSQL-compatible functions for SQLite test sessions.

    ``gen_random_uuid()`` is used by BaseModel as a server-side default for
    the ``id`` column.  SQLite does not have this built-in, so we add a
    Python-backed implementation for the test engine only.
    """
    import sqlite3

    if isinstance(dbapi_connection, sqlite3.Connection):
        # Return 32-char hex (no dashes) to match how SQLAlchemy's Uuid(as_uuid=True)
        # stores and queries UUID values in SQLite (CHAR(32) without dashes).
        # str(uuid4()) returns 36 chars with dashes which does NOT match SELECT params.
        dbapi_connection.create_function(
            "gen_random_uuid", 0, lambda: _uuid.uuid4().hex
        )


# ---------------------------------------------------------------------------
# Test database URL — SQLite in-memory (no external DB required)
# ---------------------------------------------------------------------------
_TEST_DATABASE_URL = "sqlite:///:memory:"

# ---------------------------------------------------------------------------
# Test-only Argon2 parameters — TEST PERFORMANCE, not a security setting.
#
# Production Argon2 defaults (core/config/settings.py: ARGON2_TIME_COST=3,
# ARGON2_MEMORY_COST=65536, ARGON2_PARALLELISM=4) are OWASP-strength and
# deliberately expensive (~110ms hash / ~135ms verify measured on this
# environment). Every fixture that builds a `Settings()` for the test
# database/API (this file, tests/fixtures/auth_fixtures.py) previously
# inherited those PRODUCTION defaults, since `Settings` has no test-mode
# switch — so every one of the ~700+ create_test_user()/login() call sites
# across the suite paid the full production cost.
#
# These values are the CHEAPEST ones the shared `Settings` Pydantic model
# already permits — ARGON2_MEMORY_COST's field constraint is `ge=19456`
# ("OWASP minimum: 19456", see settings.py), so 19456 is not a relaxation
# of that floor, just the existing floor itself. No field constraint in
# settings.py is changed by this dict; it only supplies cheaper *values*
# through the same public constructor. Production defaults, the OWASP-
# minimum validation itself, and password verification logic
# (PasswordService) are all untouched — see tests/security/test_argon2_params.py,
# which deliberately does NOT use these overrides so it keeps validating
# the real production defaults.
# ---------------------------------------------------------------------------
_TEST_ARGON2_KWARGS: dict[str, int] = {
    "ARGON2_TIME_COST": 1,
    "ARGON2_MEMORY_COST": 19456,
    "ARGON2_PARALLELISM": 1,
}


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance configured for the test environment.

    Uses SQLite in-memory so no external database is required.
    The lru_cache on get_settings() is NOT used here so each test
    gets a fresh, predictable Settings object.
    """
    return Settings(
        DATABASE_URL=_TEST_DATABASE_URL,
        SECRET_KEY="test-secret-key-minimum-32-chars-ok",
        JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
        ENVIRONMENT="testing",
        DEBUG=False,
        LOG_LEVEL="WARNING",
        API_VERSION="1.0.0",
        **_TEST_ARGON2_KWARGS,
    )


@pytest.fixture(scope="session")
def test_db_engine() -> Generator[Engine, None, None]:
    """Session-scoped in-memory SQLite engine.

    Creates all tables once for the entire test session and drops them
    when the session ends.  StaticPool keeps the same in-memory database
    alive across multiple connections (required for SQLite in-memory).
    """
    engine = create_engine(
        _TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register SQLite-compatible replacements for PostgreSQL server functions.
    event.listen(engine, "connect", _add_sqlite_functions)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine: Engine) -> Generator[Session, None, None]:
    """Function-scoped SQLAlchemy session using the nested-transaction rollback pattern.

    The outer ``connection.begin()`` starts a real transaction that is rolled
    back at teardown, restoring the database to a pristine state.
    ``join_transaction_mode="create_savepoint"`` tells SQLAlchemy to issue
    SAVEPOINT / RELEASE SAVEPOINT for any ``session.commit()`` calls made by
    repository methods, so those commits are visible within the test but are
    undone by the outer rollback.  This works with both PostgreSQL and SQLite.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session: Session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with the database dependency overridden.

    Injects the test db_session so no external database is needed and
    each test's HTTP requests use the rolled-back session automatically.
    """
    from unittest.mock import patch

    from core.database.session import get_db
    from main import create_app

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app(
        Settings(
            DATABASE_URL=_TEST_DATABASE_URL,
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
            ENVIRONMENT="testing",
            DEBUG=True,
            # Use max expiry to survive WSL2 clock drift in CI/local environments.
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440,
            **_TEST_ARGON2_KWARGS,
        )
    )
    app.dependency_overrides[get_db] = override_get_db

    # Suppress Alembic migrations at startup — the test DB is already set up
    # by the test_db_engine fixture and SQLite doesn't use Alembic.
    # The patch must stay active for the whole TestClient lifetime because
    # startup events run inside TestClient.__enter__().
    with patch("main.run_migrations"):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Generic factory helpers (reusable across all modules)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Reset SlowAPI rate limiter storage before each test.

    The limiter in ``modules.auth.router`` is a module-level singleton whose
    in-memory counter storage persists across test functions in the same
    process.  This autouse fixture clears all counts so tests that send
    multiple requests to rate-limited endpoints (e.g. forgot-password with a
    limit of 3/15min) don't exhaust the quota and receive spurious 429s.
    """
    try:
        from modules.auth.router import limiter as _auth_limiter

        _auth_limiter.reset()
    except Exception:  # noqa: BLE001
        pass


def make_uuid() -> str:
    """Return a new UUID4 string — generic factory for test data."""
    import uuid

    return str(uuid.uuid4())


def make_utcnow() -> Any:
    """Return the current UTC datetime — generic factory for test data."""
    from core.utils.datetime import utcnow

    return utcnow()

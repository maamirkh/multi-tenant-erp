"""Shared real-Postgres fixtures for Epic 11 Phase 1 Saved Report View
tests (T046 Gate 1 requires a real-Postgres CRUD round-trip, JSONB
``filter_config`` included — SQLite cannot substitute).

Scoped to **this subdirectory only** (pytest conftest.py resolution is
directory-based): the parent ``tests/integration/api/v1/reports/``
directory's Phase 0 tests keep using the shared, SQLite-backed
``db_session`` from the root ``tests/conftest.py`` unaffected — mirrors
``tests/integration/api/v1/installments/conftest.py``'s identical
override technique, narrowed to just this one subdirectory instead of an
entire module's API test tree.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.config.settings import Settings
from core.database.session import get_db
from tests.conftest import _TEST_ARGON2_KWARGS
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest) -> Generator[Engine, None, None]:
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "076")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine: Engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Overrides the root ``test_client`` fixture with one real change: a
    concrete ``client=("127.0.0.1", ...)`` host. Starlette's ``TestClient``
    otherwise reports the fake host ``"testclient"`` as ``request.client.
    host``, which ``CompanyAuditLogRepository``'s real Postgres ``inet``
    column for ``ip_address`` correctly rejects as invalid (SQLite's
    untyped column silently accepted it — a genuine, pre-existing SQLite/
    Postgres test-double gap unrelated to Epic 11, first surfaced here
    because this is the first real-Postgres test to create a company via
    the actual HTTP signup flow rather than a bare UUID)."""
    from main import create_app

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app(
        Settings(
            DATABASE_URL="postgresql://test:test@localhost/test_dummy",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
            ENVIRONMENT="testing",
            DEBUG=True,
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440,
            **_TEST_ARGON2_KWARGS,
        )
    )
    app.dependency_overrides[get_db] = override_get_db

    with patch("main.run_migrations"):
        with TestClient(
            app, client=("127.0.0.1", 12345), raise_server_exceptions=False
        ) as client:
            yield client

    app.dependency_overrides.clear()

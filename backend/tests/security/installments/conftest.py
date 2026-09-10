"""Real-Postgres fixtures/builders for this directory's Phase 11 tests
that need schedule-backed contracts (T197/T199) — re-exported from
``tests/integration/api/v1/installments/conftest.py`` the same way
``tests/security/crm/conftest.py`` re-exports ``crm_client`` (T096).

Deliberately does NOT re-export ``db_session``/``pg_engine`` under their
original names: this directory's pre-existing files
(``test_contract_tenant_isolation.py``, ``test_cure_permission_isolation.py``,
``test_no_generic_status_setter.py``) use the root conftest's fast
SQLite-backed ``db_session`` and never touch schedule-line rows —
shadowing that name here would silently force every test in the
directory onto the slower, Docker-dependent, full-migration-replay
Postgres path for zero behavioural benefit. ``pg_db_session`` is a
distinctly-named fixture instead.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
    build_delinquency_service,
    build_rescheduling_service,
    build_settlement_service,
)
from tests.integration.api.v1.installments.conftest import pg_engine as _pg_engine
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

__all__ = [
    "build_active_contract_with_schedule",
    "build_collection_service",
    "build_contract_service",
    "build_delinquency_service",
    "build_rescheduling_service",
    "build_settlement_service",
    "pg_db_session",
    "installments_http_client",
]

pg_engine = _pg_engine

#: Same cheap Argon2 settings tests/conftest.py's own test_client/crm_client
#: fixtures use — not a security relaxation (see that file's own comment),
#: just avoiding paying full production hash cost at every login call below.
_TEST_ARGON2_KWARGS: dict[str, Any] = {
    "ARGON2_TIME_COST": 1,
    "ARGON2_MEMORY_COST": 19456,
    "ARGON2_PARALLELISM": 1,
}


@pytest.fixture
def pg_db_session(pg_engine) -> Generator[Session, None, None]:  # noqa: ANN001
    from sqlalchemy.orm import sessionmaker

    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def installments_http_client(
    pg_db_session: Session,
) -> Generator[TestClient, None, None]:
    """A real, fully-mounted ``main.create_app()`` FastAPI application —
    the actual ``api.v1.router`` assembly, unmodified, including the real
    ``installments_router``/``installments_admin_router`` mount from
    T190 — with ONLY ``get_db`` overridden to the real-Postgres
    ``pg_db_session`` (already migrated to head 071). No Installments-
    specific dependency is overridden (there is none to override — T190
    deliberately mounts with ``get_current_company_member`` only, no
    entitlement gate). This is the same construction
    ``tests/conftest.py``'s own ``test_client`` uses, just Postgres-backed
    instead of SQLite so schedule-dependent Installments endpoints work."""
    from unittest.mock import patch

    from core.config.settings import Settings
    from core.database.session import get_db
    from main import create_app

    def override_get_db() -> Generator[Session, None, None]:
        yield pg_db_session

    app = create_app(
        Settings(
            DATABASE_URL="postgresql://devsphere:changeme_dev_password@localhost:5432/devsphere_dev",
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
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client

    app.dependency_overrides.clear()

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

import pytest
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
]

pg_engine = _pg_engine


@pytest.fixture
def pg_db_session(pg_engine) -> Generator[Session, None, None]:  # noqa: ANN001
    from sqlalchemy.orm import sessionmaker

    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

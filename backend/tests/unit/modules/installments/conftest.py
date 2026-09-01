"""Real-Postgres fixture for the two Phase 12 tests in this directory
(T211/T212) that need schedule-backed contracts — re-exported from
``tests/integration/api/v1/installments/conftest.py``, the same
conftest.py re-export convention ``tests/security/installments/
conftest.py``/``tests/performance/installments/conftest.py`` already
establish.

Deliberately does NOT re-export ``db_session``/``pg_engine`` under
their original names: this directory holds many pre-existing, fast
SQLite-backed unit tests that never touch schedule-line rows —
shadowing ``db_session`` here would silently force all of them onto
the slower, Docker-dependent, full-migration-replay Postgres path for
zero behavioural benefit. ``pg_db_session`` is a distinctly-named
fixture instead.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from tests.integration.api.v1.installments.conftest import pg_engine as _pg_engine
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

__all__ = ["pg_db_session"]

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

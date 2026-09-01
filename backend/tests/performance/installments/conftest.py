"""Real-Postgres fixtures for this directory's Phase 12 performance test
(T213) — re-exported from
``tests/integration/api/v1/installments/conftest.py``, the same
conftest.py re-export convention ``tests/security/crm/conftest.py``/
``tests/security/installments/conftest.py`` already establish.

Schedule-line persistence requires real Postgres (``server_default=
text("now()")`` columns SQLite cannot resolve) — no pre-existing file in
this (empty, ``__init__.py``-only) directory to avoid shadowing, so
``db_session``/``pg_engine`` are re-exported under their original names
directly.
"""

from __future__ import annotations

from tests.integration.api.v1.installments.conftest import db_session, pg_engine
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

__all__ = ["db_session", "pg_engine"]

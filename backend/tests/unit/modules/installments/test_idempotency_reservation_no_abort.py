"""Real-Postgres test (tasks.md T092): the reservation
``INSERT...ON CONFLICT DO NOTHING`` statement never raises
``IntegrityError`` and never leaves the SQLAlchemy session in an aborted
state — subsequent statements in the same session succeed immediately
after a duplicate-reservation attempt.

**Placed under ``tests/unit/`` per the task's own specified path, but
uses a real Postgres connection** (via the same throwaway-database
fixtures used elsewhere in this module) rather than SQLite: the
production code under test calls ``sqlalchemy.dialects.postgresql.insert()``
with ``.on_conflict_do_nothing()``, a Postgres-specific construct that
does not compile under the SQLite dialect at all (plan.md §20.2's
explicit, deliberate choice — see ``idempotency_service.py``'s module
docstring). Testing this against SQLite would either crash for the
wrong reason or require dialect-agnostic production code contradicting
the approved design. This is a genuinely different, lighter-weight test
than T089-091's real two-session concurrency suite: everything here
happens sequentially within a single session.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from modules.installments.exceptions import InstallmentIdempotencyConflictError
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_session(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestReservationNeverAbortsSession:
    def test_duplicate_reservation_does_not_raise_or_abort_session(
        self, pg_session
    ) -> None:
        svc = InstallmentIdempotencyService(pg_session)
        company_id = uuid.uuid4()

        first = svc.reserve(company_id, "contract.activate", "key-1", "fingerprint-a")
        assert first.outcome == "RESERVED"
        svc.complete(first.reservation_id, {"ok": True})
        pg_session.commit()

        # Second attempt with the SAME key/fingerprint after A completed —
        # must not raise IntegrityError; must resolve as a clean REPLAY.
        second = svc.reserve(company_id, "contract.activate", "key-1", "fingerprint-a")
        assert second.outcome == "REPLAY"
        assert second.result_payload == {"ok": True}

        # The session must NOT be left in an aborted state — prove it by
        # successfully executing a completely unrelated subsequent
        # statement in the SAME session.
        third = svc.reserve(company_id, "contract.activate", "key-2", "fingerprint-b")
        assert third.outcome == "RESERVED"
        svc.complete(third.reservation_id, {"ok": True})
        pg_session.commit()

    def test_duplicate_with_mismatched_fingerprint_raises_cleanly(
        self, pg_session
    ) -> None:
        svc = InstallmentIdempotencyService(pg_session)
        company_id = uuid.uuid4()

        first = svc.reserve(company_id, "contract.cancel", "key-1", "fingerprint-a")
        svc.complete(first.reservation_id, {"ok": True})
        pg_session.commit()

        with pytest.raises(InstallmentIdempotencyConflictError) as exc_info:
            svc.reserve(company_id, "contract.cancel", "key-1", "fingerprint-DIFFERENT")
        assert exc_info.value.code == "IDEMPOTENCY_PAYLOAD_MISMATCH"

        # Session still usable afterwards, with NO recovery step (no
        # rollback/savepoint) — the raised exception is a clean
        # application-level error, not a DB-transaction abort.
        fresh = svc.reserve(company_id, "contract.cancel", "key-3", "fingerprint-c")
        assert fresh.outcome == "RESERVED"
        svc.complete(fresh.reservation_id, {"ok": True})
        pg_session.commit()

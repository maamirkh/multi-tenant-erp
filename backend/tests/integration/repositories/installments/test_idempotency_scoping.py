"""Real-Postgres repository test (tasks.md T093): idempotency keys are
scoped ``(company_id, operation, idempotency_key)`` — the same key
reused under a **different** ``company_id`` or **different**
``operation`` is treated as an independent key (tenant/operation
isolation).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

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
    alembic_upgrade(pg_url, "071")
    engine = db_engine(pg_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestIdempotencyKeyScoping:
    def test_same_key_different_company_is_independent(self, pg_session) -> None:
        svc = InstallmentIdempotencyService(pg_session)
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        key = "shared-key"

        result_a = svc.reserve(company_a, "contract.activate", key, "fingerprint")
        result_b = svc.reserve(company_b, "contract.activate", key, "fingerprint")

        assert result_a.outcome == "RESERVED"
        assert result_b.outcome == "RESERVED"
        assert result_a.reservation_id != result_b.reservation_id

    def test_same_key_different_operation_is_independent(self, pg_session) -> None:
        svc = InstallmentIdempotencyService(pg_session)
        company_id = uuid.uuid4()
        key = "shared-key"

        result_activate = svc.reserve(
            company_id, "contract.activate", key, "fingerprint"
        )
        result_cancel = svc.reserve(company_id, "contract.cancel", key, "fingerprint")

        assert result_activate.outcome == "RESERVED"
        assert result_cancel.outcome == "RESERVED"
        assert result_activate.reservation_id != result_cancel.reservation_id

    def test_same_key_same_company_same_operation_is_the_same_reservation(
        self, pg_session
    ) -> None:
        """Negative control: proves the scoping test above isn't
        vacuously true — an exact (company_id, operation, key) repeat
        does correctly collide (REPLAY after completion)."""
        svc = InstallmentIdempotencyService(pg_session)
        company_id = uuid.uuid4()

        first = svc.reserve(company_id, "contract.activate", "key-x", "fingerprint")
        svc.complete(first.reservation_id, {"ok": True})
        pg_session.commit()

        second = svc.reserve(company_id, "contract.activate", "key-x", "fingerprint")
        assert second.outcome == "REPLAY"
        assert second.reservation_id == first.reservation_id

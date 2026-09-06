"""Real-Postgres concurrency tests (tasks.md T089/T090/T091) for
``InstallmentIdempotencyService`` — the three normal-outcome scenarios
plan.md §20.3 requires to hold as direct consequences of PostgreSQL's
own MVCC/unique-index locking semantics, with zero application-level
locking, savepoints, or retry loops.

T089/T090/T091 share this one file and are explicitly NOT parallel-safe
with each other (tasks.md's own correction) — each test creates its own
independent ``company_id``/key so they remain correct if pytest ever
runs them out of declared order, but they are still sequenced here as
one coherent concurrency suite.
"""

from __future__ import annotations

import threading
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from modules.installments.exceptions import InstallmentIdempotencyConflictError
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


class TestConcurrentSameKeySamePayload:
    def test_a_wins_b_replays_after_a_commits(self, pg_engine) -> None:
        """T089: A wins the reservation; B's INSERT blocks at the DB
        level until A resolves; once A commits, B replays A's stored
        result — exactly one financial-adjacent effect occurred."""
        session_factory = sessionmaker(bind=pg_engine)
        session_a = session_factory()
        session_b = session_factory()
        company_id = uuid.uuid4()
        key = "activate-key-1"
        fingerprint = "same-fingerprint"

        # A reserves BEFORE the barrier so B's own INSERT (issued only
        # after both threads cross the barrier) genuinely races against
        # A's already-uncommitted row — never a real Python-level
        # deadlock risk, since only ONE barrier is used and nothing
        # after it waits on Python-level synchronization again (T053's
        # documented lesson: never place a barrier between a flush and
        # its commit for BOTH sides — here only A does that, B simply
        # blocks at the DB level afterward, which safely resolves on
        # its own once A commits or rolls back).
        barrier = threading.Barrier(2)
        results: dict[str, object] = {}

        def _worker_a() -> None:
            svc = InstallmentIdempotencyService(session_a)
            reservation = svc.reserve(company_id, "contract.activate", key, fingerprint)
            results["a_outcome"] = reservation.outcome
            barrier.wait()
            # Simulated business logic, then complete + commit.
            svc.complete(reservation.reservation_id, {"activated": True})
            session_a.commit()

        def _worker_b() -> None:
            barrier.wait()
            svc = InstallmentIdempotencyService(session_b)
            reservation = svc.reserve(company_id, "contract.activate", key, fingerprint)
            results["b_outcome"] = reservation.outcome
            results["b_payload"] = reservation.result_payload

        thread_a = threading.Thread(target=_worker_a)
        thread_b = threading.Thread(target=_worker_b)
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=15)
        thread_b.join(timeout=15)
        session_a.close()
        session_b.close()

        assert results["a_outcome"] == "RESERVED"
        assert results["b_outcome"] == "REPLAY"
        assert results["b_payload"] == {"activated": True}

        # Exactly one row exists for this key — verified with a fresh session.
        verify_session = session_factory()
        try:
            rows = (
                verify_session.execute(
                    select(InstallmentIdempotencyKey).where(
                        InstallmentIdempotencyKey.company_id == company_id,
                        InstallmentIdempotencyKey.operation == "contract.activate",
                        InstallmentIdempotencyKey.idempotency_key == key,
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].status == "COMPLETED"
        finally:
            verify_session.close()


class TestConcurrentSameKeyDifferentPayload:
    def test_b_receives_payload_mismatch_after_a_commits(self, pg_engine) -> None:
        """T090: B receives 409 IDEMPOTENCY_PAYLOAD_MISMATCH after A
        commits — never both proceed."""
        session_factory = sessionmaker(bind=pg_engine)
        session_a = session_factory()
        session_b = session_factory()
        company_id = uuid.uuid4()
        key = "activate-key-2"

        barrier = threading.Barrier(2)
        results: dict[str, object] = {}

        def _worker_a() -> None:
            svc = InstallmentIdempotencyService(session_a)
            reservation = svc.reserve(
                company_id, "contract.activate", key, "fingerprint-a"
            )
            results["a_outcome"] = reservation.outcome
            barrier.wait()
            svc.complete(reservation.reservation_id, {"activated": True})
            session_a.commit()

        def _worker_b() -> None:
            barrier.wait()
            svc = InstallmentIdempotencyService(session_b)
            try:
                svc.reserve(company_id, "contract.activate", key, "fingerprint-b")
                results["b_outcome"] = "UNEXPECTED_SUCCESS"
            except InstallmentIdempotencyConflictError as exc:
                results["b_outcome"] = "CONFLICT"
                results["b_code"] = exc.code

        thread_a = threading.Thread(target=_worker_a)
        thread_b = threading.Thread(target=_worker_b)
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=15)
        thread_b.join(timeout=15)
        session_a.close()
        session_b.close()

        assert results["a_outcome"] == "RESERVED"
        assert results["b_outcome"] == "CONFLICT"
        assert results["b_code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"


class TestFailedReservationNeverStranded:
    def test_retry_after_rollback_succeeds_fresh(self, pg_engine) -> None:
        """T091: the first request's business logic fails after
        reservation succeeds — the whole transaction (including the
        IN_PROGRESS row) rolls back; a retried request with the same key
        succeeds fresh, never permanently stranded."""
        session_factory = sessionmaker(bind=pg_engine)
        company_id = uuid.uuid4()
        key = "activate-key-3"

        session_first = session_factory()
        svc_first = InstallmentIdempotencyService(session_first)
        first_reservation = svc_first.reserve(
            company_id, "contract.activate", key, "fingerprint-a"
        )
        assert first_reservation.outcome == "RESERVED"

        # Simulate the business operation failing AFTER reservation
        # succeeded — the whole transaction rolls back, never reaching
        # complete()/commit().
        session_first.rollback()
        session_first.close()

        # A retried request with the SAME key must succeed fresh — not
        # REPLAY (nothing was ever completed) and not CONFLICT (the
        # failed row no longer exists).
        session_retry = session_factory()
        try:
            svc_retry = InstallmentIdempotencyService(session_retry)
            retried = svc_retry.reserve(
                company_id, "contract.activate", key, "fingerprint-a"
            )
            assert retried.outcome == "RESERVED"
            svc_retry.complete(retried.reservation_id, {"activated": True})
            session_retry.commit()
        finally:
            session_retry.close()

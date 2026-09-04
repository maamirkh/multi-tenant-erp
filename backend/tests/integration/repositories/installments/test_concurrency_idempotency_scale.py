"""[Epic 10, Phase 14, T241] Real-Postgres concurrency test — duplicate
idempotency-key submission under SUSTAINED concurrent load (20
concurrent identical requests). Exactly one financial effect — extends
Phase 5.5's ``test_idempotency_concurrency.py`` (T089's two-session
proof) to 20 simultaneous same-key/same-payload attempts, proving the
``INSERT ... ON CONFLICT DO NOTHING ... RETURNING`` reservation
mechanism resolves cleanly under real many-way contention, not merely a
single competing writer.

Mirrors T089's own documented precedent: "use a placeholder staged
write for this test, real financial workflows tested in later phases"
— the exactly-one-financial-effect proof here is against a placeholder
row insert performed only by the reservation winner inside the SAME
transaction as its `complete()` call, exactly modelling where a real
service method's business logic runs relative to reservation/
completion.
"""

from __future__ import annotations

import threading
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    pg_test_db,
)

_CONCURRENCY = 20


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "071")
    # Unlike this suite's other pg_engine fixtures (2-10 concurrent
    # sessions, comfortably inside the shared db_engine() helper's
    # default pool_size=5+max_overflow=10=15 connection ceiling), this
    # file genuinely needs 20 simultaneous connections — one per thread,
    # all held for the duration of each session's own transaction. A
    # bare db_engine(pg_url) here would starve the pool and surface as
    # a spurious QueuePool TimeoutError that looks like a correctness
    # failure but is actually just a test-harness capacity problem, not
    # anything about the idempotency mechanism under test.
    engine = sa.create_engine(pg_url, pool_size=_CONCURRENCY, max_overflow=0)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class TestConcurrentSameKeySamePayloadAtScale:
    def test_twenty_concurrent_identical_requests_exactly_one_financial_effect(
        self, pg_engine
    ) -> None:
        session_factory = sessionmaker(bind=pg_engine)
        company_id = uuid.uuid4()
        key = "activate-scale-key-1"
        fingerprint = "same-fingerprint"

        sessions = [session_factory() for _ in range(_CONCURRENCY)]
        # A wide barrier maximizes genuine simultaneous arrival at the
        # reservation INSERT across all 20 threads, rather than a
        # staggered sequence that would only re-prove the two-session
        # case 20 times over.
        barrier = threading.Barrier(_CONCURRENCY)
        results: dict[int, dict[str, object]] = {}

        def _worker(idx: int, session) -> None:
            svc = InstallmentIdempotencyService(session)
            barrier.wait()
            reservation = svc.reserve(company_id, "contract.activate", key, fingerprint)
            results[idx] = {"outcome": reservation.outcome}
            if reservation.outcome == "RESERVED":
                # Placeholder financial-adjacent effect, staged in the
                # SAME transaction as complete()+commit — mirrors where
                # a real service's business logic sits relative to
                # reservation/completion (T089's own documented
                # precedent for this exact substitution).
                session.execute(
                    InstallmentIdempotencyKey.__table__.update()
                    .where(InstallmentIdempotencyKey.id == reservation.reservation_id)
                    .values(contract_id=uuid.uuid4())
                )
                svc.complete(
                    reservation.reservation_id, {"activated": True, "winner": idx}
                )
                session.commit()
            else:
                results[idx]["payload"] = reservation.result_payload

        threads = [
            threading.Thread(target=_worker, args=(i, sessions[i]))
            for i in range(_CONCURRENCY)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        for s in sessions:
            s.close()

        outcomes = [results[i]["outcome"] for i in range(_CONCURRENCY)]
        assert (
            outcomes.count("RESERVED") == 1
        ), f"expected exactly 1 RESERVED winner out of {_CONCURRENCY}, got: {outcomes}"
        assert (
            outcomes.count("REPLAY") == _CONCURRENCY - 1
        ), f"expected exactly {_CONCURRENCY - 1} REPLAY outcomes, got: {outcomes}"

        winner_idx = next(
            i for i in range(_CONCURRENCY) if results[i]["outcome"] == "RESERVED"
        )
        for i in range(_CONCURRENCY):
            if i == winner_idx:
                continue
            assert results[i]["payload"] == {
                "activated": True,
                "winner": winner_idx,
            }, f"loser {i} did not replay the winner's exact stored result: {results[i]}"

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
            # Exactly one durable row — one financial-adjacent effect —
            # regardless of 20-way contention.
            assert len(rows) == 1, (
                f"expected exactly 1 idempotency key row after {_CONCURRENCY}-way "
                f"contention, found {len(rows)}"
            )
            assert rows[0].status == "COMPLETED"
            assert rows[0].result_payload == {"activated": True, "winner": winner_idx}
        finally:
            verify_session.close()

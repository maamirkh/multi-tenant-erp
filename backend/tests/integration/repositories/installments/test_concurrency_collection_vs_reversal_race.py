"""[Epic 10, Phase 14 — Exit Gate gap-closure, plan.md §19] Real-Postgres
concurrency test — collection vs. reversal race. Named explicitly in
plan.md §19's race table ("Same contract-row lock serializes both
operations against the same contract") but, like duplicate activation
(see this directory's sibling `test_concurrency_activation_race.py`),
not assigned its own dedicated race test by any earlier phase or by
tasks.md's literal T236-T241 enumeration. Added here for the same
reason: Phase 14's own Purpose ("closing any remaining gap") and Exit
Gate ("every critical race named in plan.md §19/§31") both require it.

Unlike the "exactly one wins" races (over-collection, double
settlement, ...), a collection and a reversal of a DIFFERENT, EARLIER
collection are not mutually exclusive business operations — both can
legitimately succeed, serialized one after the other by the shared
`FOR UPDATE` lock, with no conflict between them. The invariant under
test here is therefore not "exactly one succeeds" but "no lost update":
the contract's final, post-race state must reflect BOTH effects
correctly regardless of execution order — never a torn/overwritten
outcome where one operation's effect is silently dropped because it
read a stale pre-lock snapshot.

Design: seed ONE collection (contract now partially paid). Race a
SECOND, independent collection against a REVERSAL of the FIRST
collection. Whichever the lock admits first commits fully before the
second proceeds against the fresh state; the final outcome — net
collected amount, allocation-reference row count, contract status — is
identical regardless of which order actually occurred, which is exactly
what "no lost update" means operationally.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_REPETITIONS = 5


# See test_concurrency_collections_scale.py's identical comment: this
# directory has no local conftest.py, and the repo-root `db_session` is
# a different, SQLite-capable fixture — these shadow it with the real
# multi-connection Postgres pair the imported helpers require.
@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class TestCollectionVsReversalRaceAtScale:
    def test_five_repetitions_no_lost_update(self, db_session, pg_engine) -> None:
        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(_REPETITIONS):
            ctx = build_active_contract_with_schedule(
                db_session, installment_count=3, installment_amount=Decimal("100.00")
            )
            company_id = ctx["company_id"]
            contract_id = ctx["contract"].id
            bank_account_id = ctx["bank_account"].id

            # Seed: one collection of 100 up front (real service call,
            # committed before the race begins — the payment the
            # reversal thread below will reverse).
            seed_service = build_collection_service(db_session)
            seed_result = seed_service.record_collection(
                company_id,
                contract_id,
                amount=Decimal("100.00"),
                payment_method="BANK_TRANSFER",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=bank_account_id,
            )
            seeded_payment_id = uuid.UUID(seed_result["accounting_payment_id"])

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, tuple[str, object]] = {}

            def _second_collection(session) -> None:
                try:
                    service = build_collection_service(session)
                    result = service.record_collection(
                        company_id,
                        contract_id,
                        amount=Decimal("100.00"),
                        payment_method="BANK_TRANSFER",
                        idempotency_key=str(uuid.uuid4()),
                        actor_id=None,
                        bank_account_id=bank_account_id,
                    )
                    results["collection"] = ("success", result)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results["collection"] = ("error", exc)

            def _reversal(session) -> None:
                try:
                    service = build_collection_service(session)
                    result = service.reverse_collection(
                        company_id,
                        seeded_payment_id,
                        reason="Phase 14 concurrency test reversal",
                        idempotency_key=str(uuid.uuid4()),
                        actor_id=None,
                    )
                    results["reversal"] = ("success", result)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results["reversal"] = ("error", exc)

            thread_a = threading.Thread(target=_second_collection, args=(session_a,))
            thread_b = threading.Thread(target=_reversal, args=(session_b,))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=30)
            thread_b.join(timeout=30)
            session_a.close()
            session_b.close()

            # Both are legitimate, non-conflicting operations — the
            # shared FOR UPDATE lock serializes rather than rejects
            # either one; both must succeed.
            assert results["collection"][0] == "success", f"repetition {rep}: {results}"
            assert results["reversal"][0] == "success", f"repetition {rep}: {results}"

            # No-lost-update proof: regardless of execution order,
            # exactly 3 allocation-reference rows exist (the seeded
            # original, the second collection, the reversal of the
            # original) and the net collected amount is exactly 100
            # (100 seeded + 100 second collection - 100 reversed).
            verify_session = session_factory()
            try:
                all_refs = (
                    verify_session.execute(
                        select(InstallmentAllocationReference).where(
                            InstallmentAllocationReference.company_id == company_id,
                            InstallmentAllocationReference.contract_id == contract_id,
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(all_refs) == 3, (
                    f"repetition {rep}: expected exactly 3 allocation-reference rows "
                    f"(original + second collection + reversal), found {len(all_refs)} "
                    f"— a lost update would show fewer"
                )
                reversal_rows = [r for r in all_refs if r.is_reversal]
                original_rows = [r for r in all_refs if not r.is_reversal]
                assert len(reversal_rows) == 1, f"repetition {rep}"
                assert len(original_rows) == 2, f"repetition {rep}"
                assert reversal_rows[0].accounting_payment_id == seeded_payment_id

                net_collected = sum(
                    (r.allocated_amount if not r.is_reversal else -r.allocated_amount)
                    for r in all_refs
                )
                assert net_collected == Decimal("100.00"), (
                    f"repetition {rep}: expected net collected 100.00 "
                    f"(100 seeded + 100 second - 100 reversed), got {net_collected}"
                )
            finally:
                verify_session.close()

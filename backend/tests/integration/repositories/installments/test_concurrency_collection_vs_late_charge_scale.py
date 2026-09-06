"""[Epic 10, Phase 14, T238] Real-Postgres concurrency test — collection
vs. late-charge race, REPEATED AT SCALE. Extends Phase 8's
``test_concurrent_collection_vs_late_charge.py`` (a single race) to 10
independent repetitions, each against its own fresh contract — proving
the invariant (a contract is never observed COMPLETED while an open,
non-waived late-charge AR exists, Concurrency Test D, plan.md §31) holds
consistently under sustained/repeated contention, not merely as a
one-shot coincidence of one particular thread-scheduling outcome.

Two lock orderings are possible per repetition, both provably safe (see
the Phase 8 test's own docstring for the full reasoning): whichever of
``record_collection()``/``apply_late_charge()`` acquires the shared
``FOR UPDATE`` lock on ``InstallmentContract`` first determines whether
the late charge posts against a still-ACTIVE contract (leaving it
correctly ACTIVE post-collection) or loses cleanly against an
already-COMPLETED one. Running 10 independent repetitions exercises
both orderings across genuine OS thread-scheduling variance rather than
asserting only one hand-picked outcome.
"""

from __future__ import annotations

import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from modules.installments.exceptions import InstallmentActivationFailedError
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_delinquency_service,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}
_REPETITIONS = 10


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
def db_session(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class TestConcurrentCollectionVsLateChargeAtScale:
    def test_ten_repetitions_never_produce_a_torn_completion(
        self, db_session, pg_engine
    ) -> None:
        from sqlalchemy.orm import sessionmaker

        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(_REPETITIONS):
            ctx = build_active_contract_with_schedule(
                db_session,
                installment_count=1,
                installment_amount=Decimal("100.00"),
                late_charge_policy=_POLICY,
            )
            company_id = ctx["company_id"]
            contract_id = ctx["contract"].id
            bank_account_id = ctx["bank_account"].id
            line_id = ctx["schedule_lines"][0].id

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, tuple[str, object]] = {}

            def _collect(session) -> None:
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
                except Exception as exc:  # noqa: BLE001 — capturing for assertion
                    session.rollback()
                    results["collection"] = ("error", exc)

            def _apply_late_charge(session) -> None:
                try:
                    service = build_delinquency_service(session)
                    late_charge = service.apply_late_charge(
                        company_id, contract_id, line_id, actor_id=None
                    )
                    results["late_charge"] = ("success", late_charge)
                except Exception as exc:  # noqa: BLE001 — capturing for assertion
                    session.rollback()
                    results["late_charge"] = ("error", exc)

            thread_a = threading.Thread(target=_collect, args=(session_a,))
            thread_b = threading.Thread(target=_apply_late_charge, args=(session_b,))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=30)
            thread_b.join(timeout=30)
            session_a.close()
            session_b.close()

            collection_outcome, collection_payload = results["collection"]
            late_charge_outcome, late_charge_payload = results["late_charge"]

            assert collection_outcome == "success", f"repetition {rep}: {results}"
            contract_status_seen = collection_payload["contract_status"]

            if late_charge_outcome == "success":
                assert contract_status_seen == "ACTIVE", f"repetition {rep}: {results}"
            else:
                assert (
                    contract_status_seen == "COMPLETED"
                ), f"repetition {rep}: {results}"
                assert isinstance(
                    late_charge_payload, InstallmentActivationFailedError
                ), f"repetition {rep}: {results}"

            verify_session = session_factory()
            try:
                contract = verify_session.get(InstallmentContract, contract_id)
                if contract.status == "COMPLETED":
                    open_charges = [
                        charge
                        for charge in InstallmentLateChargeRepository(
                            verify_session
                        ).list_for_contract(company_id, contract_id)
                        if charge.waived_at is None
                    ]
                    assert open_charges == [], (
                        f"repetition {rep}: contract COMPLETED with an open, unwaived "
                        f"late charge still present: {open_charges}"
                    )
            finally:
                verify_session.close()

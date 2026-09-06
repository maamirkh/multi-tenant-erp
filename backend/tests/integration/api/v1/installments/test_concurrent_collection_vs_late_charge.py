"""[Epic 10, Phase 8, T153] Real-Postgres concurrency test — Concurrency
Test D (plan.md §31): a collection that zeros the schedule outstanding
races a concurrent late-charge post on the same contract. The shared
``FOR UPDATE`` lock on ``InstallmentContract`` (taken by both
``InstallmentCollectionService.record_collection()`` and
``InstallmentDelinquencyService.apply_late_charge()``) serializes the
two attempts — ``assert_zero_outstanding()`` never observes a torn
combination: a contract can only auto-complete if there truly is no
open late-charge AR at the instant the check runs, given a total
ordering of the two operations.

Two lock orderings are possible, both provably safe:

  * Collection wins the lock first: the late charge does not exist yet,
    so the collection zeroes the schedule and auto-completes
    (FR-INST-104); the late charge then loses against the now-COMPLETED
    contract (the documented servicing-status guard) — no late charge
    is ever created against a completed contract.
  * The late charge wins the lock first: it posts against the still-
    ACTIVE contract; the collection then sees the fresh late-charge AR
    as additional outstanding (plan.md §11.3) and — since it only pays
    the schedule amount — leaves the contract ACTIVE rather than
    torn-COMPLETED-with-an-open-obligation.

Either way, the invariant under test holds: a contract is never
observed COMPLETED while an open, non-waived late-charge AR exists.
"""

from __future__ import annotations

import threading
import uuid
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

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

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


class TestConcurrentCollectionVsLateCharge:
    def test_collection_and_late_charge_race_never_produce_a_torn_completion(
        self, db_session, pg_engine
    ) -> None:
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

        session_factory = sessionmaker(bind=pg_engine)
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

        assert collection_outcome == "success", results
        contract_status_seen = collection_payload["contract_status"]

        if late_charge_outcome == "success":
            # The late charge won the lock first: the collection only
            # pays off the schedule amount, so 25.00 of late-charge AR
            # remains outstanding — the contract must NOT have
            # auto-completed.
            assert contract_status_seen == "ACTIVE", results
        else:
            # The collection won the lock first and auto-completed the
            # contract before the late charge could be applied against
            # it — the late charge must have lost with the documented
            # servicing-status guard, never a generic/unexpected error.
            assert contract_status_seen == "COMPLETED", results
            assert isinstance(
                late_charge_payload, InstallmentActivationFailedError
            ), results

        # Authoritative invariant, independent of which ordering
        # occurred: never observe a COMPLETED contract with an open,
        # non-waived late-charge AR outstanding (the torn state
        # Concurrency Test D exists to rule out).
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
                    "contract COMPLETED with an open, unwaived late charge "
                    f"still present: {open_charges}"
                )
        finally:
            verify_session.close()

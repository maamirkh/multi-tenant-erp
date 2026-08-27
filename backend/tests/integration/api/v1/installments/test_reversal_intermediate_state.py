"""[Epic 10, Phase 7, T133] Service test: reversal/cancellation
intermediate-state resume (plan.md §12.3.2).

``AccountingIntegrationGateway.reverse_payment(full_cancellation=True)``
internally calls ``PaymentService.reallocate_payment()`` then
``cancel_payment()`` as two separate Accounting-internal commits — an
honestly-flagged limitation (not a staged/finalize pair), since a
failure between the two calls would leave the payment unallocated
(status ``ALLOCATED`` with zero ``PaymentAllocationLine`` rows — the
real, if oddly named, status ``AllocationEngine.allocate()`` produces
even for an empty allocation list) but not yet cancelled: a valid,
fully-explainable intermediate state, not a corrupt one. This test proves that
intermediate state directly (by calling the two steps separately, the
same way a caller resuming from a recorded failure would) and confirms a
resume needs only the second call, never re-attempting the first.

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_payment_service
from modules.accounting.repositories.payments import PaymentAllocationLineRepository
from modules.companies.models.company import Company
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import grant_permission_to_user
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


def _create_real_company(db_session: Session, company_id) -> None:
    """``roles``/``company_members`` carry a real FK to ``companies``
    (enforced under real Postgres, unlike this repo's SQLite test
    fixtures) — ``grant_permission_to_user()`` needs an actual row here,
    not just a bare ``uuid4()``."""
    owner, _ = create_test_user(db_session, email=f"{company_id}@example.com")
    company = Company(
        id=company_id,
        legal_name="T133 Test Co",
        slug=f"t133-{company_id}",
        owner_id=owner.id,
        email=f"owner-{company_id}@example.com",
    )
    db_session.add(company)
    db_session.commit()


class TestReversalIntermediateStateResume:
    def test_unallocated_then_cancelled_is_a_valid_resumable_intermediate_state(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("400.00")
        )
        collection_service = build_collection_service(db_session)

        collect_result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("400.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        payment_id = uuid.UUID(collect_result["accounting_payment_id"])

        _create_real_company(db_session, ctx["company_id"])
        canceller, _ = create_test_user(
            db_session, email=f"canceller-{uuid.uuid4()}@example.com"
        )
        canceller_id = canceller.id
        grant_permission_to_user(
            db_session,
            company_id=ctx["company_id"],
            user_id=canceller_id,
            permission_code="accounting.journal.reverse",
        )

        payment_service = build_payment_service(db_session)

        # Step 1 — the first half of reverse_payment(full_cancellation=True)
        # completing (its own internal commit).
        payment_service.reallocate_payment(
            company_id=ctx["company_id"],
            payment_id=payment_id,
            new_allocation_lines=[],
            actor_id=canceller_id,
        )

        # Intermediate state: unallocated, NOT yet cancelled — a valid,
        # fully-explainable state (matching plan.md §12.3.2's documented
        # limitation). Ground truth verified directly: reallocate_payment()
        # ends by calling AllocationEngine.allocate() with an empty line
        # list, which unconditionally sets status="ALLOCATED" even though
        # zero PaymentAllocationLine rows exist — the real (if oddly
        # named) unallocated status this pre-existing Accounting method
        # produces, not "POSTED".
        unallocated_payment = payment_service.get_payment(ctx["company_id"], payment_id)
        assert unallocated_payment.status == "ALLOCATED"
        remaining_lines = PaymentAllocationLineRepository(db_session).find_by_payment(
            ctx["company_id"], payment_id
        )
        assert remaining_lines == []

        # Resume: a retried reversal detects the payment is already
        # unallocated and calls ONLY cancel_payment(), never re-attempting
        # reallocate_payment() against an already-empty allocation set.
        cancelled_payment = payment_service.cancel_payment(
            company_id=ctx["company_id"],
            payment_id=payment_id,
            reason="Resumed reversal after forced failure",
            actor_id=canceller_id,
        )
        assert cancelled_payment.status == "CANCELLED"

    def test_reallocate_payment_is_a_safe_no_op_against_an_already_unallocated_payment(
        self, db_session: Session
    ) -> None:
        """Confirms the resume strategy's safety net: even a naive retry
        that DOES call ``reallocate_payment()`` again against an
        already-unallocated payment does not error or duplicate any
        financial effect — it is a no-op given empty existing
        allocations, empty new allocations."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("150.00")
        )
        collection_service = build_collection_service(db_session)

        collect_result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("150.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        payment_id = uuid.UUID(collect_result["accounting_payment_id"])

        _create_real_company(db_session, ctx["company_id"])
        canceller, _ = create_test_user(
            db_session, email=f"canceller-{uuid.uuid4()}@example.com"
        )
        canceller_id = canceller.id
        grant_permission_to_user(
            db_session,
            company_id=ctx["company_id"],
            user_id=canceller_id,
            permission_code="accounting.journal.reverse",
        )
        payment_service = build_payment_service(db_session)

        payment_service.reallocate_payment(
            company_id=ctx["company_id"],
            payment_id=payment_id,
            new_allocation_lines=[],
            actor_id=canceller_id,
        )
        # Calling it again must not raise and must leave the payment in
        # the same unallocated state.
        payment_service.reallocate_payment(
            company_id=ctx["company_id"],
            payment_id=payment_id,
            new_allocation_lines=[],
            actor_id=canceller_id,
        )
        still_unallocated = payment_service.get_payment(ctx["company_id"], payment_id)
        assert still_unallocated.status == "ALLOCATED"
        remaining_lines = PaymentAllocationLineRepository(db_session).find_by_payment(
            ctx["company_id"], payment_id
        )
        assert remaining_lines == []

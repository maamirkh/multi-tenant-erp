"""[Epic 10, Phase 10, T169] Service tests — InstallmentContractService.
cancel()'s free path, financial-activity (down-payment reversal) path,
and the "recorded ordinary collections block cancellation" guard.

Now idempotency-protected (one of the 8 approved high-risk commands) —
requires real Postgres (``ON CONFLICT DO NOTHING``), hence this file
replaces the SQLite-based cancel() coverage that used to live in
``tests/unit/modules/installments/test_lifecycle_transition_matrix.py``.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.models.payments import Payment, PaymentAllocationLine
from modules.installments.exceptions import (
    InstallmentCancellationNotAllowedError,
    InstallmentCancellationPaymentReferenceRequiredError,
    InstallmentIllegalTransitionError,
)
from modules.installments.models.contract import InstallmentContract
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
)


def _persist_pre_active_contract(db_session, status: str) -> tuple:
    """A DRAFT/PENDING_APPROVAL/APPROVED contract — no schedule, no
    Accounting activity — for the free-cancellation-path tests."""
    company_id = uuid.uuid4()
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-{uuid.uuid4().hex[:8]}",
        customer_id=uuid.uuid4(),
        sales_invoice_id=uuid.uuid4(),
        contract_date=date.today(),
        principal_amount=Decimal("900.00"),
        down_payment_amount=Decimal("0"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("900.00"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date.today(),
        maturity_date=date.today(),
        currency_code="USD",
        status=status,
        terms_snapshot={"note": "cancellation-service fixture"},
    )
    db_session.add(contract)
    db_session.commit()
    return company_id, contract


class TestCancelFreePath:
    @pytest.mark.parametrize(
        "starting_status", ["DRAFT", "PENDING_APPROVAL", "APPROVED"]
    )
    def test_cancel_succeeds_pre_activation(self, db_session, starting_status) -> None:
        company_id, contract = _persist_pre_active_contract(db_session, starting_status)
        svc = build_contract_service(db_session)

        updated = svc.cancel(
            company_id,
            contract.id,
            "Customer request",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        assert updated.status == "CANCELLED"
        assert updated.cancelled_at is not None

    def test_cancel_succeeds_active_with_zero_down_payment_and_no_collections(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(db_session)

        updated = svc.cancel(
            ctx["company_id"],
            ctx["contract"].id,
            "Customer request",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        assert updated.status == "CANCELLED"

    @pytest.mark.parametrize(
        "starting_status", ["COMPLETED", "CANCELLED", "WRITTEN_OFF"]
    )
    def test_cancel_rejected_from_terminal_statuses(
        self, db_session, starting_status
    ) -> None:
        company_id, contract = _persist_pre_active_contract(db_session, starting_status)
        svc = build_contract_service(db_session)

        with pytest.raises(InstallmentIllegalTransitionError):
            svc.cancel(
                company_id,
                contract.id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_cancel_commits_durably(self, db_session) -> None:
        company_id, contract = _persist_pre_active_contract(db_session, "DRAFT")
        svc = build_contract_service(db_session)
        svc.cancel(
            company_id,
            contract.id,
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        db_session.expire_all()
        refetched = (
            db_session.query(InstallmentContract).filter_by(id=contract.id).one()
        )
        assert refetched.status == "CANCELLED"

    def test_cancel_replay_with_same_key_returns_same_result(self, db_session) -> None:
        company_id, contract = _persist_pre_active_contract(db_session, "DRAFT")
        svc = build_contract_service(db_session)
        idem_key = str(uuid.uuid4())

        first = svc.cancel(
            company_id, contract.id, "reason", idempotency_key=idem_key, actor_id=None
        )
        second = svc.cancel(
            company_id, contract.id, "reason", idempotency_key=idem_key, actor_id=None
        )
        assert first.id == second.id
        assert first.status == second.status == "CANCELLED"


class TestCancelFinancialActivityPath:
    def test_cancel_reverses_the_down_payment_when_payment_id_supplied(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=2,
            installment_amount=Decimal("100.00"),
            down_payment_amount=Decimal("50.00"),
        )
        assert ctx["down_payment"] is not None
        svc = build_contract_service(db_session)

        updated = svc.cancel(
            ctx["company_id"],
            ctx["contract"].id,
            "Customer request",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            payment_id=ctx["down_payment"].id,
        )
        assert updated.status == "CANCELLED"
        assert updated.cancelled_at is not None

        # The down payment is un-allocated, not fully cancelled
        # (full_cancellation=False, matching reverse_collection()'s own
        # choice — full cancellation would additionally require the
        # actor to hold Accounting's own accounting.journal.reverse
        # permission, which an Installments-side actor cannot be
        # assumed to hold). Its allocation-line count, not its status
        # string, is the authoritative signal here: PaymentService.
        # reallocate_payment() sets status="POSTED" after reversing the
        # old lines, but its own trailing AllocationEngine.allocate()
        # call (even with an empty new_allocation_lines list) then
        # unconditionally sets status="ALLOCATED" again — pre-existing
        # Accounting behavior, already relied upon unremarked-upon by
        # Phase 7's reverse_collection() (identical call shape), not
        # something this phase introduces or should work around.
        refreshed_payment = (
            db_session.execute(
                select(Payment).where(Payment.id == ctx["down_payment"].id)
            )
            .scalars()
            .one()
        )
        assert refreshed_payment.status == "ALLOCATED"
        remaining_lines = (
            db_session.execute(
                select(PaymentAllocationLine).where(
                    PaymentAllocationLine.payment_id == ctx["down_payment"].id,
                    PaymentAllocationLine.is_deleted == False,  # noqa: E712
                )
            )
            .scalars()
            .all()
        )
        assert remaining_lines == []

    def test_cancel_rejects_active_down_payment_without_payment_id(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            down_payment_amount=Decimal("50.00"),
        )
        svc = build_contract_service(db_session)

        with pytest.raises(InstallmentCancellationPaymentReferenceRequiredError):
            svc.cancel(
                ctx["company_id"],
                ctx["contract"].id,
                "Customer request",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        db_session.rollback()
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "ACTIVE"

    def test_cancel_blocked_when_ordinary_collections_recorded(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        collection_service = build_collection_service(db_session)
        collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        svc = build_contract_service(db_session)
        with pytest.raises(InstallmentCancellationNotAllowedError):
            svc.cancel(
                ctx["company_id"],
                ctx["contract"].id,
                "Customer request",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        db_session.rollback()
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "ACTIVE"

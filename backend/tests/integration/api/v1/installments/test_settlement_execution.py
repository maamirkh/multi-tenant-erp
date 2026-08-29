"""[Epic 10, Phase 9, T161/T162] Service tests — settlement execution.

T161: settlement execution with 3+ remaining installments -> COMPLETED,
zero outstanding remains (spec Scenario F).

T162 [CORRECTED — Correction 6: removed incorrect [P] marker, same
implied file as T161]: a stale/expired settlement quote is rejected at
execution time, a new quote must be generated (spec §28 edge case) —
NOT parallel-safe with T161 (same file).

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from modules.installments.exceptions import (
    InstallmentIdempotencyConflictError,
    InstallmentSettlementNotAllowedError,
    InstallmentSettlementQuoteStaleError,
)
from modules.installments.models.contract import InstallmentContract
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_settlement_service,
)


class TestSettlementExecution:
    def test_settlement_with_three_remaining_installments_completes_contract(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = build_settlement_service(db_session)
        as_of = date.today()

        quote = service.generate_quote(ctx["company_id"], ctx["contract"].id, as_of)
        assert quote.settlement_amount == Decimal("300.00")

        contract = service.execute(
            ctx["company_id"],
            ctx["contract"].id,
            quote.settlement_amount,
            quote.as_of_date,
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            payment_method="BANK_TRANSFER",
            bank_account_id=ctx["bank_account"].id,
        )

        assert contract.status == "COMPLETED"
        assert contract.closed_at is not None

        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "COMPLETED"

        # Zero outstanding remains — re-quoting a COMPLETED/settled
        # contract yields nothing left to settle.
        outstanding = service._outstanding.compute_outstanding_breakdown(
            ctx["company_id"], ctx["contract"].id
        )
        assert outstanding.total_outstanding == Decimal("0")

    def test_settlement_execution_replay_returns_the_same_result(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("75.00")
        )
        service = build_settlement_service(db_session)
        as_of = date.today()
        quote = service.generate_quote(ctx["company_id"], ctx["contract"].id, as_of)
        idem_key = str(uuid.uuid4())

        first = service.execute(
            ctx["company_id"],
            ctx["contract"].id,
            quote.settlement_amount,
            quote.as_of_date,
            idempotency_key=idem_key,
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        second = service.execute(
            ctx["company_id"],
            ctx["contract"].id,
            quote.settlement_amount,
            quote.as_of_date,
            idempotency_key=idem_key,
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert first.id == second.id
        assert first.status == second.status == "COMPLETED"

    def test_reusing_the_key_for_a_different_settlement_request_is_a_conflict(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("75.00")
        )
        service = build_settlement_service(db_session)
        quote = service.generate_quote(
            ctx["company_id"], ctx["contract"].id, date.today()
        )
        idem_key = str(uuid.uuid4())

        service.execute(
            ctx["company_id"],
            ctx["contract"].id,
            quote.settlement_amount,
            quote.as_of_date,
            idempotency_key=idem_key,
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        # Same key, a different request (a different as_of_date changes
        # the fingerprint) — must be rejected as a conflict, never
        # silently reprocessed or silently replayed with a mismatched
        # payload (FR-INST-381).
        with pytest.raises(InstallmentIdempotencyConflictError) as exc_info:
            service.execute(
                ctx["company_id"],
                ctx["contract"].id,
                quote.settlement_amount,
                date(2020, 1, 1),
                idempotency_key=idem_key,
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )
        assert exc_info.value.code == "IDEMPOTENCY_PAYLOAD_MISMATCH"


class TestStaleSettlementQuoteRejected:
    def test_execution_rejects_a_stale_quote_after_intervening_collection(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = build_settlement_service(db_session)
        as_of = date.today()

        quote = service.generate_quote(ctx["company_id"], ctx["contract"].id, as_of)
        assert quote.settlement_amount == Decimal("300.00")

        # State changes since the quote was generated — an intervening
        # partial collection reduces the true live outstanding balance.
        collection_service = service._collections
        collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        with pytest.raises(InstallmentSettlementQuoteStaleError) as exc_info:
            service.execute(
                ctx["company_id"],
                ctx["contract"].id,
                quote.settlement_amount,
                quote.as_of_date,
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )
        assert exc_info.value.code == "SETTLEMENT_QUOTE_STALE"
        db_session.rollback()

        # The stale execution attempt must not have mutated the contract —
        # a fresh quote reflects only the intervening collection.
        fresh_quote = service.generate_quote(
            ctx["company_id"], ctx["contract"].id, date.today()
        )
        assert fresh_quote.settlement_amount == Decimal("200.00")

        # And executing against the FRESH quote succeeds.
        contract = service.execute(
            ctx["company_id"],
            ctx["contract"].id,
            fresh_quote.settlement_amount,
            fresh_quote.as_of_date,
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert contract.status == "COMPLETED"

    def test_execution_rejects_a_quote_amount_that_never_matched(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_settlement_service(db_session)

        with pytest.raises(InstallmentSettlementQuoteStaleError):
            service.execute(
                ctx["company_id"],
                ctx["contract"].id,
                Decimal("499.00"),
                date.today(),
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )
        db_session.rollback()

        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "ACTIVE"


class TestSettlementExecutionRejectedForNonSettleableStatus:
    def test_execute_rejects_a_draft_contract(self, db_session) -> None:
        company_id = uuid.uuid4()
        contract = InstallmentContract(
            company_id=company_id,
            contract_number=f"IC-{uuid.uuid4().hex[:8]}",
            customer_id=uuid.uuid4(),
            sales_invoice_id=uuid.uuid4(),
            contract_date=date.today(),
            principal_amount=Decimal("900.00"),
            down_payment_amount=Decimal("100.00"),
            markup_amount=Decimal("0"),
            contractual_total=Decimal("900.00"),
            installment_count=3,
            frequency="MONTHLY",
            first_due_date=date.today(),
            maturity_date=date.today(),
            currency_code="USD",
            status="DRAFT",
            terms_snapshot={"note": "settlement-not-allowed fixture"},
        )
        db_session.add(contract)
        db_session.commit()

        service = build_settlement_service(db_session)

        with pytest.raises(InstallmentSettlementNotAllowedError):
            service.execute(
                company_id,
                contract.id,
                Decimal("900.00"),
                date.today(),
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

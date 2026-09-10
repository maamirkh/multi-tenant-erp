"""Unit tests for AllocationEngine — Phase 10.

Tests (tasks.md T220):
  - Over-allocation raises AllocationExceedsOutstandingError
  - Partial allocation updates outstanding correctly (both the invoice and
    the payment's own paired credit transaction)
  - Realized FX gain calculated correctly (EUR invoice at rate 1.1 settled
    at 1.15 = gain) — the phase's own Independent Test
  - Concurrent allocation to the same invoice: two sequential calls must
    serialize correctly (SQLite does not enforce real row-level locking in
    tests, so this verifies business-level correctness of the SELECT FOR
    UPDATE code path rather than true concurrent-transaction blocking)

Spec ref: specs/008-accounting-finance/tasks.md T220
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_payment_service,
)
from modules.accounting.exceptions import AllocationExceedsOutstandingError
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.allocation_engine import AllocationEngine
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import PaymentService


@pytest.fixture
def setup(db_session: Session) -> dict[str, Any]:
    account_repo = AccountRepository(db_session)
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    company_id = uuid4()

    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank_account_repo = BankAccountRepository(db_session)
    bank = bank_account_repo.create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-0001",
            currency_code="USD",
            gl_account_id=bank_gl.id,
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    exchange_gain = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7100",
            account_name="Realized Exchange Gain",
            account_type="REVENUE",
        )
    )
    exchange_loss = account_repo.create(
        Account(
            company_id=company_id,
            account_code="8100",
            account_name="Realized Exchange Loss",
            account_type="EXPENSE",
        )
    )
    discount_allowed = account_repo.create(
        Account(
            company_id=company_id,
            account_code="8200",
            account_name="Discount Allowed",
            account_type="EXPENSE",
        )
    )

    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )

    config_repo = AccountingConfigurationRepository(db_session)
    config_repo.create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
            default_exchange_gain_account_id=exchange_gain.id,
            default_exchange_loss_account_id=exchange_loss.id,
        )
    )

    return {
        "company_id": company_id,
        "ar": ar,
        "bank": bank,
        "revenue": revenue,
        "exchange_gain": exchange_gain,
        "exchange_loss": exchange_loss,
        "discount_allowed": discount_allowed,
        "today": today,
    }


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


@pytest.fixture
def allocation_engine(db_session: Session) -> AllocationEngine:
    return build_allocation_engine(db_session)


def _make_invoice(
    db_session: Session,
    setup: dict[str, Any],
    amount_foreign: Decimal,
    exchange_rate: Decimal = Decimal("1"),
    currency_code: str = "USD",
) -> ARTransaction:
    ledger_repo = CustomerLedgerRepository(db_session)
    customer_id = uuid4()
    ledger = ledger_repo.create(
        CustomerLedger(company_id=setup["company_id"], customer_id=customer_id)
    )
    amount_base = amount_foreign * exchange_rate
    txn_repo = ARTransactionRepository(db_session)
    return txn_repo.create(
        ARTransaction(
            company_id=setup["company_id"],
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=setup["today"],
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=amount_foreign,
            amount_base=amount_base,
            outstanding_amount=amount_base,
            status="OPEN",
            invoice_number=f"INV-{uuid4().hex[:6]}",
        )
    )


class TestOverAllocation:
    def test_allocation_exceeding_invoice_outstanding_raises(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(payment_service.db, setup, Decimal("100.00"))
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("150.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        with pytest.raises(AllocationExceedsOutstandingError):
            payment_service.allocate_payment(
                company_id=setup["company_id"],
                payment_id=payment.id,
                allocation_lines=[
                    {"transaction_id": invoice.id, "amount_foreign": Decimal("150.00")}
                ],
                actor_id=None,
            )

    def test_allocation_exceeding_payment_balance_raises(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(payment_service.db, setup, Decimal("1000.00"))
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("100.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        with pytest.raises(AllocationExceedsOutstandingError):
            payment_service.allocate_payment(
                company_id=setup["company_id"],
                payment_id=payment.id,
                allocation_lines=[
                    {"transaction_id": invoice.id, "amount_foreign": Decimal("500.00")}
                ],
                actor_id=None,
            )


class TestPartialAllocation:
    def test_partial_allocation_updates_outstanding_correctly(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(payment_service.db, setup, Decimal("1000.00"))
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("400.00")}
            ],
            actor_id=None,
        )
        assert len(lines) == 1
        assert lines[0].allocated_amount_base == Decimal("400.00")

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice is not None
        assert refreshed_invoice.outstanding_amount == Decimal("600.00")
        assert refreshed_invoice.status == "PARTIALLY_PAID"

        credit_txn = ar_repo.find_by_source_document(
            company_id=setup["company_id"],
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        assert credit_txn is not None
        assert credit_txn.outstanding_amount == Decimal("-600.00")
        assert credit_txn.status == "PARTIALLY_PAID"

    def test_full_allocation_closes_invoice_and_payment(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(payment_service.db, setup, Decimal("700.00"))
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("700.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("700.00")}
            ],
            actor_id=None,
        )

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice is not None
        assert refreshed_invoice.outstanding_amount == Decimal("0")
        assert refreshed_invoice.status == "PAID"

        credit_txn = ar_repo.find_by_source_document(
            company_id=setup["company_id"],
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        assert credit_txn is not None
        assert credit_txn.outstanding_amount == Decimal("0")
        assert credit_txn.status == "PAID"


class TestRealizedFXGainLoss:
    def test_eur_invoice_at_1_1_settled_at_1_15_is_a_gain(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(
            payment_service.db,
            setup,
            amount_foreign=Decimal("1000.00"),
            exchange_rate=Decimal("1.10"),
            currency_code="EUR",
        )
        assert invoice.amount_base == Decimal("1100.00")

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="EUR",
            exchange_rate=Decimal("1.15"),
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        assert payment.amount_base == Decimal("1150.00")

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("1000.00")}
            ],
            actor_id=None,
        )
        assert lines[0].gain_loss_amount == Decimal("50.00")
        assert lines[0].gain_loss_journal_entry_id is not None

        from modules.accounting.repositories.gl import (
            GLReportRepository,
        )

        gl_reports = GLReportRepository(payment_service.db)
        gain_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["exchange_gain"].id
        )
        assert gain_balance["total_credit"] - gain_balance["total_debit"] == Decimal(
            "50.00"
        )

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice is not None
        assert refreshed_invoice.outstanding_amount == Decimal("0")
        assert refreshed_invoice.status == "PAID"

        # This test's fixture invoice was inserted directly via the repository
        # (no GL entry posted for it, unlike a real record_sales_invoice()
        # call), so AR-control only reflects the payment (CR 1150) and the
        # gain adjustment (DR 50) here. Net = -1100, exactly the invoice's
        # own booked value (1100) — proving that if the invoice's own DR AR
        # 1100 entry existed too, AR-control would net to zero, as required.
        ar_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["ar"].id
        )
        assert ar_balance["total_credit"] - ar_balance["total_debit"] == Decimal(
            "1100.00"
        )

    def test_eur_invoice_at_1_15_settled_at_1_10_is_a_loss(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(
            payment_service.db,
            setup,
            amount_foreign=Decimal("1000.00"),
            exchange_rate=Decimal("1.15"),
            currency_code="EUR",
        )
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="EUR",
            exchange_rate=Decimal("1.10"),
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("1000.00")}
            ],
            actor_id=None,
        )
        assert lines[0].gain_loss_amount == Decimal("-50.00")

        from modules.accounting.repositories.gl import GLReportRepository

        gl_reports = GLReportRepository(payment_service.db)
        loss_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["exchange_loss"].id
        )
        assert loss_balance["total_debit"] - loss_balance["total_credit"] == Decimal(
            "50.00"
        )


class TestDiscount:
    def test_discount_reduces_invoice_and_posts_to_discount_account(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(payment_service.db, setup, Decimal("1000.00"))
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("980.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {
                    "transaction_id": invoice.id,
                    "amount_foreign": Decimal("980.00"),
                    "discount_amount": Decimal("20.00"),
                    "discount_account_id": setup["discount_allowed"].id,
                }
            ],
            actor_id=None,
        )
        assert lines[0].discount_amount == Decimal("20.00")

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice is not None
        assert refreshed_invoice.outstanding_amount == Decimal("0")
        assert refreshed_invoice.status == "PAID"

        from modules.accounting.repositories.gl import GLReportRepository

        gl_reports = GLReportRepository(payment_service.db)
        discount_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["discount_allowed"].id
        )
        assert discount_balance["total_debit"] - discount_balance[
            "total_credit"
        ] == Decimal("20.00")


class TestSequentialAllocationSerializesCorrectly:
    """SQLite does not enforce SELECT FOR UPDATE row locking, so this
    verifies the business-level correctness of allocating to the same
    invoice across two sequential calls (each acquiring/releasing the lock
    query in turn) rather than true concurrent-transaction blocking, which
    would require a real PostgreSQL connection to exercise.
    """

    def test_two_sequential_allocations_to_same_invoice_do_not_overshoot(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        invoice = _make_invoice(payment_service.db, setup, Decimal("1000.00"))
        payment_a, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("600.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        payment_b, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("600.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment_a.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("600.00")}
            ],
            actor_id=None,
        )

        with pytest.raises(AllocationExceedsOutstandingError):
            payment_service.allocate_payment(
                company_id=setup["company_id"],
                payment_id=payment_b.id,
                allocation_lines=[
                    {"transaction_id": invoice.id, "amount_foreign": Decimal("600.00")}
                ],
                actor_id=None,
            )

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice is not None
        assert refreshed_invoice.outstanding_amount == Decimal("400.00")

"""Integration tests for Payment Processing — Phase 10.

Tests (tasks.md T222) — the phase's own Exit Criteria, literally:
  - Full Sales-to-Cash flow: invoice -> customer payment -> allocation ->
    invoice outstanding = 0 -> AR control account reconciles
  - Full Purchase-to-Pay flow: bill -> supplier payment -> allocation ->
    bill outstanding = 0 -> AP control account reconciles

Uses the REAL ``AccountsReceivableService.record_sales_invoice()`` /
``AccountsPayableService.record_supplier_bill()`` entry points (rather than
inserting ``ARTransaction``/``APTransaction`` rows directly, as the unit
tests do) so the invoice/bill's own GL entry genuinely exists, and
``reconcile_ar_control_account()``/``reconcile_ap_control_account()``
(Phase 6/7's financial-integrity backstops) can verify the subsidiary
ledger and GL agree after the full payment cycle.

Spec ref: specs/008-accounting-finance/tasks.md T222
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_ap_service,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.ap_service import AccountsPayableService
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import PaymentService
from tests.fixtures.users_roles_fixtures import grant_permission_to_user


@pytest.fixture
def setup(db_session: Session) -> dict:
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
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2000",
            account_name="AP",
            account_type="LIABILITY",
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
    expense = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5000",
            account_name="Expense",
            account_type="EXPENSE",
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
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-0001",
            currency_code="USD",
            gl_account_id=bank_gl.id,
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

    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_ap_account_id=ap.id,
            default_revenue_account_id=revenue.id,
            default_expense_account_id=expense.id,
        )
    )

    return {"company_id": company_id, "ar": ar, "ap": ap, "bank": bank, "today": today}


@pytest.fixture
def ar_service(db_session: Session) -> AccountsReceivableService:
    return build_ar_service(db_session)


@pytest.fixture
def ap_service(db_session: Session) -> AccountsPayableService:
    return build_ap_service(db_session)


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


class TestFullSalesToCashFlow:
    def test_invoice_payment_allocation_zeroes_outstanding_and_ar_reconciles(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-1001",
            total_amount=Decimal("1500.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )
        assert invoice.outstanding_amount == Decimal("1500.00")

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1500.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("1500.00")}
            ],
            actor_id=None,
        )

        from modules.accounting.repositories.ar import ARTransactionRepository

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice.outstanding_amount == Decimal("0")
        assert refreshed_invoice.status == "PAID"

        reconciled_balance = ar_service.reconcile_ar_control_account(
            setup["company_id"]
        )
        assert reconciled_balance == Decimal("0")

    def test_partial_payment_leaves_correct_outstanding_and_ar_still_reconciles(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-1002",
            total_amount=Decimal("2000.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("800.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("800.00")}
            ],
            actor_id=None,
        )

        from modules.accounting.repositories.ar import ARTransactionRepository

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice.outstanding_amount == Decimal("1200.00")
        assert refreshed_invoice.status == "PARTIALLY_PAID"

        reconciled_balance = ar_service.reconcile_ar_control_account(
            setup["company_id"]
        )
        assert reconciled_balance == Decimal("1200.00")


class TestFullPurchaseToPayFlow:
    def test_bill_payment_allocation_zeroes_outstanding_and_ap_reconciles(
        self,
        ap_service: AccountsPayableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        supplier_id = uuid4()
        bill, _ = ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-2001",
            total_amount=Decimal("900.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )
        assert bill.outstanding_amount == Decimal("900.00")

        payment, _ = payment_service.create_supplier_payment(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("900.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": bill.id, "amount_foreign": Decimal("900.00")}
            ],
            actor_id=None,
        )

        from modules.accounting.repositories.ap import APTransactionRepository

        ap_repo = APTransactionRepository(payment_service.db)
        refreshed_bill = ap_repo.get_by_id_or_none(
            id=bill.id, company_id=setup["company_id"]
        )
        assert refreshed_bill.outstanding_amount == Decimal("0")
        assert refreshed_bill.status == "PAID"

        reconciled_balance = ap_service.reconcile_ap_control_account(
            setup["company_id"]
        )
        assert reconciled_balance == Decimal("0")


class TestCancelAndRefund:
    def test_cancel_unallocated_payment_reverses_gl_and_closes_credit(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        payment, result = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("300.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        # Regression: cancel_payment() was fixed during the pre-Epic-9
        # hardening audit (2026-08-15) to require accounting.journal.reverse
        # when it reverses a posted payment's GL entry — the exact same
        # operation POST /journals/{id}/reverse already gated, which this
        # method previously bypassed entirely. actor_id=None (a system
        # actor) can never satisfy that, so a real, permitted actor is
        # required here.
        canceller_id = uuid4()
        grant_permission_to_user(
            payment_service.db,
            company_id=setup["company_id"],
            user_id=canceller_id,
            permission_code="accounting.journal.reverse",
        )
        cancelled = payment_service.cancel_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            reason="Duplicate entry",
            actor_id=canceller_id,
        )
        assert cancelled.status == "CANCELLED"

        from modules.accounting.repositories.gl import (
            GLReportRepository,
        )

        gl_reports = GLReportRepository(payment_service.db)
        ar_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["ar"].id
        )
        assert ar_balance["total_debit"] - ar_balance["total_credit"] == Decimal("0")

    def test_refund_of_overpayment_reduces_credit_balance(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-3001",
            total_amount=Decimal("500.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
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
                {"transaction_id": invoice.id, "amount_foreign": Decimal("500.00")}
            ],
            actor_id=None,
        )

        from modules.accounting.repositories.ar import ARTransactionRepository

        ar_repo = ARTransactionRepository(payment_service.db)
        credit_txn = ar_repo.find_by_source_document(
            company_id=setup["company_id"],
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        assert credit_txn.outstanding_amount == Decimal("-200.00")

        # Regression: process_refund() was fixed during the pre-Epic-9
        # hardening audit (2026-08-15) to require the same approve-tier
        # permission as approve_payment(), since it posts a brand-new,
        # immediately-finalized GL entry moving real cash. actor_id=None
        # (a system actor) can never satisfy that.
        refunder_id = uuid4()
        grant_permission_to_user(
            payment_service.db,
            company_id=setup["company_id"],
            user_id=refunder_id,
            permission_code="accounting.payment.customer.approve",
        )
        refund, _ = payment_service.process_refund(
            company_id=setup["company_id"],
            payment_id=payment.id,
            refund_date=setup["today"],
            amount=Decimal("200.00"),
            reason="Overpayment refund",
            bank_account_id=setup["bank"].id,
            actor_id=refunder_id,
        )
        assert refund.amount == Decimal("200.00")

        refreshed_credit = ar_repo.get_by_id_or_none(
            id=credit_txn.id, company_id=setup["company_id"]
        )
        assert refreshed_credit.outstanding_amount == Decimal("0")
        assert refreshed_credit.status == "PAID"


class TestReallocation:
    """T208's ``reallocate_payment()`` — "reverse prior + new allocation"
    (data-model.md §4.3: "Re-allocation: reverse and redo an incorrect
    allocation"). Added during Phase 10 final verification: this method had
    no prior test coverage.
    """

    def test_reallocate_to_a_different_invoice_restores_original_and_applies_new(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice_a, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-4001",
            total_amount=Decimal("600.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )
        invoice_b, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-4002",
            total_amount=Decimal("600.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("600.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice_a.id, "amount_foreign": Decimal("600.00")}
            ],
            actor_id=None,
        )

        from modules.accounting.repositories.ar import ARTransactionRepository

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_a = ar_repo.get_by_id_or_none(
            id=invoice_a.id, company_id=setup["company_id"]
        )
        assert refreshed_a.outstanding_amount == Decimal("0")
        assert refreshed_a.status == "PAID"

        new_lines = payment_service.reallocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            new_allocation_lines=[
                {"transaction_id": invoice_b.id, "amount_foreign": Decimal("600.00")}
            ],
            actor_id=None,
        )
        assert len(new_lines) == 1
        assert new_lines[0].ar_transaction_id == invoice_b.id

        refreshed_a_after = ar_repo.get_by_id_or_none(
            id=invoice_a.id, company_id=setup["company_id"]
        )
        assert refreshed_a_after.outstanding_amount == Decimal("600.00")
        assert refreshed_a_after.status == "OPEN"

        refreshed_b = ar_repo.get_by_id_or_none(
            id=invoice_b.id, company_id=setup["company_id"]
        )
        assert refreshed_b.outstanding_amount == Decimal("0")
        assert refreshed_b.status == "PAID"

        reconciled_balance = ar_service.reconcile_ar_control_account(
            setup["company_id"]
        )
        assert reconciled_balance == Decimal("600.00")


class TestUnallocatedPaymentsReport:
    """T219's ``list_unallocated_payments()`` — found broken during Phase
    10 final verification (discovered via a live smoke test against a real
    PostgreSQL database, not the SQLite test harness): once a payment
    receives ANY allocation, ``AllocationEngine.allocate()`` flips its
    ``status`` to ALLOCATED regardless of whether the allocation was
    partial. The original query filtered on ``status == "POSTED"`` only,
    so a payment with real remaining credit (e.g. an overpayment,
    spec.md 22.5) silently disappeared from the "unallocated payments"
    report the moment it received its first partial allocation.
    """

    def test_partially_allocated_payment_still_appears_as_unallocated(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-5001",
            total_amount=Decimal("50.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="CASH",
            payment_date=setup["today"],
            amount=Decimal("200.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        # Before any allocation: POSTED, must appear.
        unallocated_before = payment_service.list_unallocated_payments(
            setup["company_id"]
        )
        assert payment.id in {p.id for p in unallocated_before}

        # Partially allocate (50 of 200) — status flips to ALLOCATED, but
        # 150 of real credit remains; must still appear.
        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("50.00")}
            ],
            actor_id=None,
        )
        unallocated_after_partial = payment_service.list_unallocated_payments(
            setup["company_id"]
        )
        assert payment.id in {p.id for p in unallocated_after_partial}

    def test_fully_allocated_payment_does_not_appear_as_unallocated(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-5002",
            total_amount=Decimal("300.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=None,
            actor_id=None,
        )
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="CASH",
            payment_date=setup["today"],
            amount=Decimal("300.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("300.00")}
            ],
            actor_id=None,
        )

        unallocated = payment_service.list_unallocated_payments(setup["company_id"])
        assert payment.id not in {p.id for p in unallocated}

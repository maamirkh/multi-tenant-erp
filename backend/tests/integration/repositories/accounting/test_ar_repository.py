"""Integration tests for the AR subsidiary ledger — Phase 6.

Tests (tasks.md T153):
  - Recording a Sales invoice creates an ARTransaction and updates
    CustomerLedger.total_outstanding_base.
  - AR control account GL balance == CustomerLedger sum after posting
    (T140's reconciliation assertion, exercised here directly).
  - A subsequent credit note correctly reduces the outstanding balance and
    reconciliation still holds.
  - An adjustment posts to the GL and reconciles.
  - A write-off zeroes the transaction's outstanding amount and reconciles.

Full event-bus-triggered coverage (publish real Sales events through
``handle_sales_invoice_posted``/``handle_sales_credit_note_posted``) lives in
``test_integration_handlers.py`` (Phase 4/6) — this file exercises the AR
repository/service layer directly, plus the reconciliation backstop after
every posting type.

Spec ref: specs/008-accounting-finance/tasks.md T153, T140
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService


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
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    bad_debt = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6900",
            account_name="Bad Debt Expense",
            account_type="EXPENSE",
        )
    )
    rounding = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7900",
            account_name="Rounding",
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
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
            default_bad_debt_account_id=bad_debt.id,
        )
    )
    return {
        "company_id": company_id,
        "ar": ar,
        "revenue": revenue,
        "bad_debt": bad_debt,
        "rounding": rounding,
        "today": today,
    }


@pytest.fixture
def ar_service(db_session: Session) -> AccountsReceivableService:
    return build_ar_service(db_session, with_sales_sync=False)


class TestSalesInvoiceRecording:
    def test_record_invoice_creates_transaction_and_updates_ledger(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        transaction, result = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-1001",
            total_amount=Decimal("1000.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        assert transaction.status == "OPEN"
        assert transaction.outstanding_amount == Decimal("1000.00")
        assert result.journal_entry_id == transaction.journal_entry_id

        ledger = ar_service.get_customer_ledger(setup["company_id"], customer_id)
        assert ledger.total_outstanding_base == Decimal("1000.00")
        assert ledger.credit_status == "GOOD"

    def test_reconciliation_holds_after_invoice_posting(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            invoice_id=uuid4(),
            invoice_number="INV-1002",
            total_amount=Decimal("500.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("500.00")

    def test_reconciliation_holds_after_credit_note(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        invoice_id = uuid4()
        ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=invoice_id,
            invoice_number="INV-1003",
            total_amount=Decimal("800.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        ar_service.record_sales_credit_note(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=invoice_id,
            invoice_number="INV-1003",
            credit_amount=Decimal("300.00"),
            transaction_date=setup["today"],
            actor_id=None,
        )

        ledger = ar_service.get_customer_ledger(setup["company_id"], customer_id)
        assert ledger.total_outstanding_base == Decimal("500.00")

        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("500.00")

    def test_reconciliation_holds_after_adjustment(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-1004",
            total_amount=Decimal("1000.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        ar_service.adjust_receivable(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("-50.00"),
            contra_account_id=setup["rounding"].id,
            reason="Rounding adjustment",
            posting_date=setup["today"],
            actor_id=None,
        )

        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("950.00")

    def test_reconciliation_holds_after_write_off(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        transaction, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-1005",
            total_amount=Decimal("200.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        written_off = ar_service.confirm_write_off(
            company_id=setup["company_id"],
            ar_transaction_id=transaction.id,
            reason="Uncollectible",
            actor_id=None,
        )

        assert written_off.status == "WRITTEN_OFF"
        assert written_off.outstanding_amount == Decimal("0")

        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("0")

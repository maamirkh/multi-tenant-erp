"""Integration tests for the AP subsidiary ledger — Phase 7.

Tests (tasks.md T173):
  - Recording a supplier bill creates an APTransaction and updates
    SupplierLedger.total_outstanding_base.
  - AP control account GL balance == SupplierLedger sum after posting
    (T165's reconciliation assertion, exercised here directly).
  - A subsequent credit note correctly reduces the outstanding balance and
    reconciliation still holds.
  - An adjustment posts to the GL and reconciles.
  - Supplier statement reconciliation matches exact-amount statement lines
    against open bills and leaves unmatched items for manual follow-up.
  - AP aging bucket assignment via ``AccountsPayableService.get_supplier_aging()``.

No live Purchase event exists to publish (Phase 0 verification confirmed
Purchase has no Bill/AP entity at all — see ``handlers/integration_handlers.
py``'s module docstring) — this file exercises the AP service/repository
layer directly, exactly as the manual-entry API endpoints do.

Spec ref: specs/008-accounting-finance/tasks.md T173, T165
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ap_service
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
from modules.accounting.services.ap_service import AccountsPayableService
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
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2100",
            account_name="AP",
            account_type="LIABILITY",
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
            default_ap_account_id=ap.id,
            default_expense_account_id=expense.id,
        )
    )
    return {
        "company_id": company_id,
        "ap": ap,
        "expense": expense,
        "rounding": rounding,
        "today": today,
    }


@pytest.fixture
def ap_service(db_session: Session) -> AccountsPayableService:
    return build_ap_service(db_session)


class TestSupplierBillRecording:
    def test_record_bill_creates_transaction_and_updates_ledger(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        transaction, result = ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-1001",
            total_amount=Decimal("1000.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        assert transaction.status == "OPEN"
        assert transaction.outstanding_amount == Decimal("1000.00")
        assert result.journal_entry_id == transaction.journal_entry_id

        ledger = ap_service.get_supplier_ledger(setup["company_id"], supplier_id)
        assert ledger.total_outstanding_base == Decimal("1000.00")

    def test_reconciliation_holds_after_bill_posting(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=uuid4(),
            bill_id=uuid4(),
            bill_number="BILL-1002",
            total_amount=Decimal("500.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        balance = ap_service.reconcile_ap_control_account(setup["company_id"])
        assert balance == Decimal("500.00")

    def test_reconciliation_holds_after_credit_note(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        bill_id = uuid4()
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=bill_id,
            bill_number="BILL-1003",
            total_amount=Decimal("800.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        ap_service.record_supplier_credit_note(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=bill_id,
            bill_number="BILL-1003",
            credit_amount=Decimal("300.00"),
            transaction_date=setup["today"],
            actor_id=None,
        )

        ledger = ap_service.get_supplier_ledger(setup["company_id"], supplier_id)
        assert ledger.total_outstanding_base == Decimal("500.00")

        balance = ap_service.reconcile_ap_control_account(setup["company_id"])
        assert balance == Decimal("500.00")

    def test_reconciliation_holds_after_adjustment(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-1004",
            total_amount=Decimal("1000.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        ap_service.adjust_payable(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            amount=Decimal("-50.00"),
            contra_account_id=setup["rounding"].id,
            reason="Early payment discount",
            posting_date=setup["today"],
            actor_id=None,
        )

        balance = ap_service.reconcile_ap_control_account(setup["company_id"])
        assert balance == Decimal("950.00")


class TestSupplierStatementReconciliation:
    def test_matches_exact_amount_line_to_open_bill(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-2001",
            total_amount=Decimal("650.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        reconciliation = ap_service.reconcile_supplier_statement(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            statement_date=setup["today"],
            statement_total=Decimal("650.00"),
            statement_lines=[{"reference": "STMT-1", "amount": Decimal("650.00")}],
            actor_id=None,
        )

        assert reconciliation.status == "COMPLETED"
        items = ap_service.get_reconciliation_items(
            setup["company_id"], reconciliation.id
        )
        assert len(items) == 1
        assert items[0].match_status == "MATCHED"

    def test_unmatched_statement_line_and_unmatched_gl_bill_both_recorded(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-2002",
            total_amount=Decimal("400.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        reconciliation = ap_service.reconcile_supplier_statement(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            statement_date=setup["today"],
            statement_total=Decimal("999.00"),
            statement_lines=[{"reference": "STMT-X", "amount": Decimal("999.00")}],
            actor_id=None,
        )

        assert reconciliation.status == "IN_PROGRESS"
        items = ap_service.get_reconciliation_items(
            setup["company_id"], reconciliation.id
        )
        statuses = {item.match_status for item in items}
        assert statuses == {"UNMATCHED_STATEMENT", "UNMATCHED_GL"}


class TestAPAging:
    def test_bill_due_today_buckets_as_current(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-3001",
            total_amount=Decimal("300.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        row = ap_service.get_supplier_aging(
            setup["company_id"], supplier_id, setup["today"]
        )
        assert row is not None
        assert row.current == Decimal("300.00")

    def test_bill_31_days_overdue_buckets_as_31_60(
        self, ap_service: AccountsPayableService, setup: dict[str, Any]
    ) -> None:
        supplier_id = uuid4()
        due_date = setup["today"] - timedelta(days=31)
        ap_service.record_supplier_bill(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            bill_id=uuid4(),
            bill_number="BILL-3002",
            total_amount=Decimal("150.00"),
            currency_code="USD",
            transaction_date=due_date,
            due_date=due_date,
            actor_id=None,
        )
        row = ap_service.get_supplier_aging(
            setup["company_id"], supplier_id, setup["today"]
        )
        assert row is not None
        assert row.days_31_60 == Decimal("150.00")

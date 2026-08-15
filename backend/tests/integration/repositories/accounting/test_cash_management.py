"""Integration tests for Cash Management — Phase 9.

Tests (tasks.md T202) — the phase's own Independent Test, literally:
  - Create petty cash vouchers totalling £150 -> run replenishment ->
    verify GL entry: DR individual expense accounts / CR Bank = £150

Also covers cash receipts/payments (balance + GL posting), cash
reconciliation (short/over posting), and the double-replenishment guard.

Spec ref: specs/008-accounting-finance/tasks.md T202
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_cash_account_service
from modules.accounting.exceptions import (
    PettyCashVoucherNotFoundError,
    PostingValidationError,
    VoucherAlreadyReplenishedError,
)
from modules.accounting.models.coa import Account
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.cash_service import CashAccountService
from modules.accounting.services.fiscal_service import FiscalCalendarService


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
    till_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1010",
            account_name="Cash Till",
            account_type="ASSET",
        )
    )
    petty_cash_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1011",
            account_name="Petty Cash",
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
    revenue_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    travel_expense_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5100",
            account_name="Travel Expense",
            account_type="EXPENSE",
        )
    )
    office_expense_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5200",
            account_name="Office Supplies",
            account_type="EXPENSE",
        )
    )
    cash_short_over_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5900",
            account_name="Cash Short/Over",
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
    return {
        "company_id": company_id,
        "till_gl": till_gl,
        "petty_cash_gl": petty_cash_gl,
        "bank_gl": bank_gl,
        "revenue_gl": revenue_gl,
        "travel_expense_gl": travel_expense_gl,
        "office_expense_gl": office_expense_gl,
        "cash_short_over_gl": cash_short_over_gl,
        "today": today,
    }


@pytest.fixture
def cash_service(db_session: Session) -> CashAccountService:
    return build_cash_account_service(db_session)


@pytest.fixture
def gl_reports(db_session: Session) -> GLReportRepository:
    return GLReportRepository(db_session)


def _make_till(cash_service: CashAccountService, setup: dict):
    return cash_service.create_cash_account(
        company_id=setup["company_id"],
        account_name="Main Till",
        currency_code="USD",
        gl_account_id=setup["till_gl"].id,
    )


def _make_petty_cash_box(cash_service: CashAccountService, setup: dict):
    return cash_service.create_cash_account(
        company_id=setup["company_id"],
        account_name="Petty Cash Box 1",
        currency_code="USD",
        gl_account_id=setup["petty_cash_gl"].id,
        is_petty_cash=True,
        float_amount=Decimal("150.00"),
    )


class TestCashReceiptsAndPayments:
    def test_record_receipt_posts_balanced_journal_and_updates_balance(
        self,
        cash_service: CashAccountService,
        setup: dict,
        gl_reports: GLReportRepository,
    ) -> None:
        till = _make_till(cash_service, setup)

        transaction, result = cash_service.record_cash_receipt(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            amount=Decimal("200.00"),
            contra_account_id=setup["revenue_gl"].id,
            receipt_date=setup["today"],
            actor_id=None,
        )

        assert transaction.amount == Decimal("200.00")
        assert transaction.transaction_type == "RECEIPT"
        assert transaction.journal_entry_id == result.journal_entry_id

        refreshed = cash_service.get_cash_account(setup["company_id"], till.id)
        assert refreshed.current_balance == Decimal("200.00")

        balances = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["till_gl"].id
        )
        assert balances["total_debit"] - balances["total_credit"] == Decimal("200.00")

    def test_record_payment_posts_balanced_journal_and_updates_balance(
        self, cash_service: CashAccountService, setup: dict
    ) -> None:
        till = _make_till(cash_service, setup)
        cash_service.record_cash_receipt(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            amount=Decimal("500.00"),
            contra_account_id=setup["revenue_gl"].id,
            receipt_date=setup["today"],
            actor_id=None,
        )

        transaction, _ = cash_service.record_cash_payment(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            amount=Decimal("120.00"),
            contra_account_id=setup["travel_expense_gl"].id,
            payment_date=setup["today"],
            actor_id=None,
        )

        assert transaction.amount == Decimal("-120.00")
        refreshed = cash_service.get_cash_account(setup["company_id"], till.id)
        assert refreshed.current_balance == Decimal("380.00")

    def test_zero_amount_receipt_rejected(
        self, cash_service: CashAccountService, setup: dict
    ) -> None:
        till = _make_till(cash_service, setup)
        with pytest.raises(PostingValidationError):
            cash_service.record_cash_receipt(
                company_id=setup["company_id"],
                cash_account_id=till.id,
                amount=Decimal("0"),
                contra_account_id=setup["revenue_gl"].id,
                receipt_date=setup["today"],
                actor_id=None,
            )


class TestPettyCashReplenishment:
    def test_vouchers_totalling_150_replenish_creates_correct_gl_entry(
        self,
        cash_service: CashAccountService,
        setup: dict,
        gl_reports: GLReportRepository,
    ) -> None:
        box = _make_petty_cash_box(cash_service, setup)

        v1 = cash_service.create_petty_cash_voucher(
            company_id=setup["company_id"],
            cash_account_id=box.id,
            voucher_date=setup["today"],
            amount=Decimal("100.00"),
            expense_account_id=setup["travel_expense_gl"].id,
            recipient_name="Alice",
            purpose="Taxi fare",
            voucher_number="PCV-0001",
            actor_id=None,
        )
        v2 = cash_service.create_petty_cash_voucher(
            company_id=setup["company_id"],
            cash_account_id=box.id,
            voucher_date=setup["today"],
            amount=Decimal("50.00"),
            expense_account_id=setup["office_expense_gl"].id,
            recipient_name="Bob",
            purpose="Stationery",
            voucher_number="PCV-0002",
            actor_id=None,
        )
        assert v1.journal_entry_id is None
        assert v2.journal_entry_id is None

        transaction, vouchers, result = cash_service.replenish_petty_cash(
            company_id=setup["company_id"],
            cash_account_id=box.id,
            voucher_ids=[v1.id, v2.id],
            bank_gl_account_id=setup["bank_gl"].id,
            replenishment_date=setup["today"],
            actor_id=None,
        )

        assert transaction.amount == Decimal("150.00")
        assert all(v.journal_entry_id == result.journal_entry_id for v in vouchers)

        travel_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["travel_expense_gl"].id
        )
        assert travel_balance["total_debit"] - travel_balance[
            "total_credit"
        ] == Decimal("100.00")

        office_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["office_expense_gl"].id
        )
        assert office_balance["total_debit"] - office_balance[
            "total_credit"
        ] == Decimal("50.00")

        bank_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["bank_gl"].id
        )
        assert bank_balance["total_credit"] - bank_balance["total_debit"] == Decimal(
            "150.00"
        )

        refreshed_box = cash_service.get_cash_account(setup["company_id"], box.id)
        assert refreshed_box.current_balance == Decimal("150.00")

    def test_double_replenishment_of_same_voucher_raises(
        self, cash_service: CashAccountService, setup: dict
    ) -> None:
        box = _make_petty_cash_box(cash_service, setup)
        voucher = cash_service.create_petty_cash_voucher(
            company_id=setup["company_id"],
            cash_account_id=box.id,
            voucher_date=setup["today"],
            amount=Decimal("30.00"),
            expense_account_id=setup["travel_expense_gl"].id,
            recipient_name="Carol",
            purpose="Parking",
            voucher_number="PCV-0003",
            actor_id=None,
        )
        cash_service.replenish_petty_cash(
            company_id=setup["company_id"],
            cash_account_id=box.id,
            voucher_ids=[voucher.id],
            bank_gl_account_id=setup["bank_gl"].id,
            replenishment_date=setup["today"],
            actor_id=None,
        )

        with pytest.raises(VoucherAlreadyReplenishedError):
            cash_service.replenish_petty_cash(
                company_id=setup["company_id"],
                cash_account_id=box.id,
                voucher_ids=[voucher.id],
                bank_gl_account_id=setup["bank_gl"].id,
                replenishment_date=setup["today"],
                actor_id=None,
            )

    def test_replenish_with_unknown_voucher_raises_not_found(
        self, cash_service: CashAccountService, setup: dict
    ) -> None:
        box = _make_petty_cash_box(cash_service, setup)
        with pytest.raises(PettyCashVoucherNotFoundError):
            cash_service.replenish_petty_cash(
                company_id=setup["company_id"],
                cash_account_id=box.id,
                voucher_ids=[uuid4()],
                bank_gl_account_id=setup["bank_gl"].id,
                replenishment_date=setup["today"],
                actor_id=None,
            )


class TestCashReconciliation:
    def test_reconciliation_with_no_difference(
        self, cash_service: CashAccountService, setup: dict
    ) -> None:
        till = _make_till(cash_service, setup)
        cash_service.record_cash_receipt(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            amount=Decimal("300.00"),
            contra_account_id=setup["revenue_gl"].id,
            receipt_date=setup["today"],
            actor_id=None,
        )

        reconciliation = cash_service.reconcile_cash(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            reconciliation_date=setup["today"],
            physical_count_amount=Decimal("300.00"),
            actor_id=None,
        )
        assert reconciliation.difference == Decimal("0")
        assert reconciliation.status == "COMPLETED"
        assert reconciliation.journal_entry_id is None

    def test_reconciliation_overage_posts_to_short_over_account(
        self,
        cash_service: CashAccountService,
        setup: dict,
        gl_reports: GLReportRepository,
    ) -> None:
        till = _make_till(cash_service, setup)
        cash_service.record_cash_receipt(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            amount=Decimal("300.00"),
            contra_account_id=setup["revenue_gl"].id,
            receipt_date=setup["today"],
            actor_id=None,
        )

        reconciliation = cash_service.reconcile_cash(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            reconciliation_date=setup["today"],
            physical_count_amount=Decimal("310.00"),
            difference_account_id=setup["cash_short_over_gl"].id,
            actor_id=None,
        )
        assert reconciliation.difference == Decimal("10.00")
        assert reconciliation.journal_entry_id is not None

        till_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["till_gl"].id
        )
        assert till_balance["total_debit"] - till_balance["total_credit"] == Decimal(
            "310.00"
        )

        short_over_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["cash_short_over_gl"].id
        )
        assert short_over_balance["total_credit"] - short_over_balance[
            "total_debit"
        ] == Decimal("10.00")

        refreshed_till = cash_service.get_cash_account(setup["company_id"], till.id)
        assert refreshed_till.current_balance == Decimal("310.00")

    def test_reconciliation_shortage_requires_difference_account(
        self, cash_service: CashAccountService, setup: dict
    ) -> None:
        till = _make_till(cash_service, setup)
        cash_service.record_cash_receipt(
            company_id=setup["company_id"],
            cash_account_id=till.id,
            amount=Decimal("300.00"),
            contra_account_id=setup["revenue_gl"].id,
            receipt_date=setup["today"],
            actor_id=None,
        )

        with pytest.raises(PostingValidationError):
            cash_service.reconcile_cash(
                company_id=setup["company_id"],
                cash_account_id=till.id,
                reconciliation_date=setup["today"],
                physical_count_amount=Decimal("290.00"),
                actor_id=None,
            )

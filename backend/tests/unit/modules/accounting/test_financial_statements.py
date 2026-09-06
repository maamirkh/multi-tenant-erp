"""Unit tests for FinancialStatementService — Phase 12 (multi-currency) + Phase 13 (full suite).

Phase 12 (tasks.md T248):
  - Balance Sheet: Assets == Liabilities + Equity in the base currency, and
    every balance is scaled by the CLOSING rate when a report currency is
    requested.
  - P&L: net income scales by the AVERAGE rate when a report currency is
    requested.
  - Omitting ``report_currency`` (or requesting the base currency) leaves
    amounts untranslated.

Phase 13 (tasks.md T269) — the phase's own Independent Test, literally:
  - Post a known dataset (10 invoices, 5 expenses, 3 payments) -> Balance
    Sheet: Assets == Liabilities + Equity; P&L: net income matches the
    dataset's expected value.
  - Trial Balance: total debits == total credits.
  - P&L net income == Balance Sheet retained-earnings movement for the
    period (verified by actually posting a CLOSING entry, since this system
    has no automatic period-end close — see ``TestNetIncomeMatchesRetainedEarningsMovement``).
  - Cash Flow: the indirect-method total reconciles EXACTLY to the actual
    GL cash/bank balance change (a mathematical identity — see
    financial_statements.py's module docstring for the proof sketch).

Spec ref: specs/008-accounting-finance/tasks.md T248, T269
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_financial_statement_service,
    build_posting_engine,
)
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.currency_service import CurrencyService
from modules.accounting.services.financial_statements import FinancialStatementService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.posting_engine import PostingEngine


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

    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
            is_cash_account=True,
        )
    )
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
    equity = account_repo.create(
        Account(
            company_id=company_id,
            account_code="3000",
            account_name="Owner's Equity",
            account_type="EQUITY",
        )
    )
    retained_earnings = account_repo.create(
        Account(
            company_id=company_id,
            account_code="3100",
            account_name="Retained Earnings",
            account_type="EQUITY",
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

    today = date.today()
    fiscal_year = fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    periods = fiscal_service.list_periods(company_id, fiscal_year.id)
    period = next(p for p in periods if p.start_date <= today <= p.end_date)

    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(company_id=company_id, base_currency_code="USD")
    )

    return {
        "company_id": company_id,
        "cash": cash,
        "ar": ar,
        "ap": ap,
        "equity": equity,
        "retained_earnings": retained_earnings,
        "revenue": revenue,
        "expense": expense,
        "period": period,
        "today": today,
    }


@pytest.fixture
def posting_engine(db_session: Session) -> PostingEngine:
    return build_posting_engine(db_session)


@pytest.fixture
def service(db_session: Session) -> FinancialStatementService:
    return build_financial_statement_service(db_session)


@pytest.fixture
def currency_service(db_session: Session) -> CurrencyService:
    from modules.accounting.repositories.foundation import (
        CurrencyRepository,
        ExchangeRateRepository,
    )

    return CurrencyService(
        db=db_session,
        currency_repo=CurrencyRepository(db_session),
        exchange_rate_repo=ExchangeRateRepository(db_session),
    )


class TestBalanceSheet:
    def test_balance_sheet_balances_in_base_currency(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="OPENING_BALANCE",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("1000.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("1000.00"),
                },
            ],
            currency_code="USD",
        )

        report = service.get_balance_sheet(setup["company_id"], setup["today"])

        assert report["total_assets"] == Decimal("1000.00")
        assert report["total_liabilities"] == Decimal("0")
        assert report["total_equity"] == Decimal("1000.00")
        assert report["is_balanced"] is True
        assert report["report_currency"] == "USD"

    def test_balance_sheet_translates_using_closing_rate(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        currency_service: CurrencyService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="OPENING_BALANCE",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("1000.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("1000.00"),
                },
            ],
            currency_code="USD",
        )
        currency_service.set_exchange_rate(
            setup["company_id"],
            "USD",
            "EUR",
            setup["today"],
            Decimal("0.90"),
            rate_type="CLOSING",
        )

        report = service.get_balance_sheet(
            setup["company_id"], setup["today"], report_currency="EUR"
        )

        assert report["total_assets"] == Decimal("900.000")
        assert report["total_equity"] == Decimal("900.000")
        assert report["report_currency"] == "EUR"


class TestProfitAndLoss:
    def test_pl_translates_using_average_rate(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        currency_service: CurrencyService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("500.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("500.00"),
                },
            ],
            currency_code="USD",
        )
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["expense"].id,
                    "debit_amount": Decimal("200.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("200.00"),
                },
            ],
            currency_code="USD",
        )
        currency_service.set_exchange_rate(
            setup["company_id"],
            "USD",
            "GBP",
            setup["today"],
            Decimal("0.80"),
            rate_type="AVERAGE",
        )

        report_usd = service.get_pl(setup["company_id"], setup["today"], setup["today"])
        assert report_usd["total_revenue"] == Decimal("500.00")
        assert report_usd["total_expense"] == Decimal("200.00")
        assert report_usd["net_income"] == Decimal("300.00")

        report_gbp = service.get_pl(
            setup["company_id"], setup["today"], setup["today"], report_currency="GBP"
        )
        assert report_gbp["net_income"] == Decimal("240.000")
        assert report_gbp["report_currency"] == "GBP"


class TestKnownDataset:
    """Phase 13's own Independent Test, literally: 10 invoices, 5 expenses,
    3 payments -> Assets == Liabilities + Equity; net income matches.
    """

    def test_ten_invoices_five_expenses_three_payments(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        setup: dict,
    ) -> None:
        # Opening capital.
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="OPENING_BALANCE",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("5000.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("5000.00"),
                },
            ],
            currency_code="USD",
        )
        # 10 invoices: DR AR / CR Revenue, $100 each = $1000 revenue.
        for _ in range(10):
            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="STANDARD",
                posting_source="SALES",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": setup["ar"].id,
                        "debit_amount": Decimal("100.00"),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["revenue"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": Decimal("100.00"),
                    },
                ],
                currency_code="USD",
            )
        # 5 expenses: DR Expense / CR AP, $40 each = $200 expense.
        for _ in range(5):
            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="STANDARD",
                posting_source="PURCHASE",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": setup["expense"].id,
                        "debit_amount": Decimal("40.00"),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["ap"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": Decimal("40.00"),
                    },
                ],
                currency_code="USD",
            )
        # 3 payments: DR AP / CR Cash, $40 each = $120 paid off.
        for _ in range(3):
            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="STANDARD",
                posting_source="PAYMENT",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": setup["ap"].id,
                        "debit_amount": Decimal("40.00"),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["cash"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": Decimal("40.00"),
                    },
                ],
                currency_code="USD",
            )

        pl = service.get_pl(setup["company_id"], setup["today"], setup["today"])
        assert pl["total_revenue"] == Decimal("1000.00")
        assert pl["total_expense"] == Decimal("200.00")
        assert pl["net_income"] == Decimal("800.00")

        bs = service.get_balance_sheet(setup["company_id"], setup["today"])
        assert bs["total_assets"] == bs["total_liabilities"] + bs["total_equity"]
        assert bs["is_balanced"] is True
        # Cash: 5000 - 120 = 4880; AR: 1000; total assets = 5880.
        assert bs["total_assets"] == Decimal("5880.00")
        # AP: 200 - 120 = 80.
        assert bs["total_liabilities"] == Decimal("80.00")
        # Equity: 5000 contributed capital + 800 unclosed net income
        # (Current Year Earnings — no CLOSING entry was posted in this test).
        assert bs["total_equity"] == Decimal("5800.00")


class TestTrialBalance:
    def test_trial_balance_debits_equal_credits(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("300.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("300.00"),
                },
            ],
            currency_code="USD",
        )

        report = service.get_trial_balance(setup["company_id"], setup["period"].id)

        assert report["total_debit"] == report["total_credit"]
        assert report["is_balanced"] is True
        assert report["total_debit"] == Decimal("300.00")

    def test_trial_balance_with_comparative_period(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("50.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("50.00"),
                },
            ],
            currency_code="USD",
        )

        report = service.get_trial_balance(
            setup["company_id"],
            setup["period"].id,
            comparative_period_id=setup["period"].id,
        )

        assert "comparative" in report
        assert report["comparative"]["total_debit"] == report["total_debit"]
        assert report["comparative"]["is_balanced"] is True


class TestNetIncomeMatchesRetainedEarningsMovement:
    """T269's fourth assertion, verified the honest way: this system has no
    automatic period-end close, so a CLOSING entry is posted explicitly
    (mirroring what a real close would do — zero revenue/expense into
    Retained Earnings) and the two independently-computed numbers are
    checked against each other.
    """

    def test_pl_net_income_equals_retained_earnings_movement(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("700.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("700.00"),
                },
            ],
            currency_code="USD",
        )
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["expense"].id,
                    "debit_amount": Decimal("250.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("250.00"),
                },
            ],
            currency_code="USD",
        )

        pl = service.get_pl(setup["company_id"], setup["today"], setup["today"])
        assert pl["net_income"] == Decimal("450.00")

        re_balance_before = GLReportRepository(posting_engine.db).account_balance_query(
            company_id=setup["company_id"], account_id=setup["retained_earnings"].id
        )
        re_before = re_balance_before["total_credit"] - re_balance_before["total_debit"]

        # Manual close: DR Revenue 700 / CR Expense 250 / CR Retained Earnings 450.
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="CLOSING",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("700.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["expense"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("250.00"),
                },
                {
                    "account_id": setup["retained_earnings"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("450.00"),
                },
            ],
            currency_code="USD",
        )

        re_balance_after = GLReportRepository(posting_engine.db).account_balance_query(
            company_id=setup["company_id"], account_id=setup["retained_earnings"].id
        )
        re_after = re_balance_after["total_credit"] - re_balance_after["total_debit"]

        assert (re_after - re_before) == pl["net_income"]


class TestCashFlow:
    def test_cash_flow_reconciles_to_actual_gl_cash_balance(
        self,
        posting_engine: PostingEngine,
        service: FinancialStatementService,
        setup: dict,
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="OPENING_BALANCE",
            posting_source="MANUAL",
            posting_date=setup["today"] - timedelta(days=10),
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("1000.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("1000.00"),
                },
            ],
            currency_code="USD",
        )
        # Revenue in cash.
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="SALES",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("500.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("500.00"),
                },
            ],
            currency_code="USD",
        )
        # Expense paid in cash.
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["expense"].id,
                    "debit_amount": Decimal("150.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("150.00"),
                },
            ],
            currency_code="USD",
        )
        # Sale on credit (non-cash working capital movement: AR increases).
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="SALES",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["ar"].id,
                    "debit_amount": Decimal("300.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("300.00"),
                },
            ],
            currency_code="USD",
        )
        # Owner injects more capital directly into cash (a "financing" event
        # with no dedicated Account classification in this data model —
        # exactly the case the module docstring calls out).
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("200.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("200.00"),
                },
            ],
            currency_code="USD",
        )

        report = service.get_cash_flow(
            setup["company_id"], setup["today"] - timedelta(days=1), setup["today"]
        )

        assert report["reconciles"] is True
        assert (
            report["net_cash_from_operating_activities"] == report["net_change_in_cash"]
        )
        # Direct GL truth: 500 (cash sale) - 150 (cash expense) + 200 (capital) = 550.
        assert report["net_change_in_cash"] == Decimal("550.00")
        assert report["closing_cash_balance"] - report[
            "opening_cash_balance"
        ] == Decimal("550.00")

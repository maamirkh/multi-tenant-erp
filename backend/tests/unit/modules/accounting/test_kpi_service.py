"""Unit tests for FinancialKPIService — Phase 15 (tasks.md T286, T292).

Independent Test (tasks.md Phase 15): a fully known dataset posted through
``PostingEngine`` plus matching AR/AP subsidiary-ledger records, then every
one of the 15 KPIs is asserted against a value computed by hand (documented
in the module docstring's arithmetic below and cross-checked against
``FinancialStatementService`` where the two overlap, e.g. Operating Cash
Flow's mathematical identity — see financial_statements.py).

Dataset (all dated within fiscal year 2026; ``AS_OF = 2026-06-15``):
  2026-01-01  DR Cash 10,000            / CR Equity 10,000       (opening)
  2026-06-01  DR AR 500                 / CR Revenue 500          (invoice)
  2026-06-01  DR Cash 80                / CR TaxPayable 80        (tax collected)
  2026-06-03  DR Inventory 300          / CR AP 300                (purchase)
  2026-06-05  DR COGS 200               / CR Inventory 200         (cost of sale)
  2026-06-10  DR OtherExpense 50        / CR Cash 50                (opex paid cash)

AR subsidiary: 300 not-yet-due + 200 overdue (31-60d bucket) = 500 total, 40% overdue.
AP subsidiary: 180 not-yet-due + 120 overdue (31-60d bucket) = 300 total, 40% overdue.
Both AR/AP transactions carry ``transaction_date`` in June, so the prior-period
(2026-05-15) snapshot correctly sees none of them (spec.md §18.3 aging is
computed from currently-open transactions filtered by transaction_date, not a
retroactive point-in-time reconstruction).

As of AS_OF (2026-06-15):
  Cash = 10,000 - 50 + 80 = 10,030;  AR = 500;  Inventory = 300 - 200 = 100
  Current Assets (CUR-AST) = 10,630;  AP = 300;  TaxPayable = 80
  Current Liabilities (CUR-LIA) = 380
  Current Ratio = 10630/380;  Quick Ratio = (10630-100)/380 = 10530/380
  Revenue MTD = 500; COGS MTD = 200; Gross Profit = 300 -> Gross Margin 60%
  Total Expense MTD = COGS(200)+OtherExpense(50) = 250; Net Income = 250 -> Net Margin 50%
  days_elapsed (June 1-15 inclusive) = 15
  DSO = (500/500)*15 = 15;  DPO = (300/200)*15 = 22.5
  Operating Cash Flow (June): net_income 250 + WC adjustment (-500 AR, -100
  Inventory, +300 AP, +80 TaxPayable = -220) = 30 -- verified against the
  direct cash movement: -50 (opex) + 80 (tax) = +30.
  Tax Liability Balance = 80 (single credit posting, no prior debits)

As of the prior comparison date (2026-05-15, only the Jan 1 opening entry has
posted): Cash = 10,000; everything else = 0.

Spec ref: specs/008-accounting-finance/spec.md §40 KPI Requirements
Tasks ref: specs/008-accounting-finance/tasks.md T286, T292
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_kpi_service, build_posting_engine
from modules.accounting.models.ap import APTransaction, SupplierLedger
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.tax import TaxCode
from modules.accounting.repositories.ap import (
    APTransactionRepository,
    SupplierLedgerRepository,
)
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.repositories.tax import TaxCodeRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.kpi_service import FinancialKPIService
from modules.accounting.services.posting_engine import PostingEngine

AS_OF = date(2026, 6, 15)


@pytest.fixture
def base_setup(db_session: Session) -> dict[str, Any]:
    account_repo = AccountRepository(db_session)
    group_repo = AccountGroupRepository(db_session)
    company_id = uuid4()

    cur_ast = group_repo.create(
        AccountGroup(
            company_id=company_id,
            group_code="CUR-AST",
            group_name="Current Assets",
            account_type="ASSET",
        )
    )
    cur_lia = group_repo.create(
        AccountGroup(
            company_id=company_id,
            group_code="CUR-LIA",
            group_name="Current Liabilities",
            account_type="LIABILITY",
        )
    )
    cogs_group = group_repo.create(
        AccountGroup(
            company_id=company_id,
            group_code="COGS",
            group_name="Cost of Goods Sold",
            account_type="EXPENSE",
        )
    )

    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
            account_group_id=cur_ast.id,
            is_cash_account=True,
        )
    )
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="Accounts Receivable",
            account_type="ASSET",
            account_group_id=cur_ast.id,
        )
    )
    inventory = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1300",
            account_name="Merchandise Inventory",
            account_type="ASSET",
            account_group_id=cur_ast.id,
        )
    )
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2000",
            account_name="Accounts Payable",
            account_type="LIABILITY",
            account_group_id=cur_lia.id,
        )
    )
    tax_payable = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2100",
            account_name="Tax Payable",
            account_type="LIABILITY",
            account_group_id=cur_lia.id,
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
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    cogs = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5000",
            account_name="Cost of Goods Sold",
            account_type="EXPENSE",
            account_group_id=cogs_group.id,
        )
    )
    other_expense = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6000",
            account_name="Other Operating Expense",
            account_type="EXPENSE",
        )
    )

    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    fiscal_service.create_fiscal_year(
        company_id,
        "FY-2026",
        date(2026, 1, 1),
        date(2026, 12, 31),
        "USD",
        is_current=True,
    )

    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(company_id=company_id, base_currency_code="USD")
    )

    tax_code = TaxCodeRepository(db_session).create(
        TaxCode(
            company_id=company_id,
            tax_code="VAT-STD",
            tax_name="Standard VAT",
            tax_type="VAT",
            applicability="SALES",
            gl_account_id=tax_payable.id,
            is_input_tax_recoverable=False,
        )
    )

    return {
        "company_id": company_id,
        "cash": cash,
        "ar": ar,
        "inventory": inventory,
        "ap": ap,
        "tax_payable": tax_payable,
        "equity": equity,
        "revenue": revenue,
        "cogs": cogs,
        "other_expense": other_expense,
        "tax_code": tax_code,
    }


@pytest.fixture
def setup(db_session: Session, base_setup: dict[str, Any]) -> dict[str, Any]:
    """``base_setup`` plus the AR/AP subsidiary-ledger records the known-
    dataset test needs. Kept separate so ``TestZeroDenominatorSafety`` can
    depend on ``base_setup`` alone and get a genuinely empty ledger.
    """
    company_id = base_setup["company_id"]
    customer_id = uuid4()
    customer_ledger = CustomerLedgerRepository(db_session).create(
        CustomerLedger(company_id=company_id, customer_id=customer_id)
    )
    ar_txn_repo = ARTransactionRepository(db_session)
    ar_txn_repo.create(
        ARTransaction(
            company_id=company_id,
            customer_ledger_id=customer_ledger.id,
            transaction_type="INVOICE",
            transaction_date=date(2026, 6, 1),
            due_date=date(2026, 6, 25),
            currency_code="USD",
            exchange_rate=Decimal("1"),
            amount_foreign=Decimal("300.00"),
            amount_base=Decimal("300.00"),
            outstanding_amount=Decimal("300.00"),
            status="OPEN",
            invoice_number="INV-KPI-001",
        )
    )
    ar_txn_repo.create(
        ARTransaction(
            company_id=company_id,
            customer_ledger_id=customer_ledger.id,
            transaction_type="INVOICE",
            transaction_date=date(2026, 6, 1),
            due_date=date(2026, 5, 6),
            currency_code="USD",
            exchange_rate=Decimal("1"),
            amount_foreign=Decimal("200.00"),
            amount_base=Decimal("200.00"),
            outstanding_amount=Decimal("200.00"),
            status="OPEN",
            invoice_number="INV-KPI-002",
        )
    )

    supplier_id = uuid4()
    supplier_ledger = SupplierLedgerRepository(db_session).create(
        SupplierLedger(company_id=company_id, supplier_id=supplier_id)
    )
    ap_txn_repo = APTransactionRepository(db_session)
    ap_txn_repo.create(
        APTransaction(
            company_id=company_id,
            supplier_ledger_id=supplier_ledger.id,
            transaction_type="BILL",
            transaction_date=date(2026, 6, 3),
            due_date=date(2026, 6, 20),
            currency_code="USD",
            exchange_rate=Decimal("1"),
            amount_foreign=Decimal("180.00"),
            amount_base=Decimal("180.00"),
            outstanding_amount=Decimal("180.00"),
            status="OPEN",
            bill_number="BILL-KPI-001",
        )
    )
    ap_txn_repo.create(
        APTransaction(
            company_id=company_id,
            supplier_ledger_id=supplier_ledger.id,
            transaction_type="BILL",
            transaction_date=date(2026, 6, 3),
            due_date=date(2026, 5, 1),
            currency_code="USD",
            exchange_rate=Decimal("1"),
            amount_foreign=Decimal("120.00"),
            amount_base=Decimal("120.00"),
            outstanding_amount=Decimal("120.00"),
            status="OPEN",
            bill_number="BILL-KPI-002",
        )
    )

    return base_setup


@pytest.fixture
def posting_engine(db_session: Session) -> PostingEngine:
    return build_posting_engine(db_session)


@pytest.fixture
def service(db_session: Session) -> FinancialKPIService:
    return build_kpi_service(db_session)


def _post_dataset(posting_engine: PostingEngine, setup: dict[str, Any]) -> None:
    company_id = setup["company_id"]

    posting_engine.post_direct(
        company_id=company_id,
        journal_type="OPENING_BALANCE",
        posting_source="MANUAL",
        posting_date=date(2026, 1, 1),
        lines=[
            {
                "account_id": setup["cash"].id,
                "debit_amount": Decimal("10000.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": setup["equity"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("10000.00"),
            },
        ],
        currency_code="USD",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="SALES",
        posting_date=date(2026, 6, 1),
        lines=[
            {
                "account_id": setup["ar"].id,
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
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="MANUAL",
        posting_date=date(2026, 6, 1),
        lines=[
            {
                "account_id": setup["cash"].id,
                "debit_amount": Decimal("80.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": setup["tax_payable"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("80.00"),
            },
        ],
        currency_code="USD",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="PURCHASE",
        posting_date=date(2026, 6, 3),
        lines=[
            {
                "account_id": setup["inventory"].id,
                "debit_amount": Decimal("300.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": setup["ap"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("300.00"),
            },
        ],
        currency_code="USD",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="SALES",
        posting_date=date(2026, 6, 5),
        lines=[
            {
                "account_id": setup["cogs"].id,
                "debit_amount": Decimal("200.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": setup["inventory"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("200.00"),
            },
        ],
        currency_code="USD",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="MANUAL",
        posting_date=date(2026, 6, 10),
        lines=[
            {
                "account_id": setup["other_expense"].id,
                "debit_amount": Decimal("50.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": setup["cash"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("50.00"),
            },
        ],
        currency_code="USD",
    )


class TestKnownDataset:
    """Phase 15's Independent Test: all 15 KPIs against a hand-computed
    known dataset (see module docstring for the arithmetic).
    """

    def test_all_fifteen_kpis(
        self,
        posting_engine: PostingEngine,
        service: FinancialKPIService,
        setup: dict[str, Any],
    ) -> None:
        _post_dataset(posting_engine, setup)

        result = service.get_dashboard_kpis(setup["company_id"], AS_OF)
        kpis = result["kpis"]

        assert kpis["cash_position"]["current_value"] == Decimal("10030.00")
        assert kpis["cash_position"]["prior_value"] == Decimal("10000.00")
        assert kpis["cash_position"]["trend"] == "up"

        assert kpis["accounts_receivable_total"]["current_value"] == Decimal("500.00")
        assert kpis["accounts_receivable_total"]["prior_value"] == Decimal("0")

        assert kpis["accounts_payable_total"]["current_value"] == Decimal("300.00")
        assert kpis["accounts_payable_total"]["prior_value"] == Decimal("0")

        assert kpis["ar_overdue_pct"]["current_value"] == Decimal("40")
        assert kpis["ap_overdue_pct"]["current_value"] == Decimal("40")

        assert kpis["revenue_mtd"]["current_value"] == Decimal("500.00")
        assert kpis["revenue_mtd"]["prior_value"] == Decimal("0")

        assert kpis["gross_profit_margin"]["current_value"] == Decimal("60")
        assert kpis["net_profit_margin"]["current_value"] == Decimal("50")

        expected_current_ratio = Decimal("10630.00") / Decimal("380.00")
        expected_quick_ratio = Decimal("10530.00") / Decimal("380.00")
        assert kpis["current_ratio"]["current_value"] == expected_current_ratio
        assert kpis["quick_ratio"]["current_value"] == expected_quick_ratio
        # Prior snapshot has zero current liabilities -> safe-division zero.
        assert kpis["current_ratio"]["prior_value"] == Decimal("0")
        assert kpis["quick_ratio"]["prior_value"] == Decimal("0")

        assert kpis["days_sales_outstanding"]["current_value"] == Decimal("15")
        assert kpis["days_payable_outstanding"]["current_value"] == Decimal("22.5")

        assert kpis["operating_cash_flow"]["current_value"] == Decimal("30.00")
        assert kpis["operating_cash_flow"]["prior_value"] == Decimal("0")

        assert kpis["tax_liability_balance"]["current_value"] == Decimal("80.00")
        assert kpis["tax_liability_balance"]["prior_value"] == Decimal("0")
        assert kpis["tax_liability_balance"]["change_pct"] is None
        assert kpis["tax_liability_balance"]["trend"] == "up"

        assert len(result["period_close_status"]) == 12
        assert all(p["status"] == "OPEN" for p in result["period_close_status"])
        june = next(p for p in result["period_close_status"] if p["period_number"] == 6)
        assert june["period_name"] == "June 2026"

    def test_cash_position_endpoint(
        self,
        posting_engine: PostingEngine,
        service: FinancialKPIService,
        setup: dict[str, Any],
    ) -> None:
        _post_dataset(posting_engine, setup)

        result = service.get_cash_position(setup["company_id"], AS_OF, trend_days=7)

        assert result["total_cash_position"] == Decimal("10030.00")
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["balance"] == Decimal("10030.00")
        assert result["accounts"][0]["is_cash_account"] is True
        assert len(result["trend"]) == 7
        assert result["trend"][-1]["date"] == AS_OF
        assert result["trend"][-1]["balance"] == Decimal("10030.00")


class TestZeroDenominatorSafety:
    def test_kpis_do_not_raise_with_no_postings(
        self, service: FinancialKPIService, base_setup: dict[str, Any]
    ) -> None:
        """No journals, no AR/AP records at all: every ratio/percentage
        must resolve to a safe zero rather than raising
        ``ZeroDivisionError`` (spec.md §40 KPIs are reporting math, not
        posting-path validation).
        """
        result = service.get_dashboard_kpis(base_setup["company_id"], AS_OF)
        kpis = result["kpis"]

        for key in (
            "ar_overdue_pct",
            "ap_overdue_pct",
            "gross_profit_margin",
            "net_profit_margin",
            "current_ratio",
            "quick_ratio",
            "days_sales_outstanding",
            "days_payable_outstanding",
        ):
            assert kpis[key]["current_value"] == Decimal("0"), key

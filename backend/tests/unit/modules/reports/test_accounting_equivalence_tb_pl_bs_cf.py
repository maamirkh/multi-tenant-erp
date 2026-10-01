"""T058 — given fixture posted journal entries,
``FinancialStatementService.get_trial_balance/get_pl/get_balance_sheet/
get_cash_flow()`` called directly, compared against
``AccountingAdapter.run()``'s output for the same 4 keys — byte-identical
totals; Balance Sheet equation holds in both.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_financial_statement_service
from modules.reports.schemas.accounting import (
    BalanceSheetFilter,
    CashFlowFilter,
    ProfitLossFilter,
    TrialBalanceFilter,
)
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter
from modules.reports.services.adapters.base import AggregateReportResult
from tests.integration.api.v1.accounting.test_reports_api import _setup


def test_trial_balance_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    fixture = _setup(db_session, company_id)

    statements = build_financial_statement_service(db_session)
    direct = statements.get_trial_balance(company_id, fixture["period"].id)

    adapter = AccountingAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "accounting.trial_balance",
        TrialBalanceFilter(period_id=fixture["period"].id),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.total_debit == direct["total_debit"]
    assert result.data.total_credit == direct["total_credit"]
    assert result.data.is_balanced == direct["is_balanced"]
    assert result.data.is_balanced is True


def test_profit_loss_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    fixture = _setup(db_session, company_id)
    today = fixture["today"]

    statements = build_financial_statement_service(db_session)
    direct = statements.get_pl(company_id, today, today)

    adapter = AccountingAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "accounting.profit_loss",
        ProfitLossFilter(period_from=today, period_to=today),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.total_revenue == direct["total_revenue"]
    assert result.data.total_expense == direct["total_expense"]
    assert result.data.net_income == direct["net_income"]


def test_balance_sheet_equivalence_and_equation_holds(db_session: Session) -> None:
    company_id = uuid.uuid4()
    fixture = _setup(db_session, company_id)
    today: date = fixture["today"]

    statements = build_financial_statement_service(db_session)
    direct = statements.get_balance_sheet(company_id, today)

    adapter = AccountingAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "accounting.balance_sheet",
        BalanceSheetFilter(as_of_date=today),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.total_assets == direct["total_assets"]
    assert result.data.total_liabilities == direct["total_liabilities"]
    assert result.data.total_equity == direct["total_equity"]
    # Balance Sheet equation: Assets = Liabilities + Equity, in both.
    assert (
        direct["total_assets"] == direct["total_liabilities"] + direct["total_equity"]
    )
    assert result.data.total_assets == (
        result.data.total_liabilities + result.data.total_equity
    )


def test_cash_flow_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    fixture = _setup(db_session, company_id)
    today = fixture["today"]

    statements = build_financial_statement_service(db_session)
    direct = statements.get_cash_flow(company_id, today, today)

    adapter = AccountingAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "accounting.cash_flow",
        CashFlowFilter(period_from=today, period_to=today),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.net_change_in_cash == direct["net_change_in_cash"]
    assert result.data.closing_cash_balance == direct["closing_cash_balance"]

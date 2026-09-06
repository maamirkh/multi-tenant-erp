"""Pydantic v2 schemas for Financial Statements & Reports — Phase 13.

  TrialBalanceRow / TrialBalanceReport
  BalanceSheetLine / BalanceSheetSection / BalanceSheetReport
  PLLine / PLSection / PLReport
  CashFlowReport
  GLReportResponse (``GLReportRow`` already exists in schemas/gl.py — Phase 4
  — and is reused here rather than duplicated, per DRY)

``FinancialStatementService`` returns flat dicts (Phase 12's proven,
tested shape — ``total_assets``/``assets``/etc. as sibling top-level keys,
not nested under a nested "section" object, since changing that shape
would break Phase 12's already-passing tests). ``BalanceSheetReport``/
``PLReport`` bridge that flat shape into the sectioned API contract T259
asks for via a small ``from_service_dict()`` adapter — a thin,
presentation-layer transform, not a domain-service change.

Spec ref: specs/008-accounting-finance/tasks.md T259
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from modules.accounting.schemas.base import AccountingBaseSchema
from modules.accounting.schemas.gl import GLReportRow, JournalEntryResponse

# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------


class TrialBalanceRow(AccountingBaseSchema):
    account_id: UUID
    account_code: str
    total_debit: Decimal
    total_credit: Decimal


class TrialBalanceReport(AccountingBaseSchema):
    company_id: UUID
    fiscal_period_id: UUID
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool
    comparative: TrialBalanceReport | None = None


# ---------------------------------------------------------------------------
# Balance Sheet
# ---------------------------------------------------------------------------


class BalanceSheetLine(AccountingBaseSchema):
    # account_id is None for the synthetic "Current Year Earnings" line
    # (FinancialStatementService._get_current_year_earnings()) — computed,
    # not tied to a single ledger account.
    account_id: UUID | None = None
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    amount: Decimal


class BalanceSheetSection(AccountingBaseSchema):
    """One grouped section of the Balance Sheet — Assets, Liabilities, or Equity."""

    name: str
    lines: list[BalanceSheetLine]
    total: Decimal


class BalanceSheetReport(AccountingBaseSchema):
    company_id: UUID
    as_of_date: date
    report_currency: str
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool
    comparative: BalanceSheetReport | None = None

    @classmethod
    def from_service_dict(cls, data: dict[str, Any]) -> BalanceSheetReport:
        comparative = data.get("comparative")
        return cls(
            company_id=data["company_id"],
            as_of_date=data["as_of_date"],
            report_currency=data["report_currency"],
            assets=BalanceSheetSection(
                name="Assets", lines=data["assets"], total=data["total_assets"]
            ),
            liabilities=BalanceSheetSection(
                name="Liabilities",
                lines=data["liabilities"],
                total=data["total_liabilities"],
            ),
            equity=BalanceSheetSection(
                name="Equity", lines=data["equity"], total=data["total_equity"]
            ),
            total_assets=data["total_assets"],
            total_liabilities=data["total_liabilities"],
            total_equity=data["total_equity"],
            is_balanced=data["is_balanced"],
            comparative=cls.from_service_dict(comparative) if comparative else None,
        )


# ---------------------------------------------------------------------------
# Profit & Loss
# ---------------------------------------------------------------------------


class PLLine(AccountingBaseSchema):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    amount: Decimal


class PLSection(AccountingBaseSchema):
    """One grouped section of the P&L — Revenue or Expense."""

    name: str
    lines: list[PLLine]
    total: Decimal


class PLReport(AccountingBaseSchema):
    company_id: UUID
    period_from: date
    period_to: date
    cost_center_id: UUID | None = None
    report_currency: str
    revenue: PLSection
    expense: PLSection
    total_revenue: Decimal
    total_expense: Decimal
    net_income: Decimal
    comparative: PLReport | None = None

    @classmethod
    def from_service_dict(cls, data: dict[str, Any]) -> PLReport:
        comparative = data.get("comparative")
        return cls(
            company_id=data["company_id"],
            period_from=data["period_from"],
            period_to=data["period_to"],
            cost_center_id=data.get("cost_center_id"),
            report_currency=data["report_currency"],
            revenue=PLSection(
                name="Revenue", lines=data["revenue_lines"], total=data["total_revenue"]
            ),
            expense=PLSection(
                name="Expense", lines=data["expense_lines"], total=data["total_expense"]
            ),
            total_revenue=data["total_revenue"],
            total_expense=data["total_expense"],
            net_income=data["net_income"],
            comparative=cls.from_service_dict(comparative) if comparative else None,
        )


# ---------------------------------------------------------------------------
# Cash Flow
# ---------------------------------------------------------------------------


class CashFlowAdjustmentLine(AccountingBaseSchema):
    account_id: UUID
    account_code: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    adjustment: Decimal


class CashFlowReport(AccountingBaseSchema):
    company_id: UUID
    period_from: date
    period_to: date
    net_income: Decimal
    working_capital_adjustments: list[CashFlowAdjustmentLine]
    net_cash_from_operating_activities: Decimal
    opening_cash_balance: Decimal
    closing_cash_balance: Decimal
    net_change_in_cash: Decimal
    reconciles: bool


# ---------------------------------------------------------------------------
# GL report — cursor-paginated (GLReportRow reused from schemas/gl.py)
# ---------------------------------------------------------------------------


class GLReportResponse(AccountingBaseSchema):
    items: list[GLReportRow]
    has_more: bool
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Journal report
# ---------------------------------------------------------------------------


class JournalReportResponse(AccountingBaseSchema):
    company_id: UUID
    fiscal_period_id: UUID
    entries: list[JournalEntryResponse]
    total: int


__all__ = [
    "BalanceSheetLine",
    "BalanceSheetReport",
    "BalanceSheetSection",
    "CashFlowAdjustmentLine",
    "CashFlowReport",
    "GLReportResponse",
    "GLReportRow",
    "JournalReportResponse",
    "PLLine",
    "PLReport",
    "PLSection",
    "TrialBalanceReport",
    "TrialBalanceRow",
]

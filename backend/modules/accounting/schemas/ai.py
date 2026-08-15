"""Pydantic v2 schemas for AI ERP Readiness endpoints — Phase 17.

  GLEventStreamRow
  PLHistoryPeriod / PLHistoryResponse
  CashFlowHistoryPeriod / CashFlowHistoryResponse
  AnomalyReportRequest / AnomalyFlagResponse

Spec ref: specs/008-accounting-finance/tasks.md T308
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# GL event stream (T304)
# ---------------------------------------------------------------------------


class GLEventStreamRow(AccountingBaseSchema):
    """One posted journal entry, shaped for ML training-data consumption.

    Mirrors ``accounting.journal.posted``'s payload fields (see
    contracts/events.md) plus ``reference`` — present on the read model even
    though the fire-and-forget domain event itself omits it (T303 finding).
    """

    journal_entry_id: UUID
    journal_number: str | None = None
    journal_type: str
    posting_source: str
    posting_date: date
    reference: str | None = None
    total_debit_base: Decimal
    total_credit_base: Decimal
    posted_at: datetime | None = None
    actor_id: UUID | None = Field(
        None,
        description="user_id who posted the entry, or null for system-posted entries",
    )


# ---------------------------------------------------------------------------
# P&L history (T305)
# ---------------------------------------------------------------------------


class PLHistoryPeriod(AccountingBaseSchema):
    """One fiscal period's P&L summary, for revenue/expense forecasting models."""

    fiscal_period_id: UUID
    period_name: str
    start_date: date
    end_date: date
    total_revenue: Decimal
    total_expense: Decimal
    net_income: Decimal


class PLHistoryResponse(AccountingBaseSchema):
    company_id: UUID
    periods: list[PLHistoryPeriod]


# ---------------------------------------------------------------------------
# Cash flow history (T306)
# ---------------------------------------------------------------------------


class CashFlowHistoryPeriod(AccountingBaseSchema):
    """One fiscal period's cash flow summary, for cash flow forecasting models."""

    fiscal_period_id: UUID
    period_name: str
    start_date: date
    end_date: date
    net_income: Decimal
    net_cash_from_operating_activities: Decimal
    opening_cash_balance: Decimal
    closing_cash_balance: Decimal
    net_change_in_cash: Decimal


class CashFlowHistoryResponse(AccountingBaseSchema):
    company_id: UUID
    periods: list[CashFlowHistoryPeriod]


# ---------------------------------------------------------------------------
# Anomaly detection stub (T307)
# ---------------------------------------------------------------------------


class AnomalyReportRequest(AccountingBaseSchema):
    journal_entry_ids: list[UUID] = Field(..., min_length=1)
    reason: str | None = None


class AnomalyFlagResponse(AccountingBaseSchema):
    id: UUID
    journal_entry_id: UUID
    reason: str | None = None
    status: str
    created_at: datetime

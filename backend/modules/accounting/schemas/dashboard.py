"""Pydantic v2 schemas for the CFO Financial Intelligence & KPI Dashboard — Phase 15.

  KPIValue / FinancialKPIResponse — the 15 KPIs of spec.md §40
  PeriodCloseStatusItem
  CashAccountBalance / CashTrendPoint / CashPositionResponse

Spec ref: specs/008-accounting-finance/spec.md §40 KPI Requirements
Tasks ref: specs/008-accounting-finance/tasks.md T289
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# KPI dashboard
# ---------------------------------------------------------------------------


class KPIValue(AccountingBaseSchema):
    label: str
    current_value: Decimal
    prior_value: Decimal
    change_pct: Decimal | None = None
    trend: Literal["up", "down", "flat"]


class PeriodCloseStatusItem(AccountingBaseSchema):
    period_name: str
    period_number: int
    status: str


class FinancialKPIResponse(AccountingBaseSchema):
    company_id: UUID
    as_of_date: date
    kpis: dict[str, KPIValue]
    period_close_status: list[PeriodCloseStatusItem]


# ---------------------------------------------------------------------------
# Cash position
# ---------------------------------------------------------------------------


class CashAccountBalance(AccountingBaseSchema):
    account_id: UUID
    account_code: str
    account_name: str
    is_bank_account: bool
    is_cash_account: bool
    balance: Decimal


class CashTrendPoint(AccountingBaseSchema):
    date: date
    balance: Decimal


class CashPositionResponse(AccountingBaseSchema):
    company_id: UUID
    as_of_date: date
    total_cash_position: Decimal
    accounts: list[CashAccountBalance]
    trend: list[CashTrendPoint]


__all__ = [
    "CashAccountBalance",
    "CashPositionResponse",
    "CashTrendPoint",
    "FinancialKPIResponse",
    "KPIValue",
    "PeriodCloseStatusItem",
]

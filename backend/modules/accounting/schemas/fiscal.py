"""Pydantic v2 schemas for Fiscal Calendar — Phase 3.

  FiscalYearCreateRequest / FiscalYearResponse
  FiscalPeriodResponse
  PeriodLockRequest / PeriodUnlockRequest
  OpeningBalanceLine / OpeningBalanceImportRequest / OpeningBalanceResponse
  YearEndCloseRequest

Spec ref: specs/008-accounting-finance/tasks.md T077
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Fiscal Year
# ---------------------------------------------------------------------------


class FiscalYearCreateRequest(AccountingBaseSchema):
    """Request body for creating a fiscal year."""

    fiscal_year_name: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date
    base_currency_code: str = Field(..., min_length=3, max_length=3)
    is_current: bool = False


class FiscalYearUpdateRequest(AccountingBaseSchema):
    """Request body for updating a fiscal year. Only name/current flag are mutable.

    Dates and status are structural — dates are fixed once periods are
    generated at creation time, and status only changes via the lock/
    unlock/year-end-close workflows.
    """

    fiscal_year_name: str | None = Field(None, min_length=1, max_length=50)
    is_current: bool | None = None


class FiscalYearResponse(AccountingBaseSchema):
    """Response schema for a fiscal year."""

    id: UUID
    company_id: UUID
    fiscal_year_name: str
    start_date: date
    end_date: date
    status: str
    base_currency_code: str
    is_current: bool


# ---------------------------------------------------------------------------
# Fiscal Period
# ---------------------------------------------------------------------------


class FiscalPeriodResponse(AccountingBaseSchema):
    """Response schema for a fiscal period."""

    id: UUID
    company_id: UUID
    fiscal_year_id: UUID
    period_number: int
    period_name: str
    start_date: date
    end_date: date
    status: str
    locked_at: datetime | None
    locked_by_user_id: UUID | None
    lock_reason: str | None
    closed_at: datetime | None
    closed_by_user_id: UUID | None


class PeriodLockRequest(AccountingBaseSchema):
    """Request body for locking a fiscal period."""

    lock_reason: str = Field(..., min_length=1, max_length=500)


class PeriodUnlockRequest(AccountingBaseSchema):
    """Request body for unlocking a fiscal period. Reason is mandatory."""

    reason: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Opening Balances
# ---------------------------------------------------------------------------


class OpeningBalanceLine(AccountingBaseSchema):
    """A single opening balance line within an import request."""

    account_id: UUID
    debit_amount: Decimal = Field(Decimal("0"), ge=0)
    credit_amount: Decimal = Field(Decimal("0"), ge=0)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    notes: str | None = None


class OpeningBalanceImportRequest(AccountingBaseSchema):
    """Request body for setting up opening balances for a fiscal year."""

    lines: list[OpeningBalanceLine] = Field(..., min_length=1)


class OpeningBalanceResponse(AccountingBaseSchema):
    """Response schema for a persisted opening balance line."""

    id: UUID
    company_id: UUID
    fiscal_year_id: UUID
    account_id: UUID
    debit_amount: Decimal
    credit_amount: Decimal
    currency_code: str | None
    notes: str | None


# ---------------------------------------------------------------------------
# Year-End Close
# ---------------------------------------------------------------------------


class YearEndCloseRequest(AccountingBaseSchema):
    """Request body for executing the year-end close workflow.

    No fields are strictly required today (the actor is taken from the
    authenticated session) — reserved for a future confirmation checklist
    per the ``YearEndCloseWizard`` frontend component.
    """

    confirm: bool = Field(
        True, description="Explicit confirmation the close checklist was reviewed"
    )

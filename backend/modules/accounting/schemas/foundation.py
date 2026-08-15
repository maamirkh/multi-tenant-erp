"""Pydantic v2 schemas for accounting foundation entities — Phase 1.

  AccountingConfigurationRead/Update
  CurrencyRead/Create
  ExchangeRateRead/Create
  AccountingFeatureFlagRead/Update

Spec ref: specs/008-accounting-finance/tasks.md T033
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Accounting Configuration
# ---------------------------------------------------------------------------


class AccountingConfigurationRead(AccountingBaseSchema):
    """Response schema for company accounting configuration."""

    id: UUID
    company_id: UUID
    base_currency_code: str
    journal_approval_threshold: Decimal | None
    payment_approval_threshold: Decimal | None
    credit_warning_threshold_pct: Decimal
    cheque_stale_days: int
    default_ar_account_id: UUID | None
    default_ap_account_id: UUID | None
    default_retained_earnings_account_id: UUID | None
    default_exchange_gain_account_id: UUID | None
    default_exchange_loss_account_id: UUID | None
    default_bad_debt_account_id: UUID | None
    default_revenue_account_id: UUID | None
    default_expense_account_id: UUID | None
    default_tax_liability_account_id: UUID | None
    default_input_tax_account_id: UUID | None


class AccountingConfigurationUpdate(AccountingBaseSchema):
    """Request body for updating company accounting configuration."""

    base_currency_code: str | None = Field(None, min_length=3, max_length=3)
    journal_approval_threshold: Decimal | None = Field(None, ge=0)
    payment_approval_threshold: Decimal | None = Field(None, ge=0)
    credit_warning_threshold_pct: Decimal | None = Field(None, ge=0, le=100)
    cheque_stale_days: int | None = Field(None, ge=1)
    default_ar_account_id: UUID | None = None
    default_ap_account_id: UUID | None = None
    default_retained_earnings_account_id: UUID | None = None
    default_exchange_gain_account_id: UUID | None = None
    default_exchange_loss_account_id: UUID | None = None
    default_bad_debt_account_id: UUID | None = None
    default_revenue_account_id: UUID | None = None
    default_expense_account_id: UUID | None = None
    default_tax_liability_account_id: UUID | None = None
    default_input_tax_account_id: UUID | None = None


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------


class CurrencyRead(AccountingBaseSchema):
    """Response schema for a currency."""

    id: UUID
    iso_code: str
    name: str
    symbol: str
    decimal_places: int
    is_active: bool


class CurrencyCreate(AccountingBaseSchema):
    """Request body for creating a currency."""

    iso_code: str = Field(..., min_length=3, max_length=3)
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=10)
    decimal_places: int = Field(2, ge=0)


# ---------------------------------------------------------------------------
# Exchange Rate
# ---------------------------------------------------------------------------


class ExchangeRateRead(AccountingBaseSchema):
    """Response schema for an exchange rate."""

    id: UUID
    company_id: UUID
    from_currency_code: str
    to_currency_code: str
    rate_date: date
    rate: Decimal
    rate_type: str


class ExchangeRateCreate(AccountingBaseSchema):
    """Request body for recording a new exchange rate."""

    from_currency_code: str = Field(..., min_length=3, max_length=3)
    to_currency_code: str = Field(..., min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(..., gt=0)
    rate_type: str = Field("SPOT", pattern="^(SPOT|AVERAGE|CLOSING|HISTORICAL)$")


# ---------------------------------------------------------------------------
# Feature Flag
# ---------------------------------------------------------------------------


class AccountingFeatureFlagRead(AccountingBaseSchema):
    """Response schema for an accounting feature flag state."""

    flag_key: str
    label: str
    description: str
    is_enabled: bool
    is_overridden: bool
    default_enabled: bool


class AccountingFeatureFlagUpdate(AccountingBaseSchema):
    """Request body for updating an accounting feature flag."""

    is_enabled: bool
    description: str | None = None

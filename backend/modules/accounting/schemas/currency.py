"""Pydantic v2 schemas for Currency Revaluation — Phase 12.

  RevaluationRequest
  RevaluationLine
  RevaluationReport

Spec ref: specs/008-accounting-finance/tasks.md T250
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class RevaluationRequest(AccountingBaseSchema):
    """Request body to run a period-end currency revaluation."""

    fiscal_period_id: UUID
    revaluation_date: date


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class RevaluationLine(AccountingBaseSchema):
    """One open foreign-currency AR/AP transaction's unrealized gain/loss."""

    transaction_type: str = Field(..., description="'AR' or 'AP'")
    transaction_id: UUID
    currency_code: str
    booking_rate: Decimal
    current_rate: Decimal
    outstanding_foreign: Decimal
    outstanding_base_before: Decimal
    gain_loss_amount: Decimal = Field(
        ..., description="Positive = unrealized gain, negative = unrealized loss."
    )


class RevaluationReport(AccountingBaseSchema):
    """Full result of one currency revaluation run."""

    id: UUID
    company_id: UUID
    fiscal_period_id: UUID
    revaluation_date: date
    currencies_revalued: list[str]
    lines: list[RevaluationLine]
    total_unrealized_gain_base: Decimal
    total_unrealized_loss_base: Decimal
    net_gain_loss_base: Decimal
    journal_entry_id: UUID | None = None
    created_at: datetime


__all__ = ["RevaluationLine", "RevaluationReport", "RevaluationRequest"]

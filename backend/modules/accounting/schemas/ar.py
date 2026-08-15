"""Pydantic v2 schemas for Accounts Receivable — Phase 6.

  CustomerLedgerResponse    — subsidiary ledger root
  ARTransactionResponse     — invoice/credit-note/adjustment/write-off record
  ARAgingReport             — customer rows + aggregate bucket totals
  CustomerStatementResponse — opening balance + transactions + closing balance
  CreditHoldRequest / CreditLimitRequest
  WriteOffRequest

Spec ref: specs/008-accounting-finance/tasks.md T144
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Ledger / transaction responses
# ---------------------------------------------------------------------------


class CustomerLedgerResponse(AccountingBaseSchema):
    """Response schema for a customer's AR subsidiary ledger root."""

    id: UUID
    customer_id: UUID
    credit_limit: Decimal
    credit_status: str
    credit_hold_at: datetime | None = None
    credit_hold_reason: str | None = None
    credit_hold_by: UUID | None = None
    total_outstanding_base: Decimal
    last_payment_date: date | None = None
    average_payment_days: Decimal | None = None


class ARTransactionResponse(AccountingBaseSchema):
    """Response schema for a single AR transaction."""

    id: UUID
    customer_ledger_id: UUID
    transaction_type: str
    transaction_date: date
    due_date: date | None = None
    currency_code: str
    exchange_rate: Decimal
    amount_foreign: Decimal
    amount_base: Decimal
    outstanding_amount: Decimal
    status: str
    source_document_type: str | None = None
    source_document_id: UUID | None = None
    journal_entry_id: UUID | None = None
    invoice_number: str | None = None


# ---------------------------------------------------------------------------
# Aging
# ---------------------------------------------------------------------------


class ARAgingRow(AccountingBaseSchema):
    """One customer's aging bucket totals."""

    customer_ledger_id: UUID | None = None
    customer_id: UUID | None = None
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    days_91_120: Decimal
    days_120_plus: Decimal
    total: Decimal


class ARAgingReport(AccountingBaseSchema):
    """Full AR aging report: per-customer rows plus the aggregate totals row."""

    as_of_date: date
    rows: list[ARAgingRow]
    totals: ARAgingRow


# ---------------------------------------------------------------------------
# Customer statement
# ---------------------------------------------------------------------------


class CustomerStatementResponse(AccountingBaseSchema):
    """A customer statement for a date range: opening balance, movements, closing balance."""

    customer_id: UUID
    from_date: date
    to_date: date
    opening_balance: Decimal
    transactions: list[ARTransactionResponse]
    closing_balance: Decimal


# ---------------------------------------------------------------------------
# Credit management / write-off requests
# ---------------------------------------------------------------------------


class CreditHoldRequest(AccountingBaseSchema):
    """Request body for placing a credit hold on a customer."""

    reason: str = Field(..., min_length=1, max_length=500)


class CreditHoldReleaseRequest(AccountingBaseSchema):
    """Request body for releasing a customer's credit hold."""

    reason: str | None = Field(None, max_length=500)


class CreditLimitRequest(AccountingBaseSchema):
    """Request body for setting a customer's credit limit."""

    credit_limit: Decimal = Field(..., ge=0)


class WriteOffRequest(AccountingBaseSchema):
    """Request body for writing off an AR transaction's outstanding balance."""

    reason: str = Field(..., min_length=1, max_length=500)


__all__ = [
    "ARAgingReport",
    "ARAgingRow",
    "ARTransactionResponse",
    "CreditHoldReleaseRequest",
    "CreditHoldRequest",
    "CreditLimitRequest",
    "CustomerLedgerResponse",
    "CustomerStatementResponse",
    "WriteOffRequest",
]

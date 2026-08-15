"""Pydantic v2 schemas for Cash Management — Phase 9.

  CashAccountCreateRequest / CashAccountResponse
  CashTransactionResponse
  CashReceiptRequest / CashPaymentRequest
  PettyCashVoucherRequest / PettyCashVoucherResponse
  PettyCashReplenishmentRequest / PettyCashReplenishmentResponse
  CashReconciliationRequest / CashReconciliationResponse
  CashBookRow / CashBookResponse

Spec ref: specs/008-accounting-finance/tasks.md T197
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Cash accounts
# ---------------------------------------------------------------------------


class CashAccountCreateRequest(AccountingBaseSchema):
    account_name: str = Field(..., min_length=1, max_length=200)
    currency_code: str = Field(..., min_length=3, max_length=3)
    gl_account_id: UUID
    is_petty_cash: bool = False
    float_amount: Decimal = Decimal("0")


class CashAccountResponse(AccountingBaseSchema):
    id: UUID
    account_name: str
    currency_code: str
    gl_account_id: UUID
    current_balance: Decimal
    is_petty_cash: bool
    float_amount: Decimal
    is_active: bool


# ---------------------------------------------------------------------------
# Cash transactions / receipts / payments
# ---------------------------------------------------------------------------


class CashTransactionResponse(AccountingBaseSchema):
    id: UUID
    cash_account_id: UUID
    transaction_date: date
    transaction_type: str
    amount: Decimal
    reference: str | None = None
    description: str | None = None
    journal_entry_id: UUID | None = None
    counterparty_type: str | None = None
    counterparty_id: UUID | None = None


class CashReceiptRequest(AccountingBaseSchema):
    amount: Decimal = Field(..., gt=0)
    contra_account_id: UUID
    receipt_date: date
    reference: str | None = None
    description: str | None = None
    counterparty_type: str | None = None
    counterparty_id: UUID | None = None


class CashPaymentRequest(AccountingBaseSchema):
    amount: Decimal = Field(..., gt=0)
    contra_account_id: UUID
    payment_date: date
    reference: str | None = None
    description: str | None = None
    counterparty_type: str | None = None
    counterparty_id: UUID | None = None


# ---------------------------------------------------------------------------
# Petty cash vouchers / replenishment
# ---------------------------------------------------------------------------


class PettyCashVoucherRequest(AccountingBaseSchema):
    voucher_date: date
    amount: Decimal = Field(..., gt=0)
    expense_account_id: UUID
    recipient_name: str = Field(..., min_length=1, max_length=200)
    purpose: str = Field(..., min_length=1)
    approved_by_user_id: UUID | None = None
    voucher_number: str = Field(..., min_length=1, max_length=30)


class PettyCashVoucherResponse(AccountingBaseSchema):
    id: UUID
    cash_account_id: UUID
    voucher_date: date
    amount: Decimal
    expense_account_id: UUID
    recipient_name: str
    purpose: str
    approved_by_user_id: UUID | None = None
    voucher_number: str
    journal_entry_id: UUID | None = None


class PettyCashReplenishmentRequest(AccountingBaseSchema):
    voucher_ids: list[UUID] = Field(..., min_length=1)
    bank_gl_account_id: UUID
    replenishment_date: date
    reference: str | None = None
    description: str | None = None


class PettyCashReplenishmentResponse(AccountingBaseSchema):
    cash_transaction: CashTransactionResponse
    vouchers: list[PettyCashVoucherResponse]
    journal_entry_id: UUID


# ---------------------------------------------------------------------------
# Cash reconciliation
# ---------------------------------------------------------------------------


class CashReconciliationRequest(AccountingBaseSchema):
    reconciliation_date: date
    physical_count_amount: Decimal = Field(..., ge=0)
    difference_account_id: UUID | None = None


class CashReconciliationResponse(AccountingBaseSchema):
    id: UUID
    cash_account_id: UUID
    reconciliation_date: date
    physical_count_amount: Decimal
    gl_balance_amount: Decimal
    difference: Decimal
    difference_account_id: UUID | None = None
    journal_entry_id: UUID | None = None
    status: str
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Cash book
# ---------------------------------------------------------------------------


class CashBookRow(AccountingBaseSchema):
    id: UUID
    transaction_date: date
    transaction_type: str
    amount: Decimal
    reference: str | None = None
    description: str | None = None


class CashBookResponse(AccountingBaseSchema):
    cash_account_id: UUID
    from_date: date
    to_date: date
    opening_balance: Decimal
    transactions: list[CashBookRow]
    closing_balance: Decimal


__all__ = [
    "CashAccountCreateRequest",
    "CashAccountResponse",
    "CashBookResponse",
    "CashBookRow",
    "CashPaymentRequest",
    "CashReceiptRequest",
    "CashReconciliationRequest",
    "CashReconciliationResponse",
    "CashTransactionResponse",
    "PettyCashReplenishmentRequest",
    "PettyCashReplenishmentResponse",
    "PettyCashVoucherRequest",
    "PettyCashVoucherResponse",
]

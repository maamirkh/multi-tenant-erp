"""Pydantic v2 schemas for Payment Processing — Phase 10.

  CustomerPaymentRequest / SupplierPaymentRequest / PaymentResponse
  AllocationLineRequest / PaymentAllocationRequest / PaymentAllocationLineResponse
  RefundRequest / PaymentRefundResponse
  WHTCertificateResponse

Spec ref: specs/008-accounting-finance/tasks.md T214
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Customer / supplier payments
# ---------------------------------------------------------------------------


class CustomerPaymentRequest(AccountingBaseSchema):
    customer_id: UUID
    payment_method: str = Field(
        ..., pattern="^(CASH|BANK_TRANSFER|CHEQUE|CARD|ONLINE)$"
    )
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    currency_code: str = Field(..., min_length=3, max_length=3)
    exchange_rate: Decimal = Decimal("1")
    payment_type: str = Field(
        default="CUSTOMER_RECEIPT", pattern="^(CUSTOMER_RECEIPT|ADVANCE_RECEIPT)$"
    )
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None
    advance_account_id: UUID | None = None
    reference: str | None = None
    notes: str | None = None
    cheque_id: UUID | None = None


class SupplierPaymentRequest(AccountingBaseSchema):
    supplier_id: UUID
    payment_method: str = Field(
        ..., pattern="^(CASH|BANK_TRANSFER|CHEQUE|CARD|ONLINE)$"
    )
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    currency_code: str = Field(..., min_length=3, max_length=3)
    exchange_rate: Decimal = Decimal("1")
    payment_type: str = Field(
        default="SUPPLIER_DISBURSEMENT",
        pattern="^(SUPPLIER_DISBURSEMENT|ADVANCE_PAYMENT)$",
    )
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None
    advance_account_id: UUID | None = None
    wht_amount: Decimal = Decimal("0")
    wht_payable_account_id: UUID | None = None
    reference: str | None = None
    notes: str | None = None
    cheque_id: UUID | None = None


class PaymentResponse(AccountingBaseSchema):
    id: UUID
    payment_type: str
    payment_method: str
    payment_date: date
    currency_code: str
    exchange_rate: Decimal
    amount_foreign: Decimal
    amount_base: Decimal
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None
    party_type: str
    party_id: UUID
    reference: str | None = None
    notes: str | None = None
    status: str
    journal_entry_id: UUID | None = None
    cheque_id: UUID | None = None
    discount_amount: Decimal
    wht_amount: Decimal


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


class AllocationLineRequest(AccountingBaseSchema):
    transaction_id: UUID
    amount_foreign: Decimal = Field(..., gt=0)
    discount_amount: Decimal = Decimal("0")
    discount_account_id: UUID | None = None
    release_account_id: UUID | None = None


class PaymentAllocationRequest(AccountingBaseSchema):
    allocation_lines: list[AllocationLineRequest] = Field(..., min_length=1)


class PaymentAllocationLineResponse(AccountingBaseSchema):
    id: UUID
    payment_id: UUID
    ar_transaction_id: UUID | None = None
    ap_transaction_id: UUID | None = None
    allocated_amount_foreign: Decimal
    allocated_amount_base: Decimal
    discount_amount: Decimal
    gain_loss_amount: Decimal
    gain_loss_journal_entry_id: UUID | None = None
    allocated_at: datetime


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------


class RefundRequest(AccountingBaseSchema):
    refund_date: date
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None


class PaymentRefundResponse(AccountingBaseSchema):
    id: UUID
    original_payment_id: UUID
    refund_date: date
    amount: Decimal
    reason: str
    journal_entry_id: UUID | None = None
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None


class CancelPaymentRequest(AccountingBaseSchema):
    reason: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Withholding tax
# ---------------------------------------------------------------------------


class WHTCertificateResponse(AccountingBaseSchema):
    payment_id: UUID
    party_id: UUID
    payment_date: date
    currency_code: str
    gross_amount: Decimal
    wht_amount: Decimal
    net_amount: Decimal
    wht_rate_percent: Decimal


__all__ = [
    "AllocationLineRequest",
    "CancelPaymentRequest",
    "CustomerPaymentRequest",
    "PaymentAllocationLineResponse",
    "PaymentAllocationRequest",
    "PaymentRefundResponse",
    "PaymentResponse",
    "RefundRequest",
    "SupplierPaymentRequest",
    "WHTCertificateResponse",
]

"""Pydantic v2 schemas for Accounts Payable — Phase 7.

  SupplierLedgerResponse                  — subsidiary ledger root
  APTransactionResponse                   — bill/credit-note/adjustment record
  APAgingReport                           — supplier rows + aggregate bucket totals
  SupplierStatementResponse                — opening balance + transactions + closing balance
  BillCreateRequest / CreditNoteCreateRequest — manual bill/credit-note entry (T163/T164)
  ReconcileStatementRequest / SupplierStatementReconciliationResponse / ReconciliationItemResponse
  RemittanceAdviceResponse

Spec ref: specs/008-accounting-finance/tasks.md T167
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Ledger / transaction responses
# ---------------------------------------------------------------------------


class SupplierLedgerResponse(AccountingBaseSchema):
    """Response schema for a supplier's AP subsidiary ledger root."""

    id: UUID
    supplier_id: UUID
    total_outstanding_base: Decimal
    last_payment_date: date | None = None


class APTransactionResponse(AccountingBaseSchema):
    """Response schema for a single AP transaction."""

    id: UUID
    supplier_ledger_id: UUID
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
    bill_number: str | None = None


# ---------------------------------------------------------------------------
# Manual bill / credit-note entry (T163/T164 — no live Purchase event exists;
# see handlers/integration_handlers.py's module docstring)
# ---------------------------------------------------------------------------


class BillCreateRequest(AccountingBaseSchema):
    """Request body for recording a supplier bill."""

    supplier_id: UUID
    bill_number: str = Field(..., min_length=1, max_length=50)
    total_amount: Decimal = Field(..., gt=0)
    currency_code: str = Field(..., min_length=3, max_length=3)
    transaction_date: date
    due_date: date | None = None


class CreditNoteCreateRequest(AccountingBaseSchema):
    """Request body for recording a supplier credit note against a bill."""

    supplier_id: UUID
    bill_id: UUID
    bill_number: str = Field(..., min_length=1, max_length=50)
    credit_amount: Decimal = Field(..., gt=0)
    transaction_date: date


# ---------------------------------------------------------------------------
# Aging
# ---------------------------------------------------------------------------


class APAgingRow(AccountingBaseSchema):
    """One supplier's aging bucket totals."""

    supplier_ledger_id: UUID | None = None
    supplier_id: UUID | None = None
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    days_91_120: Decimal
    days_120_plus: Decimal
    total: Decimal


class APAgingReport(AccountingBaseSchema):
    """Full AP aging report: per-supplier rows plus the aggregate totals row."""

    as_of_date: date
    rows: list[APAgingRow]
    totals: APAgingRow


# ---------------------------------------------------------------------------
# Supplier statement
# ---------------------------------------------------------------------------


class SupplierStatementResponse(AccountingBaseSchema):
    """A supplier statement for a date range: opening balance, movements, closing balance."""

    supplier_id: UUID
    from_date: date
    to_date: date
    opening_balance: Decimal
    transactions: list[APTransactionResponse]
    closing_balance: Decimal


# ---------------------------------------------------------------------------
# Supplier statement reconciliation (T162, spec.md §19.6)
# ---------------------------------------------------------------------------


class ReconcileStatementLine(AccountingBaseSchema):
    """One line from the supplier's received statement, to be matched."""

    reference: str | None = None
    amount: Decimal


class ReconcileStatementRequest(AccountingBaseSchema):
    """Request body to reconcile a supplier statement against the AP ledger."""

    supplier_id: UUID
    statement_date: date
    statement_total: Decimal
    statement_lines: list[ReconcileStatementLine]


class ReconciliationItemResponse(AccountingBaseSchema):
    """One matched/unmatched line within a reconciliation session."""

    id: UUID
    reconciliation_id: UUID
    ap_transaction_id: UUID | None = None
    statement_line_reference: str | None = None
    statement_amount: Decimal | None = None
    gl_amount: Decimal | None = None
    match_status: str
    difference: Decimal


class SupplierStatementReconciliationResponse(AccountingBaseSchema):
    """A reconciliation session's summary, with its matched/unmatched items."""

    id: UUID
    supplier_id: UUID
    statement_date: date
    statement_total: Decimal
    status: str
    items: list[ReconciliationItemResponse] = []


# ---------------------------------------------------------------------------
# Remittance advice
# ---------------------------------------------------------------------------


class RemittanceAdviceLine(AccountingBaseSchema):
    bill_number: str | None = None
    ap_transaction_id: UUID | None = None
    allocated_amount_base: Decimal
    discount_amount: Decimal


class RemittanceAdviceResponse(AccountingBaseSchema):
    """Remittance advice for a supplier payment — built from allocation rows
    sharing ``payment_id``. Empty ``lines``/zero ``total_paid`` until Phase 9
    populates ``APPaymentAllocation`` (no ``Payment`` entity exists yet).
    """

    payment_id: UUID
    lines: list[RemittanceAdviceLine]
    total_paid: Decimal


__all__ = [
    "APAgingReport",
    "APAgingRow",
    "APTransactionResponse",
    "BillCreateRequest",
    "CreditNoteCreateRequest",
    "ReconcileStatementLine",
    "ReconcileStatementRequest",
    "ReconciliationItemResponse",
    "RemittanceAdviceLine",
    "RemittanceAdviceResponse",
    "SupplierLedgerResponse",
    "SupplierStatementReconciliationResponse",
    "SupplierStatementResponse",
]

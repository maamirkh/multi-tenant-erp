"""Pydantic v2 schemas for Banking — Phase 8.

  BankAccountCreateRequest / BankAccountUpdateRequest / BankAccountResponse
  BankTransactionResponse
  BankTransferRequest / BankDepositRequest
  BankStatementImportRequest / BankStatementLineResponse
  ReconciliationStartRequest / ReconciliationMatchRequest / BankReconciliationResponse
  BankChargeRequest
  BankBookRow / BankBookResponse
  ChequeCreateRequest / ChequeStatusUpdateRequest / ChequeResponse

Spec ref: specs/008-accounting-finance/tasks.md T184
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Bank accounts
# ---------------------------------------------------------------------------


class BankAccountCreateRequest(AccountingBaseSchema):
    bank_name: str = Field(..., min_length=1, max_length=200)
    branch_name: str | None = None
    account_number: str = Field(..., min_length=1, max_length=50)
    iban: str | None = None
    swift_bic: str | None = None
    currency_code: str = Field(..., min_length=3, max_length=3)
    gl_account_id: UUID
    opening_balance: Decimal = Decimal("0")
    opening_balance_date: date | None = None


class BankAccountUpdateRequest(AccountingBaseSchema):
    bank_name: str | None = None
    branch_name: str | None = None
    iban: str | None = None
    swift_bic: str | None = None
    is_active: bool | None = None


class BankAccountResponse(AccountingBaseSchema):
    id: UUID
    bank_name: str
    branch_name: str | None = None
    account_number: str
    iban: str | None = None
    swift_bic: str | None = None
    currency_code: str
    gl_account_id: UUID
    opening_balance: Decimal
    opening_balance_date: date | None = None
    current_gl_balance: Decimal
    is_active: bool


# ---------------------------------------------------------------------------
# Bank transactions / transfers / deposits
# ---------------------------------------------------------------------------


class BankTransactionResponse(AccountingBaseSchema):
    id: UUID
    bank_account_id: UUID
    transaction_date: date
    transaction_type: str
    amount: Decimal
    reference: str | None = None
    description: str | None = None
    journal_entry_id: UUID | None = None
    is_reconciled: bool


class BankTransferRequest(AccountingBaseSchema):
    to_bank_account_id: UUID
    amount: Decimal = Field(..., gt=0)
    transfer_date: date
    reference: str | None = None
    description: str | None = None


class BankTransferResponse(AccountingBaseSchema):
    from_transaction: BankTransactionResponse
    to_transaction: BankTransactionResponse
    journal_entry_id: UUID


class BankDepositRequest(AccountingBaseSchema):
    total_amount: Decimal = Field(..., gt=0)
    contra_account_id: UUID
    deposit_date: date
    reference: str | None = None
    description: str | None = None


class BankChargeRequest(AccountingBaseSchema):
    amount: Decimal = Field(..., gt=0)
    expense_account_id: UUID
    charge_date: date
    description: str | None = None


# ---------------------------------------------------------------------------
# Bank book
# ---------------------------------------------------------------------------


class BankBookRow(AccountingBaseSchema):
    id: UUID
    transaction_date: date
    transaction_type: str
    amount: Decimal
    reference: str | None = None
    description: str | None = None
    is_reconciled: bool


class BankBookResponse(AccountingBaseSchema):
    bank_account_id: UUID
    from_date: date
    to_date: date
    opening_balance: Decimal
    transactions: list[BankBookRow]
    closing_balance: Decimal


# ---------------------------------------------------------------------------
# Statement import / reconciliation
# ---------------------------------------------------------------------------


class BankStatementLineImport(AccountingBaseSchema):
    statement_date: date
    value_date: date | None = None
    amount: Decimal
    reference: str | None = None
    description: str | None = None
    transaction_type: str | None = None


class BankStatementImportRequest(AccountingBaseSchema):
    lines: list[BankStatementLineImport] = Field(..., min_length=1)


class BankStatementLineResponse(AccountingBaseSchema):
    id: UUID
    bank_account_id: UUID
    statement_date: date
    value_date: date | None = None
    amount: Decimal
    reference: str | None = None
    description: str | None = None
    transaction_type: str | None = None
    is_matched: bool


class ReconciliationStartRequest(AccountingBaseSchema):
    statement_date: date
    statement_closing_balance: Decimal


class ReconciliationMatchRequest(AccountingBaseSchema):
    bank_transaction_id: UUID
    statement_line_id: UUID


class BankReconciliationMatchResponse(AccountingBaseSchema):
    id: UUID
    reconciliation_id: UUID
    bank_transaction_id: UUID
    statement_line_id: UUID
    match_type: str
    matched_at: datetime


class BankReconciliationResponse(AccountingBaseSchema):
    id: UUID
    bank_account_id: UUID
    statement_date: date
    statement_closing_balance: Decimal
    gl_balance_at_date: Decimal | None = None
    difference: Decimal
    status: str
    completed_at: datetime | None = None
    completed_by_user_id: UUID | None = None


class AutoMatchResultResponse(AccountingBaseSchema):
    matched_count: int
    unmatched_count: int


class ReconciliationReportResponse(AccountingBaseSchema):
    reconciliation: BankReconciliationResponse
    matches: list[BankReconciliationMatchResponse]
    unmatched_transactions: list[BankTransactionResponse]
    unmatched_statement_lines: list[BankStatementLineResponse]


# ---------------------------------------------------------------------------
# Cheques
# ---------------------------------------------------------------------------


class ChequeCreateRequest(AccountingBaseSchema):
    bank_account_id: UUID
    cheque_number: str = Field(..., min_length=1, max_length=30)
    payee_name: str = Field(..., min_length=1, max_length=200)
    cheque_date: date
    amount: Decimal = Field(..., gt=0)


class ChequeStatusUpdateRequest(AccountingBaseSchema):
    status: str = Field(..., pattern="^(PRESENTED|CLEARED|CANCELLED|STALE)$")
    cancel_reason: str | None = None
    bank_statement_line_id: UUID | None = None


class ChequeResponse(AccountingBaseSchema):
    id: UUID
    bank_account_id: UUID
    cheque_number: str
    payee_name: str
    cheque_date: date
    amount: Decimal
    status: str
    bank_transaction_id: UUID | None = None
    bank_statement_line_id: UUID | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None


__all__ = [
    "AutoMatchResultResponse",
    "BankAccountCreateRequest",
    "BankAccountResponse",
    "BankAccountUpdateRequest",
    "BankBookResponse",
    "BankBookRow",
    "BankChargeRequest",
    "BankDepositRequest",
    "BankReconciliationMatchResponse",
    "BankReconciliationResponse",
    "BankStatementImportRequest",
    "BankStatementLineImport",
    "BankStatementLineResponse",
    "BankTransactionResponse",
    "BankTransferRequest",
    "BankTransferResponse",
    "ChequeCreateRequest",
    "ChequeResponse",
    "ChequeStatusUpdateRequest",
    "ReconciliationMatchRequest",
    "ReconciliationReportResponse",
    "ReconciliationStartRequest",
]

"""Pydantic v2 schemas for General Ledger — Phase 4 (CRITICAL).

  PostingRequest / PostingLineRequest
  PostingResult
  JournalEntryResponse / JournalEntryDetailResponse / JournalLineResponse
  SubmitRequest is not needed (no body) — RejectRequest / ReverseRequest carry a reason
  GLReportRow / GLReportRequest

Spec ref: specs/008-accounting-finance/tasks.md T100
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Posting request / result
# ---------------------------------------------------------------------------


class PostingLineRequest(AccountingBaseSchema):
    """A single line within a journal posting request."""

    account_id: UUID
    debit_amount: Decimal = Field(Decimal("0"), ge=0)
    credit_amount: Decimal = Field(Decimal("0"), ge=0)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(None, gt=0)
    cost_center_id: UUID | None = None
    department_id: UUID | None = None
    project_id: UUID | None = None
    description: str | None = None
    reference: str | None = None


class PostingRequest(AccountingBaseSchema):
    """Request body for creating a journal entry (``POST /accounting/journals``)."""

    journal_type: str = Field(
        ...,
        pattern="^(STANDARD|ADJUSTING|REVERSING|RECURRING_INSTANCE|OPENING_BALANCE|"
        "CLOSING|AUTOMATED)$",
    )
    posting_source: str = Field(
        "MANUAL",
        pattern="^(MANUAL|SALES|PURCHASE|INVENTORY|BANK|CASH|PAYMENT|RECURRING|SYSTEM)$",
    )
    posting_date: date
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    exchange_rate: Decimal = Field(Decimal("1"), gt=0)
    reference: str | None = None
    description: str | None = None
    notes: str | None = None
    source_document_type: str | None = None
    source_document_id: UUID | None = None
    lines: list[PostingLineRequest] = Field(..., min_length=2)


class PostingResult(AccountingBaseSchema):
    """Response schema for a successful posting."""

    journal_entry_id: UUID
    journal_number: str
    posted_at: datetime


class RejectRequest(AccountingBaseSchema):
    """Request body for rejecting a submitted journal entry."""

    rejection_reason: str = Field(..., min_length=1, max_length=500)


class ReverseRequest(AccountingBaseSchema):
    """Request body for reversing a posted journal entry."""

    reason: str | None = Field(None, max_length=500)


class BatchPostingRequest(AccountingBaseSchema):
    """Request body for posting multiple journal entries atomically (Phase 5, T122)."""

    journal_entry_ids: list[UUID] = Field(..., min_length=1)


class BatchPostingResponse(AccountingBaseSchema):
    """Response schema for a successful batch posting — all entries posted."""

    results: list[PostingResult]


# ---------------------------------------------------------------------------
# Journal entry / line responses
# ---------------------------------------------------------------------------


class JournalLineResponse(AccountingBaseSchema):
    """Response schema for a single GL line."""

    id: UUID
    line_number: int
    account_id: UUID
    account_code: str
    debit_amount: Decimal
    credit_amount: Decimal
    debit_amount_base: Decimal
    credit_amount_base: Decimal
    currency_code: str
    exchange_rate: Decimal
    cost_center_id: UUID | None
    department_id: UUID | None
    project_id: UUID | None
    description: str | None
    reference: str | None


class JournalEntryResponse(AccountingBaseSchema):
    """Response schema for a journal entry (list view — no nested lines)."""

    id: UUID
    company_id: UUID
    journal_number: str | None
    journal_type: str
    posting_source: str
    posting_date: date
    fiscal_period_id: UUID | None
    fiscal_year_id: UUID | None
    reference: str | None
    description: str | None
    notes: str | None
    status: str
    reversal_of_journal_id: UUID | None
    is_reversal: bool
    posted_at: datetime | None
    posted_by_user_id: UUID | None
    source_document_type: str | None
    source_document_id: UUID | None
    currency_code: str
    exchange_rate: Decimal
    total_debit_base: Decimal
    total_credit_base: Decimal
    is_balanced: bool | None


class JournalEntryDetailResponse(JournalEntryResponse):
    """Response schema for a journal entry detail view — includes lines."""

    lines: list[JournalLineResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GL report
# ---------------------------------------------------------------------------


class GLReportRequest(AccountingBaseSchema):
    """Filter parameters for the GL report / detail query."""

    account_id: UUID | None = None
    cost_center_id: UUID | None = None
    fiscal_period_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class GLReportRow(AccountingBaseSchema):
    """A single GL report row (posted line + parent-entry context)."""

    journal_entry_id: UUID
    journal_number: str | None
    posting_date: date
    account_id: UUID
    account_code: str
    line_number: int
    debit_amount: Decimal
    credit_amount: Decimal
    description: str | None
    reference: str | None
    source_document_type: str | None
    source_document_id: UUID | None
    cost_center_id: UUID | None


# ---------------------------------------------------------------------------
# Audit trail (Phase 14, T279)
# ---------------------------------------------------------------------------


class AuditLogEntryResponse(AccountingBaseSchema):
    """A single immutable audit-trail record."""

    id: UUID
    company_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor_user_id: UUID | None
    occurred_at: datetime
    before_state: dict | None
    after_state: dict | None
    reason: str | None


class AuditLogListResponse(AccountingBaseSchema):
    entries: list[AuditLogEntryResponse]
    total: int
    skip: int
    limit: int

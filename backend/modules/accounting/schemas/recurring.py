"""Pydantic v2 schemas for Recurring Journal Entries — Phase 5.

  RecurringTemplateLineRequest / RecurringTemplateLineResponse
  RecurringTemplateCreateRequest / RecurringTemplateUpdateRequest / RecurringTemplateResponse
  RecurringInstanceResponse

Note: ``JournalReversalRequest`` is intentionally NOT duplicated here —
reversal already has a request schema (``ReverseRequest`` in schemas/gl.py)
from Phase 4, where ``PostingEngine.reverse()`` and its API endpoint were
implemented. See services/journal_service.py's module docstring for why
Phase 5 delegates to that existing implementation instead of rebuilding it.

Spec ref: specs/008-accounting-finance/tasks.md T123
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Template lines
# ---------------------------------------------------------------------------


class RecurringTemplateLineRequest(AccountingBaseSchema):
    """A single line within a recurring journal template creation request."""

    account_id: UUID
    debit_amount: Decimal = Field(Decimal("0"), ge=0)
    credit_amount: Decimal = Field(Decimal("0"), ge=0)
    description: str | None = None
    cost_center_id: UUID | None = None


class RecurringTemplateLineResponse(AccountingBaseSchema):
    """Response schema for a recurring journal template line."""

    id: UUID
    line_number: int
    account_id: UUID
    debit_amount: Decimal
    credit_amount: Decimal
    description: str | None
    cost_center_id: UUID | None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class RecurringTemplateCreateRequest(AccountingBaseSchema):
    """Request body for creating a recurring journal template."""

    template_name: str = Field(..., min_length=1, max_length=200)
    frequency: str = Field(..., pattern="^(DAILY|WEEKLY|MONTHLY|QUARTERLY|ANNUALLY)$")
    start_date: date
    end_date: date | None = None
    auto_post: bool = False
    approval_required: bool = False
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    reference: str | None = None
    description: str | None = None
    lines: list[RecurringTemplateLineRequest] = Field(..., min_length=2)


class RecurringTemplateUpdateRequest(AccountingBaseSchema):
    """Request body for updating a recurring journal template.

    Schedule (frequency/start_date/next_run_date) and lines are immutable
    once created — only the fields below can be changed; deactivate and
    create a new template for schedule changes.
    """

    template_name: str | None = Field(None, min_length=1, max_length=200)
    end_date: date | None = None
    auto_post: bool | None = None
    approval_required: bool | None = None
    reference: str | None = None
    description: str | None = None


class RecurringTemplateResponse(AccountingBaseSchema):
    """Response schema for a recurring journal template."""

    id: UUID
    company_id: UUID
    template_name: str
    frequency: str
    start_date: date
    end_date: date | None
    next_run_date: date
    is_active: bool
    auto_post: bool
    approval_required: bool
    currency_code: str
    reference: str | None
    description: str | None


class RecurringTemplateDetailResponse(RecurringTemplateResponse):
    """Response schema for a recurring journal template detail view — includes lines."""

    lines: list[RecurringTemplateLineResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Instances (execution history)
# ---------------------------------------------------------------------------


class RecurringInstanceResponse(AccountingBaseSchema):
    """Response schema for one recurring template execution record."""

    id: UUID
    template_id: UUID
    journal_entry_id: UUID | None
    execution_date: date
    status: str
    error_message: str | None

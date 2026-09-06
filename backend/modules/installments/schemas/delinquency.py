"""Pydantic schemas for late charge/waiver (tasks.md T144).

No dedicated endpoints exist yet in this phase (T145 — late-charge
application/waiver are invoked internally, by the optional background
reminder job (Phase 12) or a service-level admin action) — these schemas
describe the read/response shape ``InstallmentDelinquencyService``
already produces, ready for that future wiring without a later schema
rewrite.

Spec ref: specs/010-installments/data-model.md "InstallmentLateCharge";
specs/010-installments/spec.md FR-INST-170-173.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentLateChargeRead(InstallmentsBaseSchema):
    """Response body describing one posted (or waived) late charge."""

    id: UUID
    contract_id: UUID
    schedule_line_id: UUID
    charge_amount: Decimal
    charged_at: datetime
    overdue_occurrence_date: date
    accounting_journal_entry_id: UUID | None = None
    accounting_ar_transaction_id: UUID | None = None
    waived_at: datetime | None = None
    waived_by: UUID | None = None
    waived_reason: str | None = None


class InstallmentLateChargeWaiveRequest(InstallmentsBaseSchema):
    """Request body for waiving a late charge — ``reason`` is mandatory
    (FR-INST-173)."""

    reason: str = Field(..., min_length=1)


class InstallmentDueStateRead(InstallmentsBaseSchema):
    """Response body describing one schedule line's derived due-state
    (T138) — computed at read time, never persisted."""

    schedule_line_id: UUID
    state: str
    outstanding_amount: Decimal
    days_overdue: int

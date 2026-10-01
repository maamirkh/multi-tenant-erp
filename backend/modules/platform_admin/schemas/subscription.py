"""Subscription Pydantic schemas — request/response models for the
tenant subscription routes (T114).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class AssignSubscriptionRequest(BaseModel):
    """Request body for ``POST /platform/tenants/{companyId}/subscription``.

    ``acknowledged`` must be explicitly set to ``true`` to proceed with a
    change that would place current usage above the target plan's limits
    (FR-9A-165) — defaults to ``False`` so a conflict is never silently
    bypassed.
    """

    model_config = ConfigDict()

    plan_id: UUID
    effective_date: date
    end_date: date | None = Field(
        None,
        description="Validation-only input (spec Edge Case #16): rejected "
        "if before effective_date. Not persisted as a scheduled "
        "termination — ending a Subscription happens via a later "
        "subscription change.",
    )
    reason: str | None = Field(None, max_length=1000)
    acknowledged: bool = False

    @field_validator("end_date")
    @classmethod
    def _end_date_not_before_effective_date(
        cls, value: date | None, info: ValidationInfo
    ) -> date | None:
        effective_date = info.data.get("effective_date")
        if value is not None and effective_date is not None and value < effective_date:
            raise ValueError("end_date must not be before effective_date.")
        return value


class SubscriptionResponse(BaseModel):
    """A single Subscription record (current or historical)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    plan_id: UUID
    status: str
    effective_date: date
    ended_at: datetime | None
    actor_id: UUID
    reason: str | None
    created_at: datetime


class SubscriptionHistoryResponse(BaseModel):
    """Response body for ``GET /platform/tenants/{companyId}/subscription``
    — the current active Subscription (if any) plus its full history,
    newest first."""

    model_config = ConfigDict()

    current: SubscriptionResponse | None
    history: list[SubscriptionResponse]

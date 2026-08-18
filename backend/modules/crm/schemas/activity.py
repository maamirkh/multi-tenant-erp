"""Pydantic schemas for the Activity aggregate — Phase 6.

``ActivityCreate`` enforces two rules at the schema layer (defense in
depth, alongside the identical DB ``CHECK`` from Phase 2's
``ck_crm_activities_has_relation``): BR-006 (at least one of lead_id/
customer_id/opportunity_id) and spec.md §29's "due_date required for
TASK/FOLLOW_UP" rule. ``completed_at`` is absent from every write schema —
it is set only by the dedicated ``complete()`` transition, never
client-supplied (spec.md §19.2).

Spec ref: specs/009-crm/spec.md §19, §29, §37.6, §38.5.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from modules.crm.constants import ACTIVITY_PRIORITIES, ACTIVITY_STATUSES, ACTIVITY_TYPES
from modules.crm.schemas.base import CrmBaseSchema

_DUE_DATE_REQUIRED_TYPES = frozenset({"TASK", "FOLLOW_UP"})


class ActivityCreate(CrmBaseSchema):
    """Request body for logging a new Activity (spec.md §19.1)."""

    activity_type: str
    subject: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    priority: str = "MEDIUM"
    due_date: datetime | None = None
    assigned_to: UUID
    lead_id: UUID | None = None
    customer_id: UUID | None = None
    opportunity_id: UUID | None = None

    @model_validator(mode="after")
    def validate_type_relation_and_due_date(self) -> ActivityCreate:
        if self.activity_type not in ACTIVITY_TYPES:
            raise ValueError(f"activity_type must be one of {sorted(ACTIVITY_TYPES)}")
        if self.priority not in ACTIVITY_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(ACTIVITY_PRIORITIES)}")
        if not (self.lead_id or self.customer_id or self.opportunity_id):
            raise ValueError(
                "At least one of lead_id, customer_id, or opportunity_id is required."
            )
        if self.activity_type in _DUE_DATE_REQUIRED_TYPES and self.due_date is None:
            raise ValueError("due_date is required for TASK and FOLLOW_UP activities.")
        return self


class ActivityUpdate(CrmBaseSchema):
    """Request body for updating an Activity. All fields optional."""

    subject: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    assigned_to: UUID | None = None

    @model_validator(mode="after")
    def validate_status_and_priority(self) -> ActivityUpdate:
        if self.status is not None and self.status not in ACTIVITY_STATUSES:
            raise ValueError(f"status must be one of {sorted(ACTIVITY_STATUSES)}")
        if self.priority is not None and self.priority not in ACTIVITY_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(ACTIVITY_PRIORITIES)}")
        return self


class ActivityRead(CrmBaseSchema):
    """Response body for an Activity."""

    id: UUID
    company_id: UUID
    activity_type: str
    subject: str
    description: str | None
    status: str
    priority: str
    due_date: datetime | None
    completed_at: datetime | None
    assigned_to: UUID
    lead_id: UUID | None
    customer_id: UUID | None
    opportunity_id: UUID | None
    created_at: datetime
    updated_at: datetime

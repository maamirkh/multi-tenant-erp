"""Pydantic schemas for the Opportunity aggregate — Phase 5.

``OpportunityRead.weighted_value`` is a Pydantic v2 ``@computed_field``,
never a plain field — the ORM model has no such column at all (BR-010,
plan.md §6.5); it is derived here at serialization time from ``value``
and ``probability``, matching spec.md §17.1's formula exactly.

``owner_id``, ``pipeline_id``, and ``stage_id`` are intentionally absent
from ``OpportunityUpdate`` — reassignment goes through the dedicated
``assign()``/``change_stage()`` endpoints, which perform validation a
plain field update cannot (active-membership check, INV-004). ``customer_id``
is absent everywhere except ``OpportunityCreate`` — it is immutable after
creation (BR-002).

Spec ref: specs/009-crm/spec.md §17, §37.5, §38.4.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, computed_field

from modules.crm.schemas.base import CrmBaseSchema


class OpportunityCreate(CrmBaseSchema):
    """Request body for creating an Opportunity directly against an
    existing Customer (spec.md §17.1) — independent of Lead conversion."""

    name: str = Field(..., min_length=1, max_length=200)
    customer_id: UUID
    owner_id: UUID
    pipeline_id: UUID
    stage_id: UUID
    value: Decimal = Field(default=Decimal("0"), ge=0)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    probability: int | None = Field(None, ge=0, le=100)
    expected_close_date: date | None = None
    description: str | None = None


class OpportunityUpdate(CrmBaseSchema):
    """Request body for updating an Opportunity's metadata. Rejected (409)
    once the Opportunity is WON or LOST (BR-003).

    ``quotation_id`` is the Opportunity -> Quotation link-back (spec.md
    §21.1, plan.md §15.2): the frontend creates the Quotation directly in
    Sales, then PATCHes the resulting ``quotation_id`` back here as a pure
    CRM-side field update — CRM never creates the Quotation row itself.
    """

    name: str | None = Field(None, min_length=1, max_length=200)
    value: Decimal | None = Field(None, ge=0)
    probability: int | None = Field(None, ge=0, le=100)
    expected_close_date: date | None = None
    description: str | None = None
    quotation_id: UUID | None = None


class OpportunityAssignRequest(CrmBaseSchema):
    """Request body for POST /crm/opportunities/{id}/assign."""

    owner_id: UUID


class OpportunityStageChangeRequest(CrmBaseSchema):
    """Request body for POST /crm/opportunities/{id}/stage."""

    stage_id: UUID
    probability: int | None = Field(
        None, ge=0, le=100, description="Override; defaults to the stage's own"
    )


class OpportunityLoseRequest(CrmBaseSchema):
    """Request body for POST /crm/opportunities/{id}/lose."""

    lost_reason: str = Field(..., min_length=1)


class OpportunityRead(CrmBaseSchema):
    """Response body for an Opportunity."""

    id: UUID
    company_id: UUID
    name: str
    customer_id: UUID
    owner_id: UUID
    pipeline_id: UUID
    stage_id: UUID
    value: Decimal
    currency_code: str
    probability: int
    expected_close_date: date | None
    source_lead_id: UUID | None
    description: str | None
    status: str
    lost_reason: str | None
    won_at: datetime | None
    lost_at: datetime | None
    quotation_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def weighted_value(self) -> Decimal:
        """``value * probability / 100`` (spec.md §17.1, BR-010) — always
        computed here, never accepted as input, never stored."""
        return (self.value * self.probability / Decimal(100)).quantize(Decimal("0.01"))

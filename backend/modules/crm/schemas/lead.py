"""Pydantic schemas for the Lead and LeadSource aggregates — Phase 3.

Covers:
  - LeadSource (create, update, read)
  - Lead (create, update, read, assign)

``LeadCreate`` enforces spec.md §14.3's cross-field rules at the schema
layer (before the service is even called): at least one of
first_name/last_name/lead_company_name, and at least one of email/phone.
This is defense-in-depth alongside the identical ``CHECK`` constraints
already declared on the ``crm_leads`` table (Phase 2).

``converted_customer_id``, ``converted_opportunity_id``, ``converted_at``,
and ``version`` are intentionally absent from every write schema — they
are server-only fields, never client-settable (spec.md §46 SEC-07).
``owner_id`` is likewise absent from ``LeadUpdate``; reassignment only
happens through the dedicated ``assign()`` endpoint, which performs active
-membership validation (spec.md §30.3) that a plain field update cannot.

Spec ref: specs/009-crm/spec.md §14, §37.1-37.2, §38.1-38.2.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from modules.crm.constants import LEAD_STATUSES
from modules.crm.schemas.base import CrmBaseSchema

# ---------------------------------------------------------------------------
# LeadSource schemas
# ---------------------------------------------------------------------------


class LeadSourceCreate(CrmBaseSchema):
    """Request body for creating a Lead Source."""

    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class LeadSourceUpdate(CrmBaseSchema):
    """Request body for updating a Lead Source. All fields optional."""

    code: str | None = Field(None, min_length=1, max_length=30)
    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class LeadSourceRead(CrmBaseSchema):
    """Response body for a Lead Source."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Lead schemas
# ---------------------------------------------------------------------------


def _validate_email(v: str | None) -> str | None:
    if v is not None and "@" not in v:
        raise ValueError("Invalid email address")
    return v


class LeadCreate(CrmBaseSchema):
    """Request body for capturing a new Lead (spec.md §14.1)."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    lead_company_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)
    mobile: str | None = Field(None, max_length=30)
    address_line1: str | None = Field(None, max_length=300)
    address_line2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country_code: str | None = Field(None, max_length=2)
    source_id: UUID | None = None
    score: int | None = Field(None, ge=0, le=100)
    notes: str | None = None
    next_follow_up_date: date | None = None
    qualification_notes: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _validate_email(v)

    @model_validator(mode="after")
    def validate_identity_and_contact(self) -> LeadCreate:
        if not (self.first_name or self.last_name or self.lead_company_name):
            raise ValueError(
                "At least one of first_name, last_name, or lead_company_name "
                "is required."
            )
        if not (self.email or self.phone):
            raise ValueError("At least one of email or phone is required.")
        return self


class LeadUpdate(CrmBaseSchema):
    """Request body for updating a Lead's fields and/or status.

    Qualify/disqualify are exposed here via the ``status`` field rather than
    as separate endpoints (spec.md §15) — the service layer validates the
    transition against spec.md §14.2's state machine.
    """

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    lead_company_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)
    mobile: str | None = Field(None, max_length=30)
    address_line1: str | None = Field(None, max_length=300)
    address_line2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country_code: str | None = Field(None, max_length=2)
    source_id: UUID | None = None
    status: str | None = None
    score: int | None = Field(None, ge=0, le=100)
    notes: str | None = None
    last_contact_date: date | None = None
    next_follow_up_date: date | None = None
    qualification_notes: str | None = None
    disqualification_reason: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _validate_email(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in LEAD_STATUSES:
            raise ValueError(f"status must be one of {sorted(LEAD_STATUSES)}")
        return v


class LeadAssignRequest(CrmBaseSchema):
    """Request body for POST /crm/leads/{id}/assign."""

    owner_id: UUID


class ConversionResult(CrmBaseSchema):
    """Response body for POST /crm/leads/{id}/convert (spec.md §16, §38.1)."""

    lead_id: UUID
    customer_id: UUID
    opportunity_id: UUID
    customer_matched: bool


class LeadRead(CrmBaseSchema):
    """Response body for a Lead."""

    id: UUID
    company_id: UUID
    first_name: str | None
    last_name: str | None
    lead_company_name: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country_code: str | None
    source_id: UUID | None
    status: str
    score: int | None
    owner_id: UUID | None
    notes: str | None
    last_contact_date: date | None
    next_follow_up_date: date | None
    qualification_notes: str | None
    disqualification_reason: str | None
    converted_customer_id: UUID | None
    converted_opportunity_id: UUID | None
    converted_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime

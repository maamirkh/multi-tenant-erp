"""Tenant lifecycle Pydantic schemas — request/response models for the
suspend/reactivate routes (T090).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TenantLifecycleActionRequest(BaseModel):
    """Request body for both ``POST /tenants/{companyId}/suspend`` and
    ``POST /tenants/{companyId}/reactivate`` — a mandatory, non-blank
    reason, validated server-side before any state change."""

    model_config = ConfigDict()

    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _reason_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank.")
        return value


class TenantLifecycleResponse(BaseModel):
    """Response body reflecting a tenant's lifecycle state after a
    suspend/reactivate transition."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    pre_suspension_status: str | None
    access_invalidated_at: datetime | None

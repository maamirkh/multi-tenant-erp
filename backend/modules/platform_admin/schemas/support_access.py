"""Support-access Pydantic schemas — request/response models for the
Phase 12 support-access routes (T162).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InitiateSupportAccessRequest(BaseModel):
    """Request body for ``POST /platform/tenants/{companyId}/support-access``.

    No client-supplied ``expires_at`` — the OpenAPI contract declares
    only ``reason``; the grant window is a server-determined policy
    (``SupportAccessService.DEFAULT_GRANT_DURATION_HOURS``).
    """

    model_config = ConfigDict()

    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _reason_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank.")
        return value


class SupportAccessGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform_administrator_id: UUID
    company_id: UUID
    reason: str
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None
    ended_by: UUID | None
    status: str

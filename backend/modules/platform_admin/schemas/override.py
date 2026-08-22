"""Entitlement/quota override Pydantic schemas — request/response models
for the Phase 11 override routes (T157).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GrantEntitlementOverrideRequest(BaseModel):
    """Request body for ``POST /platform/tenants/{companyId}/entitlement-overrides``."""

    model_config = ConfigDict()

    capability_key: str
    reason: str = Field(..., min_length=1, max_length=1000)
    expires_at: datetime | None = None


class EntitlementOverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    capability_key: str
    reason: str
    actor_id: UUID
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    is_active: bool


class GrantQuotaOverrideRequest(BaseModel):
    """Request body for ``POST /platform/tenants/{companyId}/quota-overrides``."""

    model_config = ConfigDict()

    quota_key: str
    override_limit: Decimal | None = Field(
        None, description="NULL means an unlimited override."
    )
    reason: str = Field(..., min_length=1, max_length=1000)
    expires_at: datetime | None = None


class QuotaOverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    quota_key: str
    override_limit: Decimal | None
    reason: str
    actor_id: UUID
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    is_active: bool

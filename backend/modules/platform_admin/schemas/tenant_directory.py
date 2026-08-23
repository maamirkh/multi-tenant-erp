"""Tenant directory / 360° detail / lifecycle-history Pydantic schemas —
response models for the Phase 13 tenant-inspection routes (T167-T169).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from modules.platform_admin.schemas.entitlement import CapabilityEntitlementResponse
from modules.platform_admin.schemas.quota import QuotaStatusResponse
from modules.platform_admin.schemas.subscription import SubscriptionResponse


class TenantSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_name: str
    slug: str
    status: str
    country: str | None
    email: str
    created_at: datetime


class PlanSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    status: str


class AuditEventSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    actor_platform_administrator_id: UUID | None
    target_type: str
    reason: str | None
    created_at: datetime


class LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    actor_platform_administrator_id: UUID | None
    reason: str | None
    created_at: datetime


class TenantLifecycleHistoryResponse(BaseModel):
    company_id: str
    events: list[LifecycleEventResponse]


class TenantDetailResponse(BaseModel):
    id: UUID
    legal_name: str
    slug: str
    status: str
    pre_suspension_status: str | None
    access_invalidated_at: datetime | None
    email: str
    country: str | None
    created_at: datetime
    plan: PlanSummaryResponse | None
    subscription: SubscriptionResponse | None
    entitlements: list[CapabilityEntitlementResponse]
    quotas: list[QuotaStatusResponse]
    user_count: int
    lifecycle_history: list[LifecycleEventResponse]
    recent_audit_events: list[AuditEventSummaryResponse]

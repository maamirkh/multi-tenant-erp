"""Entitlement response schemas (T123).

UX-only read surface — never the security boundary (plan.md §13.1). The
authoritative enforcement point is the ``require_capability_entitled``
mount-level dependency (T122), which calls the same
``PlatformEntitlementService`` this endpoint reads from.
"""

from __future__ import annotations

from pydantic import BaseModel


class CapabilityEntitlementResponse(BaseModel):
    capability_key: str
    available: bool
    reason: str


class TenantEntitlementsResponse(BaseModel):
    company_id: str
    entitlements: list[CapabilityEntitlementResponse]

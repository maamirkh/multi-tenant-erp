"""Effective quota status response schemas — GET
``/platform/tenants/{companyId}/quotas`` (T157).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class QuotaStatusResponse(BaseModel):
    quota_key: str
    state: str
    limit: Decimal | None
    current_usage: Decimal | None
    enforcement_style: str | None


class TenantQuotasResponse(BaseModel):
    company_id: str
    quotas: list[QuotaStatusResponse]

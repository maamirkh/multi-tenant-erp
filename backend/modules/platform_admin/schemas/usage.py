"""Usage record response schemas — GET
``/platform/tenants/{companyId}/usage`` (T157).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    metric_key: str
    quantity: Decimal
    period_start: datetime
    period_end: datetime
    source: str
    recorded_at: datetime


class TenantUsageResponse(BaseModel):
    company_id: str
    records: list[UsageRecordResponse]

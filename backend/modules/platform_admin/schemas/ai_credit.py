"""AI credit ledger Pydantic schemas — request/response models for the
Phase 11 AI-credit routes (T157, FR-9A-235).

The contract's `GET /tenants/{companyId}/ai-credits` summary is explicit:
"empty/'not yet active' until an AI capability exists" — `status` is a
derived UX signal (not a stored column) so a tenant's view honestly
distinguishes "no AI capability has ever been provisioned for anyone"
from "this tenant genuinely has a zero balance after real activity" is
not yet a distinction this phase's data can make (no AI capability
exists anywhere yet, data-model.md §19) — so `status` is simply
"not_yet_active" whenever the ledger is empty, "active" otherwise. A
documented Tasks-phase default, not fabricated from spec text — same
precedent as `quota_service.py`'s own `APPROACHING_THRESHOLD_RATIO`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdjustAiCreditsRequest(BaseModel):
    """Request body for ``POST /platform/tenants/{companyId}/ai-credits``."""

    model_config = ConfigDict()

    delta: Decimal = Field(
        ..., description="Signed — positive = credit grant, negative = usage debit."
    )
    reason: str = Field(..., min_length=1, max_length=1000)


class AiCreditLedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    delta: Decimal
    reason: str | None
    actor_platform_administrator_id: UUID | None
    provider: str | None
    model: str | None
    occurred_at: datetime


class TenantAiCreditsResponse(BaseModel):
    company_id: str
    status: Literal["not_yet_active", "active"]
    balance: Decimal
    entries: list[AiCreditLedgerEntryResponse]

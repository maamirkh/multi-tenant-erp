"""Pydantic schemas for Installments Configuration CRUD.

Spec ref: specs/010-installments/contracts/installments-api.yaml `/config`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentConfigurationUpsert(InstallmentsBaseSchema):
    """Request body for ``PUT /config`` — creates or replaces the
    tenant-level default configuration, or a branch-specific override
    when ``branch_id`` is supplied (the OpenAPI contract's single merged
    ``/config`` endpoint, parameterized by ``branch_id`` rather than a
    separate ``/config/branches/{branchId}`` path)."""

    branch_id: UUID | None = Field(
        None, description="NULL updates the company-level default row"
    )
    allowed_frequencies: list[str] = Field(..., min_length=1)
    min_term: int = Field(..., gt=0)
    max_term: int = Field(..., gt=0)
    min_down_payment_pct: Decimal | None = Field(None, ge=0, le=100)
    min_down_payment_amount: Decimal | None = Field(None, ge=0)
    max_financed_amount: Decimal | None = Field(None, ge=0)
    rounding_policy: str = "ROUND_HALF_UP"
    grace_period_days: int = Field(0, ge=0)
    late_charge_policy: dict | None = None
    early_settlement_policy: dict | None = None
    approval_threshold_amount: Decimal | None = Field(None, ge=0)
    backdating_allowed: bool = False
    backdating_max_days: int | None = Field(None, ge=0)
    cancellation_policy: dict | None = None
    default_policy: dict | None = None
    writeoff_requires_permission: bool = True
    cure_enabled: bool = False
    eligibility_rules: dict | None = None


class InstallmentConfigurationRead(InstallmentsBaseSchema):
    """Response body for the effective configuration."""

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    allowed_frequencies: list[str]
    min_term: int
    max_term: int
    min_down_payment_pct: Decimal | None
    min_down_payment_amount: Decimal | None
    max_financed_amount: Decimal | None
    rounding_policy: str
    grace_period_days: int
    late_charge_policy: dict | None
    early_settlement_policy: dict | None
    approval_threshold_amount: Decimal | None
    backdating_allowed: bool
    backdating_max_days: int | None
    cancellation_policy: dict | None
    default_policy: dict | None
    writeoff_requires_permission: bool
    cure_enabled: bool
    eligibility_rules: dict | None
    created_at: datetime
    updated_at: datetime

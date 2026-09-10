"""Pydantic schemas for Installments Plan Template CRUD.

Spec ref: specs/010-installments/contracts/installments-api.yaml `/plans`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentPlanTemplateCreate(InstallmentsBaseSchema):
    """Request body for ``POST /plans``."""

    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True
    frequency: str
    installment_count: int = Field(..., gt=0)
    down_payment_rule: dict[str, Any]
    markup_rule: dict[str, Any] | None = None
    grace_period_days: int | None = Field(None, ge=0)
    late_charge_policy: dict[str, Any] | None = None
    early_settlement_rule: dict[str, Any] | None = None
    applicable_product_ids: list[str] | None = None
    requires_approval: bool = False


class InstallmentPlanTemplateUpdate(InstallmentsBaseSchema):
    """Request body for ``PATCH /plans/{planId}``. All fields optional —
    never mutates contracts already created from this template
    (BR-INST-009)."""

    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    frequency: str | None = None
    installment_count: int | None = Field(None, gt=0)
    down_payment_rule: dict[str, Any] | None = None
    markup_rule: dict[str, Any] | None = None
    grace_period_days: int | None = Field(None, ge=0)
    late_charge_policy: dict[str, Any] | None = None
    early_settlement_rule: dict[str, Any] | None = None
    applicable_product_ids: list[str] | None = None
    requires_approval: bool | None = None


class InstallmentPlanTemplateRead(InstallmentsBaseSchema):
    """Response body for a Plan Template."""

    id: UUID
    company_id: UUID
    name: str
    description: str | None
    is_active: bool
    frequency: str
    installment_count: int
    down_payment_rule: dict[str, Any]
    markup_rule: dict[str, Any] | None
    grace_period_days: int | None
    late_charge_policy: dict[str, Any] | None
    early_settlement_rule: dict[str, Any] | None
    applicable_product_ids: list[str] | None
    requires_approval: bool
    created_at: datetime
    updated_at: datetime

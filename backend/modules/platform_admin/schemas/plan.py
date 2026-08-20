"""Plan Pydantic schemas — request/response models for the plan routes
(T114). `code`/`name` are configuration-driven values supplied by the
caller, never hardcoded product names (FR-9A-151).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreatePlanRequest(BaseModel):
    """Request body for ``POST /platform/plans``. Always creates a
    ``draft`` Plan — no ``status`` field is accepted here."""

    model_config = ConfigDict()

    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(None, max_length=10000)
    billing_cycle_metadata: dict[str, Any] | None = None
    pricing_metadata: dict[str, Any] | None = None
    capability_map: dict[str, bool] | None = Field(
        None, description="Capability key -> allowed. Optional at creation."
    )
    reason: str | None = Field(None, max_length=1000)


class UpdatePlanRequest(BaseModel):
    """Request body for ``PATCH /platform/plans/{planId}`` — a single
    combined operation per the contract ("Update/publish/retire a
    plan"). ``action`` selects the transition; ``update`` (the default)
    only ever touches fields, never `status`."""

    model_config = ConfigDict()

    action: Literal["update", "publish", "retire"] = "update"
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=10000)
    is_commercially_available: bool | None = None
    billing_cycle_metadata: dict[str, Any] | None = None
    pricing_metadata: dict[str, Any] | None = None
    capability_map: dict[str, bool] | None = None
    reason: str | None = Field(None, max_length=1000)


class PlanResponse(BaseModel):
    """Response body for a single Plan, including its capability
    ceiling."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    status: str
    description: str | None
    is_commercially_available: bool
    billing_cycle_metadata: dict[str, Any] | None
    pricing_metadata: dict[str, Any] | None
    capability_map: dict[str, bool] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

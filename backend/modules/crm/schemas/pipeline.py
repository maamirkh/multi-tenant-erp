"""Pydantic schemas for the Pipeline and PipelineStage aggregates — Phase 5.

Spec ref: specs/009-crm/spec.md §18, §37.3-37.4, §38.3.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from modules.crm.schemas.base import CrmBaseSchema

# ---------------------------------------------------------------------------
# Pipeline schemas
# ---------------------------------------------------------------------------


class PipelineCreate(CrmBaseSchema):
    """Request body for creating a Pipeline."""

    name: str = Field(..., min_length=1, max_length=100)
    is_default: bool = False
    is_active: bool = True


class PipelineUpdate(CrmBaseSchema):
    """Request body for updating a Pipeline. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100)
    is_default: bool | None = None
    is_active: bool | None = None


class PipelineRead(CrmBaseSchema):
    """Response body for a Pipeline."""

    id: UUID
    company_id: UUID
    name: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# PipelineStage schemas
# ---------------------------------------------------------------------------


class PipelineStageCreate(CrmBaseSchema):
    """Request body for creating a Pipeline Stage."""

    name: str = Field(..., min_length=1, max_length=100)
    sequence: int = Field(..., ge=1)
    probability: int = Field(..., ge=0, le=100)
    is_won_stage: bool = False
    is_lost_stage: bool = False
    is_active: bool = True


class PipelineStageUpdate(CrmBaseSchema):
    """Request body for updating a Pipeline Stage. All fields optional.

    Setting ``is_active=False`` is rejected (409) when any OPEN Opportunity
    currently occupies the stage (BR-007).
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    sequence: int | None = Field(None, ge=1)
    probability: int | None = Field(None, ge=0, le=100)
    is_won_stage: bool | None = None
    is_lost_stage: bool | None = None
    is_active: bool | None = None


class PipelineStageRead(CrmBaseSchema):
    """Response body for a Pipeline Stage."""

    id: UUID
    company_id: UUID
    pipeline_id: UUID
    name: str
    sequence: int
    probability: int
    is_won_stage: bool
    is_lost_stage: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

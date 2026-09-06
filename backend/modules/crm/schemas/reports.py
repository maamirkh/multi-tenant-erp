"""Pydantic response schemas for CRM reporting/dashboard — Phase 9.

Spec ref: specs/009-crm/spec.md §40 (Reporting Requirements), §41 (KPI
Requirements).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from modules.crm.schemas.base import CrmBaseSchema


class PipelineStageValue(CrmBaseSchema):
    stage_id: UUID
    value: Decimal


class PipelineOwnerValue(CrmBaseSchema):
    owner_id: UUID
    value: Decimal


class PipelineSourceValue(CrmBaseSchema):
    """``source_id`` is ``None`` for Opportunities not created via Lead
    conversion (no originating source to attribute)."""

    source_id: UUID | None
    value: Decimal


class PipelineReport(CrmBaseSchema):
    """spec.md §40.1."""

    value_by_stage: list[PipelineStageValue]
    value_by_owner: list[PipelineOwnerValue]
    value_by_source: list[PipelineSourceValue]
    won_value: Decimal
    lost_value: Decimal
    win_rate: Decimal | None
    avg_deal_size: Decimal | None
    avg_sales_cycle_days: Decimal | None
    date_from: date | None
    date_to: date | None


class LeadReport(CrmBaseSchema):
    """spec.md §40.2. Dict keys are string-coerced (UUID -> str, unset ->
    ``"none"``) since JSON object keys must be strings."""

    total_count: int
    count_by_status: dict[str, int]
    count_by_source: dict[str, int]
    conversion_rate: Decimal | None
    qualified_to_close_rate: Decimal | None
    date_from: date | None
    date_to: date | None


class ActivityReport(CrmBaseSchema):
    """spec.md §40.3."""

    completed_count: int
    completed_by_type: dict[str, int]
    overdue_count: int
    overdue_by_owner: dict[str, int]
    date_from: date | None
    date_to: date | None


class CrmDashboard(CrmBaseSchema):
    """spec.md §41 — the single-call dashboard KPI set, for the current
    calendar month unless the module is later extended with an explicit
    period parameter."""

    open_pipeline_value: Decimal
    weighted_pipeline_value: Decimal
    lead_count: int
    conversion_rate: Decimal | None
    win_rate: Decimal | None
    overdue_follow_up_count: int
    activities_completed: int
    period_from: date
    period_to: date

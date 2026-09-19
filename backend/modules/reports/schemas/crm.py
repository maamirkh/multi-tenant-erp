"""CRM report filter schemas (spec §17, plan.md Phase 2 §2.5). No
``branch_id`` anywhere (FR-RPT-091) — no CRM entity carries a branch
column. All 4 "Now" reports are aggregate-shaped; response *types* reuse
CRM's own already-tested Pydantic schemas verbatim
(``modules.crm.schemas.reports``), matching the Accounting adapter's DRY
reuse precedent — no new response models are declared here (T101)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class PipelineReportFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None


class LeadReportFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None


class ActivityReportFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None


class CrmDashboardFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

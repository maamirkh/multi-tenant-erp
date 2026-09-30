"""CRM report filter schemas (spec §17, plan.md Phase 2 §2.5). No
``branch_id`` anywhere (FR-RPT-091) — no CRM entity carries a branch
column. All 4 "Now" reports are aggregate-shaped; response *types* reuse
CRM's own already-tested Pydantic schemas verbatim
(``modules.crm.schemas.reports``), matching the Accounting adapter's DRY
reuse precedent — no new response models are declared here (T101).

Exception (FR-RPT-152): ``crm.pipeline`` and ``crm.dashboard`` wrap CRM's
schemas so money figures are reported per Opportunity currency, never
summed across currencies."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from modules.crm.schemas.reports import PipelineReport


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


class CrmPipelineCurrency(BaseModel):
    currency_code: str
    report: PipelineReport
    """CRM's own pipeline report over Opportunities in this currency only."""


class CrmPipelineByCurrency(BaseModel):
    """``crm.pipeline``: the currency-independent win rate and sales cycle
    over all Opportunities, plus CRM's pipeline report per currency."""

    win_rate: Decimal | None
    avg_sales_cycle_days: Decimal | None
    date_from: date | None
    date_to: date | None
    by_currency: list[CrmPipelineCurrency]


class CrmPipelineValues(BaseModel):
    currency_code: str
    open_pipeline_value: Decimal
    weighted_pipeline_value: Decimal


class CrmDashboardByCurrency(BaseModel):
    """``crm.dashboard``: CRM's dashboard counts and rates, with the two
    pipeline values per currency instead of one cross-currency sum."""

    lead_count: int
    conversion_rate: Decimal | None
    win_rate: Decimal | None
    overdue_follow_up_count: int
    activities_completed: int
    period_from: date
    period_to: date
    by_currency: list[CrmPipelineValues]

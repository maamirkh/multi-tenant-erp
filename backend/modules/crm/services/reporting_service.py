"""CrmReportingService — pipeline, lead, activity reports + dashboard KPIs.

Mirrors the existing "compute a dict/schema of metrics" pattern already
used by ``modules.sales.services.kpi_service``/``modules.accounting.services.
kpi_service`` — no new BI system, every metric is either one aggregate SQL
query (via the repository aggregate methods added in T080/T081) or a
Python computation over an already-bounded, already-filtered result set
(average deal size / average sales cycle — date arithmetic with no single
portable SQL expression across SQLite/Postgres, matching
``kpi_service.py``'s own precedent for this exact class of metric).

Spec ref: specs/009-crm/spec.md §40, §41; plan.md §24.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.schemas.reports import (
    ActivityReport,
    CrmDashboard,
    LeadReport,
    PipelineOwnerValue,
    PipelineReport,
    PipelineSourceValue,
    PipelineStageValue,
)

_TWO = Decimal("0.01")


def _pct(numerator: int | Decimal, denominator: int | Decimal) -> Decimal | None:
    """Percentage, or ``None`` when the denominator is zero (undefined,
    not zero — avoids a misleading 0% for "no data yet")."""
    if not denominator:
        return None
    return (Decimal(numerator) / Decimal(denominator) * 100).quantize(
        _TWO, rounding=ROUND_HALF_UP
    )


def _day_bounds(d: date | None, *, end: bool) -> datetime | None:
    if d is None:
        return None
    return datetime.combine(d, datetime.max.time() if end else datetime.min.time())


def _current_month() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)
    end = next_month_start - timedelta(days=1)
    return start, end


class CrmReportingService:
    """Application service computing CRM reports and dashboard KPIs.
    Read-only — never writes anything."""

    def __init__(
        self,
        opportunity_repo: OpportunityRepository,
        lead_repo: LeadRepository,
        activity_repo: ActivityRepository,
    ) -> None:
        self._opportunities = opportunity_repo
        self._leads = lead_repo
        self._activities = activity_repo

    # ------------------------------------------------------------------
    # Pipeline report (spec.md §40.1)
    # ------------------------------------------------------------------

    def get_pipeline_report(
        self,
        company_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PipelineReport:
        value_by_stage = [
            PipelineStageValue(stage_id=stage_id, value=value)
            for stage_id, value in self._opportunities.sum_value_by_stage(company_id)
        ]
        value_by_owner = [
            PipelineOwnerValue(owner_id=UUID(owner_id), value=value)
            for owner_id, value in self._opportunities.sum_value_by_owner(company_id)
        ]
        value_by_source = [
            PipelineSourceValue(source_id=source_id, value=value)
            for source_id, value in self._opportunities.sum_value_by_source(company_id)
        ]

        won_value = self._opportunities.sum_value_by_status_in_period(
            company_id, "WON", "won_at", date_from, date_to
        )
        lost_value = self._opportunities.sum_value_by_status_in_period(
            company_id, "LOST", "lost_at", date_from, date_to
        )
        won_count, lost_count = self._opportunities.count_won_lost_in_period(
            company_id, date_from, date_to
        )
        win_rate = _pct(won_count, won_count + lost_count)

        won_opportunities = self._opportunities.list_won_in_period(
            company_id, date_from, date_to
        )
        if won_opportunities:
            avg_deal_size = (
                sum((o.value for o in won_opportunities), Decimal("0"))
                / len(won_opportunities)
            ).quantize(_TWO, rounding=ROUND_HALF_UP)
            cycle_days = [
                (o.won_at - o.created_at).days
                for o in won_opportunities
                if o.won_at is not None
            ]
            avg_sales_cycle_days = (
                (Decimal(sum(cycle_days)) / len(cycle_days)).quantize(
                    _TWO, rounding=ROUND_HALF_UP
                )
                if cycle_days
                else None
            )
        else:
            avg_deal_size = None
            avg_sales_cycle_days = None

        return PipelineReport(
            value_by_stage=value_by_stage,
            value_by_owner=value_by_owner,
            value_by_source=value_by_source,
            won_value=won_value,
            lost_value=lost_value,
            win_rate=win_rate,
            avg_deal_size=avg_deal_size,
            avg_sales_cycle_days=avg_sales_cycle_days,
            date_from=date_from,
            date_to=date_to,
        )

    # ------------------------------------------------------------------
    # Lead report (spec.md §40.2)
    # ------------------------------------------------------------------

    def get_lead_report(
        self,
        company_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> LeadReport:
        from_dt = _day_bounds(date_from, end=False)
        to_dt = _day_bounds(date_to, end=True)

        total_count = self._leads.count_total_in_period(company_id, from_dt, to_dt)
        count_by_status = self._leads.count_by_status(company_id)
        count_by_source = {
            (str(source_id) if source_id else "none"): count
            for source_id, count in self._leads.count_by_source(company_id).items()
        }
        converted_count = self._leads.count_converted_in_period(
            company_id, from_dt, to_dt
        )
        conversion_rate = _pct(converted_count, total_count)

        currently_qualified = self._leads.count_currently_qualified(company_id)
        qualified_to_close_rate = _pct(
            converted_count, currently_qualified + converted_count
        )

        return LeadReport(
            total_count=total_count,
            count_by_status=count_by_status,
            count_by_source=count_by_source,
            conversion_rate=conversion_rate,
            qualified_to_close_rate=qualified_to_close_rate,
            date_from=date_from,
            date_to=date_to,
        )

    # ------------------------------------------------------------------
    # Activity report (spec.md §40.3)
    # ------------------------------------------------------------------

    def get_activity_report(
        self,
        company_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> ActivityReport:
        from_dt = _day_bounds(date_from, end=False)
        to_dt = _day_bounds(date_to, end=True)

        completed_by_type = self._activities.count_completed_by_type_in_period(
            company_id, from_dt, to_dt
        )
        completed_count = sum(completed_by_type.values())
        overdue_by_owner = self._activities.count_overdue_by_owner(company_id)
        overdue_count = sum(overdue_by_owner.values())

        return ActivityReport(
            completed_count=completed_count,
            completed_by_type=completed_by_type,
            overdue_count=overdue_count,
            overdue_by_owner=overdue_by_owner,
            date_from=date_from,
            date_to=date_to,
        )

    # ------------------------------------------------------------------
    # Dashboard (spec.md §41) — current calendar month
    # ------------------------------------------------------------------

    def get_dashboard(self, company_id: UUID) -> CrmDashboard:
        period_from, period_to = _current_month()

        open_pipeline_value = sum(
            (value for _, value in self._opportunities.sum_value_by_stage(company_id)),
            Decimal("0"),
        )
        weighted_pipeline_value = self._opportunities.sum_weighted_value(
            company_id, status="OPEN"
        )

        lead_report = self.get_lead_report(company_id, period_from, period_to)
        pipeline_report = self.get_pipeline_report(company_id, period_from, period_to)
        activity_report = self.get_activity_report(company_id, period_from, period_to)

        return CrmDashboard(
            open_pipeline_value=open_pipeline_value,
            weighted_pipeline_value=weighted_pipeline_value,
            lead_count=lead_report.total_count,
            conversion_rate=lead_report.conversion_rate,
            win_rate=pipeline_report.win_rate,
            overdue_follow_up_count=activity_report.overdue_count,
            activities_completed=activity_report.completed_count,
            period_from=period_from,
            period_to=period_to,
        )

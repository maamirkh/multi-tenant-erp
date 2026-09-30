"""``CrmAdapter`` — wraps CRM's already-implemented ``CrmReportingService``
behind the Reports ``ReportAdapter`` Protocol. Every figure is computed by
an existing CRM service method; this adapter re-derives nothing.

All 4 "Now" CRM reports are aggregate-shaped (``PaginationStyle.NONE``) —
none has an export/count seam (T098-equivalent note for CRM). Stateless
(matches ``AccountingAdapter``'s pattern): every call builds a fresh
``CrmReportingService`` from CRM's own existing repository factories.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.crm.dependencies import (
    get_activity_repository,
    get_crm_reporting_service,
    get_lead_repository,
    get_opportunity_repository,
)
from modules.crm.schemas.reports import (
    ActivityReport,
    LeadReport,
)
from modules.reports.exceptions import ReportNotFoundError
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.schemas.crm import (
    ActivityReportFilter,
    CrmDashboardByCurrency,
    CrmDashboardFilter,
    CrmPipelineByCurrency,
    CrmPipelineCurrency,
    CrmPipelineValues,
    LeadReportFilter,
    PipelineReportFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    BaseReportResult,
)


def _meta(report_key: str, filters: BaseModel) -> ReportEnvelopeMeta:
    from modules.reports.schemas.common import FreshnessClassification, PeriodResolution

    return ReportEnvelopeMeta(
        report_key=report_key,
        applied_filters=filters.model_dump(mode="json"),
        period=PeriodResolution(
            start="1970-01-01T00:00:00+00:00",
            end="1970-01-01T00:00:00+00:00",
            timezone="UTC",
        ),
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
    )


class CrmAdapter:
    """Stateless domain adapter for ``ReportDomain.CRM``'s 4 "Now"
    reports — all aggregate, no pagination."""

    def run(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
    ) -> BaseReportResult:
        service = get_crm_reporting_service(
            get_opportunity_repository(db),
            get_lead_repository(db),
            get_activity_repository(db),
        )

        if report_key == "crm.pipeline":
            assert isinstance(filters, PipelineReportFilter)
            overall = service.get_pipeline_report(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            pipeline = CrmPipelineByCurrency(
                win_rate=overall.win_rate,
                avg_sales_cycle_days=overall.avg_sales_cycle_days,
                date_from=overall.date_from,
                date_to=overall.date_to,
                by_currency=[
                    CrmPipelineCurrency(
                        currency_code=code,
                        report=service.get_pipeline_report(
                            company_id,
                            date_from=filters.date_from,
                            date_to=filters.date_to,
                            currency_code=code,
                        ),
                    )
                    for code in service.currency_codes(company_id)
                ],
            )
            return AggregateReportResult[CrmPipelineByCurrency](
                meta=_meta(report_key, filters), data=pipeline
            )
        if report_key == "crm.leads":
            assert isinstance(filters, LeadReportFilter)
            data_leads = service.get_lead_report(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            return AggregateReportResult[LeadReport](
                meta=_meta(report_key, filters), data=data_leads
            )
        if report_key == "crm.activities":
            assert isinstance(filters, ActivityReportFilter)
            data_activities = service.get_activity_report(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            return AggregateReportResult[ActivityReport](
                meta=_meta(report_key, filters), data=data_activities
            )
        if report_key == "crm.dashboard":
            assert isinstance(filters, CrmDashboardFilter)
            dashboard = service.get_dashboard(company_id)
            values = [
                (code, service.get_pipeline_values(company_id, code))
                for code in service.currency_codes(company_id)
            ]
            data_dashboard = CrmDashboardByCurrency(
                lead_count=dashboard.lead_count,
                conversion_rate=dashboard.conversion_rate,
                win_rate=dashboard.win_rate,
                overdue_follow_up_count=dashboard.overdue_follow_up_count,
                activities_completed=dashboard.activities_completed,
                period_from=dashboard.period_from,
                period_to=dashboard.period_to,
                by_currency=[
                    CrmPipelineValues(
                        currency_code=code,
                        open_pipeline_value=open_value,
                        weighted_pipeline_value=weighted,
                    )
                    for code, (open_value, weighted) in values
                ],
            )
            return AggregateReportResult[CrmDashboardByCurrency](
                meta=_meta(report_key, filters), data=data_dashboard
            )
        raise ReportNotFoundError(report_key)

    def export_row_model(self, report_key: str) -> type[BaseModel]:
        raise ValueError(f"'{report_key}' has no export-row iteration seam.")

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        raise ValueError(f"'{report_key}' has no export-row count seam.")

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        raise ValueError(f"'{report_key}' has no export-row iteration seam.")

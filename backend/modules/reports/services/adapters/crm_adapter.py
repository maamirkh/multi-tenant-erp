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
    CrmDashboard,
    LeadReport,
    PipelineReport,
)
from modules.reports.exceptions import ReportNotFoundError
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.schemas.crm import (
    ActivityReportFilter,
    CrmDashboardFilter,
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
            data = service.get_pipeline_report(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            return AggregateReportResult[PipelineReport](
                meta=_meta(report_key, filters), data=data
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
            data_dashboard = service.get_dashboard(company_id)
            return AggregateReportResult[CrmDashboard](
                meta=_meta(report_key, filters), data=data_dashboard
            )
        raise ReportNotFoundError(report_key)

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

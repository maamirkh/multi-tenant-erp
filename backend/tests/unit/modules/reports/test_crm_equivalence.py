"""T105 (corrected — adapter-level) — ``CrmReportingService`` called
directly vs. ``CrmAdapter.run()`` — identical for all 4 "Now" reports.
(Business-logic correctness against a hand-seeded dataset is already
covered by ``tests/integration/api/v1/crm/test_reports_api.py``'s T084 —
this test only proves the adapter is a faithful, non-lossy wrapper.)

``crm.pipeline``/``crm.dashboard`` report money per Opportunity currency
(FR-RPT-152), so they are compared with the service's per-currency calls."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.services.reporting_service import CrmReportingService
from modules.reports.schemas.crm import (
    ActivityReportFilter,
    CrmDashboardFilter,
    LeadReportFilter,
    PipelineReportFilter,
)
from modules.reports.services.adapters.base import AggregateReportResult
from modules.reports.services.adapters.crm_adapter import CrmAdapter


def _direct_service(db: Session) -> CrmReportingService:
    return CrmReportingService(
        opportunity_repo=OpportunityRepository(db),
        lead_repo=LeadRepository(db),
        activity_repo=ActivityRepository(db),
    )


def _seed_two_currencies(db: Session, company_id: uuid.UUID) -> None:
    pipeline = PipelineRepository(db).create(
        Pipeline(company_id=company_id, name="P", is_default=True)
    )
    stage = PipelineStageRepository(db).create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Open",
            sequence=1,
            probability=40,
        )
    )
    for amount, currency in (("100", "USD"), ("5000", "PKR")):
        OpportunityRepository(db).create(
            Opportunity(
                company_id=company_id,
                name=currency,
                customer_id=str(uuid.uuid4()),
                owner_id=str(uuid.uuid4()),
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                value=Decimal(amount),
                currency_code=currency,
                probability=40,
                status="OPEN",
            )
        )


def test_pipeline_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed_two_currencies(db_session, company_id)
    service = _direct_service(db_session)
    overall = service.get_pipeline_report(company_id)

    adapter = CrmAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "crm.pipeline",
        PipelineReportFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.win_rate == overall.win_rate
    assert result.data.avg_sales_cycle_days == overall.avg_sales_cycle_days
    assert [b.currency_code for b in result.data.by_currency] == ["PKR", "USD"]
    for block in result.data.by_currency:
        assert block.report == service.get_pipeline_report(
            company_id, currency_code=block.currency_code
        )


def test_leads_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    direct = _direct_service(db_session).get_lead_report(company_id)

    adapter = CrmAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "crm.leads",
        LeadReportFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data == direct


def test_activities_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    direct = _direct_service(db_session).get_activity_report(company_id)

    adapter = CrmAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "crm.activities",
        ActivityReportFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data == direct


def test_dashboard_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed_two_currencies(db_session, company_id)
    service = _direct_service(db_session)
    direct = service.get_dashboard(company_id)

    adapter = CrmAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "crm.dashboard",
        CrmDashboardFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    for field in (
        "lead_count",
        "conversion_rate",
        "win_rate",
        "overdue_follow_up_count",
        "activities_completed",
        "period_from",
        "period_to",
    ):
        assert getattr(result.data, field) == getattr(direct, field), field
    assert {
        v.currency_code: (v.open_pipeline_value, v.weighted_pipeline_value)
        for v in result.data.by_currency
    } == {
        code: service.get_pipeline_values(company_id, code) for code in ("PKR", "USD")
    }
    # Per currency, never the source's cross-currency total (5100).
    assert direct.open_pipeline_value == Decimal("5100")
    assert all(
        v.open_pipeline_value != Decimal("5100") for v in result.data.by_currency
    )

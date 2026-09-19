"""T105 (corrected — adapter-level) — ``CrmReportingService`` called
directly vs. ``CrmAdapter.run()`` — identical for all 4 "Now" reports.
(Business-logic correctness against a hand-seeded dataset is already
covered by ``tests/integration/api/v1/crm/test_reports_api.py``'s T084 —
this test only proves the adapter is a faithful, non-lossy wrapper.)"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
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


def test_pipeline_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    direct = _direct_service(db_session).get_pipeline_report(company_id)

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
    assert result.data == direct


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
    direct = _direct_service(db_session).get_dashboard(company_id)

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
    assert result.data == direct

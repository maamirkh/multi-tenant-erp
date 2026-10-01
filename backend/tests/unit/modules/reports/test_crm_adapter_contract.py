"""T104 — Contract test (mocked service): typed stability for all 4 CRM
report keys — all 4 return ``AggregateReportResult``; export/count seams
raise (no CRM "Now" report is list-shaped)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from modules.crm.schemas.reports import (
    ActivityReport,
    CrmDashboard,
    LeadReport,
    PipelineReport,
)
from modules.reports.schemas.crm import (
    ActivityReportFilter,
    CrmDashboardFilter,
    LeadReportFilter,
    PipelineReportFilter,
)
from modules.reports.services.adapters import crm_adapter as crm_adapter_mod
from modules.reports.services.adapters.base import AggregateReportResult
from modules.reports.services.adapters.crm_adapter import CrmAdapter

COMPANY_ID = uuid.uuid4()


def _run(filters: BaseModel, report_key: str) -> object:
    return CrmAdapter().run(
        MagicMock(),
        COMPANY_ID,
        report_key,
        filters,
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )


def _patch_service(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    service = MagicMock()
    monkeypatch.setattr(
        crm_adapter_mod, "get_crm_reporting_service", lambda *repos: service
    )
    return service


def test_pipeline_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_pipeline_report.return_value = PipelineReport(
        value_by_stage=[],
        value_by_owner=[],
        value_by_source=[],
        won_value=Decimal("0"),
        lost_value=Decimal("0"),
        win_rate=None,
        avg_deal_size=None,
        avg_sales_cycle_days=None,
        date_from=None,
        date_to=None,
    )
    result = _run(PipelineReportFilter(), "crm.pipeline")
    assert isinstance(result, AggregateReportResult)


def test_leads_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_lead_report.return_value = LeadReport(
        total_count=0,
        count_by_status={},
        count_by_source={},
        conversion_rate=None,
        qualified_to_close_rate=None,
        date_from=None,
        date_to=None,
    )
    result = _run(LeadReportFilter(), "crm.leads")
    assert isinstance(result, AggregateReportResult)


def test_activities_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_activity_report.return_value = ActivityReport(
        completed_count=0,
        completed_by_type={},
        overdue_count=0,
        overdue_by_owner={},
        date_from=None,
        date_to=None,
    )
    result = _run(ActivityReportFilter(), "crm.activities")
    assert isinstance(result, AggregateReportResult)


def test_dashboard_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_dashboard.return_value = CrmDashboard(
        open_pipeline_value=0,
        weighted_pipeline_value=0,
        lead_count=0,
        conversion_rate=None,
        win_rate=None,
        overdue_follow_up_count=0,
        activities_completed=0,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
    )
    result = _run(CrmDashboardFilter(), "crm.dashboard")
    assert isinstance(result, AggregateReportResult)


def test_no_export_seam_for_any_crm_report() -> None:
    adapter = CrmAdapter()
    with pytest.raises(ValueError):
        adapter.count_export_rows(
            MagicMock(), COMPANY_ID, "crm.pipeline", PipelineReportFilter()
        )
    with pytest.raises(ValueError):
        list(
            adapter.iter_export_rows(
                MagicMock(),
                COMPANY_ID,
                "crm.pipeline",
                PipelineReportFilter(),
                None,
                batch_size=100,
            )
        )

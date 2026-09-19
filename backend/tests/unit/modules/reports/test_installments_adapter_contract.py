"""T115 — Contract test (mocked service): typed stability for all 7
Installments report keys, and a structural AST-scan proving
``installments_adapter.py`` never imports ``PlatformEntitlementService``
or ``InstallmentsServicingContinuityGate`` — the Case A/B entitlement
decision genuinely lives one layer up (Phase 3's ``_authorize_and_validate()``),
never inside this adapter (mirrors
``tests/unit/modules/installments/test_accounting_gateway_boundary.py``'s
import-boundary technique, done here via a real ``ast`` parse rather than
substring matching)."""

from __future__ import annotations

import ast
import inspect
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

import modules.reports.services.adapters.installments_adapter as installments_adapter_mod
from modules.installments.services.reporting_service import InstallmentDashboardData
from modules.reports.schemas.installments import (
    CollectionsFilter,
    ContractRegisterFilter,
    DueOverdueFilter,
    InstallmentAgingFilter,
    InstallmentDashboardFilter,
    PlanPerformanceFilter,
    SettlementWriteoffFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.adapters.installments_adapter import InstallmentsAdapter

COMPANY_ID = uuid.uuid4()

_FORBIDDEN_IMPORT_NAMES = frozenset(
    {"PlatformEntitlementService", "InstallmentsServicingContinuityGate"}
)
_FORBIDDEN_IMPORT_MODULES = frozenset(
    {
        "modules.platform_admin.services.entitlement_service",
        "modules.reports.services.installments_continuity_gate",
    }
)


def test_adapter_module_never_imports_entitlement_or_continuity_gate() -> None:
    source = inspect.getsource(installments_adapter_mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in _FORBIDDEN_IMPORT_MODULES, (
                f"forbidden import of module '{node.module}'"
            )
            for alias in node.names:
                assert alias.name not in _FORBIDDEN_IMPORT_NAMES, (
                    f"forbidden import of name '{alias.name}'"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in _FORBIDDEN_IMPORT_MODULES, (
                    f"forbidden import of module '{alias.name}'"
                )


def _run(db: MagicMock, filters: BaseModel, report_key: str) -> object:
    return InstallmentsAdapter().run(
        db,
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
        installments_adapter_mod, "_build_reporting_service", lambda db: service
    )
    return service


@pytest.mark.parametrize(
    "report_key,filters,list_method",
    [
        ("installments.register", ContractRegisterFilter(), "get_contract_register"),
        ("installments.collections", CollectionsFilter(), "get_collection_report"),
    ],
)
def test_single_source_list_reports_return_paginated(
    monkeypatch: pytest.MonkeyPatch,
    report_key: str,
    filters: BaseModel,
    list_method: str,
) -> None:
    service = _patch_service(monkeypatch)
    getattr(service, list_method).return_value = ([{"contract_id": "c-1"}], 999)

    result = _run(MagicMock(), filters, report_key)
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 999
    assert len(result.items) == 1


def test_due_overdue_combines_both_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_due_report.return_value = ([{"schedule_line_id": "d-1"}], 1)
    service.get_overdue_report.return_value = ([{"schedule_line_id": "o-1"}], 1)

    result = _run(MagicMock(), DueOverdueFilter(), "installments.due_overdue")
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 2
    assert len(result.items) == 2


def test_aging_uses_bounded_population_then_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _patch_service(monkeypatch)
    service.get_aging_report.return_value = ([{"schedule_line_id": "a-1"}], 1)

    result = _run(MagicMock(), InstallmentAgingFilter(), "installments.aging")
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 1
    service.get_aging_report.assert_called_once()
    _args, kwargs = service.get_aging_report.call_args
    assert kwargs["skip"] == 0
    assert kwargs["limit"] == installments_adapter_mod._POPULATION_BOUND


def test_settlement_writeoff_combines_both_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _patch_service(monkeypatch)
    service.get_settlement_report.return_value = ([{"contract_id": "s-1"}], 1)
    service.get_default_writeoff_report.return_value = ([{"contract_id": "w-1"}], 1)

    result = _run(
        MagicMock(), SettlementWriteoffFilter(), "installments.settlement_writeoff"
    )
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 2
    assert len(result.items) == 2


def test_plan_performance_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_plan_performance_report.return_value = (
        [
            {
                "plan_template_id": "pt-1",
                "contract_count": 1,
                "total_contractual_amount": "100",
            }
        ],
        1,
    )

    result = _run(MagicMock(), PlanPerformanceFilter(), "installments.plan_performance")
    assert isinstance(result, AggregateReportResult)
    assert result.data.total == 1


def test_dashboard_returns_aggregate_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _patch_service(monkeypatch)
    service.get_dashboard.return_value = InstallmentDashboardData(
        active_contract_count=1,
        outstanding_amount="100",  # type: ignore[arg-type]
        due_today_amount="10",  # type: ignore[arg-type]
        due_this_month_amount="20",  # type: ignore[arg-type]
        collected_today_amount="5",  # type: ignore[arg-type]
        collected_this_month_amount="15",  # type: ignore[arg-type]
        overdue_amount="0",  # type: ignore[arg-type]
        overdue_count=0,
        collection_rate="0.5",  # type: ignore[arg-type]
        aging_distribution={"current": "0"},  # type: ignore[dict-item]
        defaulted_balance="0",  # type: ignore[arg-type]
        written_off_balance="0",  # type: ignore[arg-type]
        upcoming_receivables_amount="0",  # type: ignore[arg-type]
    )

    result = _run(
        MagicMock(),
        InstallmentDashboardFilter(as_of_date=date(2026, 1, 1)),
        "installments.dashboard",
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.active_contract_count == 1

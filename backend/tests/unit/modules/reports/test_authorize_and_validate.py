"""T127 — Unit tests for ``ReportExecutionService._authorize_and_validate()``
(FR-RPT-031): all failure modes, Installments Case A/B, short-circuit
ordering, and (Blocker A) a ``COMPOSITE``-kind key raising
``ReportNotFoundError`` identical to a ``DEFERRED`` key.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.platform_admin.services.entitlement_service import EffectiveEntitlement
from modules.reports.exceptions import (
    FilterValidationError,
    ReportNotEntitledError,
    ReportNotFoundError,
    ReportPermissionDeniedError,
    UnsupportedSortFieldError,
)
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.schemas.installments import (
    InstallmentAgingFilter,
    PlanPerformanceFilter,
)
from modules.reports.schemas.purchase import PurchaseSummaryFilter
from modules.reports.services import execution_service as execution_service_mod
from modules.reports.services.execution_service import ReportExecutionService

COMPANY_ID = uuid.uuid4()
USER_ID = uuid.uuid4()

# ---------------------------------------------------------------------------
# A throwaway COMPOSITE fixture entry — deliberately NOT passed to the
# real, shared ``register()`` (that would permanently pollute
# ``REPORT_REGISTRY`` for the rest of the pytest session and break Gate
# 2's "exactly 43 NOW, all ADAPTER" shape assertion in
# ``test_registry_consistency.py``, discovered by actually running the
# full suite). Instead, monkeypatched into ``execution_service_mod``'s
# own ``REPORT_REGISTRY`` reference for the one test that needs it.
# ---------------------------------------------------------------------------

_COMPOSITE_FIXTURE_KEY = "test.fixture.composite.t127"

_COMPOSITE_FIXTURE_DEFINITION = ReportDefinition(
    key=_COMPOSITE_FIXTURE_KEY,
    name="Fixture composite report",
    description="T127 fixture only.",
    domain=ReportDomain.EXECUTIVE,
    authoritative_source="builtins.len",
    required_permission="reports.executive.view",
    export_permission=None,
    domain_capability_key=None,
    supported_filters=PurchaseSummaryFilter,
    supported_dimensions=(),
    supported_measures=(),
    sortable_fields=(),
    export_formats=(),
    drill_down_targets=(),
    branch_filterable=False,
    freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
    pagination=PaginationStyle.NONE,
    status=ReportStatus.NOW,
    execution_kind=ReportExecutionKind.COMPOSITE,
)


def _service() -> ReportExecutionService:
    return ReportExecutionService()


def test_unregistered_key_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ReportNotFoundError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="does.not.exist",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def test_deferred_key_raises_not_found() -> None:
    with pytest.raises(ReportNotFoundError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="accounting.tax",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def test_composite_key_raises_not_found_identical_to_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blocker A: a COMPOSITE-kind key is unreachable via the generic
    path — identical error to a DEFERRED/unregistered key."""
    patched_registry = {
        **dict(REPORT_REGISTRY),
        _COMPOSITE_FIXTURE_KEY: _COMPOSITE_FIXTURE_DEFINITION,
    }
    monkeypatch.setattr(execution_service_mod, "REPORT_REGISTRY", patched_registry)
    with pytest.raises(ReportNotFoundError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key=_COMPOSITE_FIXTURE_KEY,
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def test_domain_not_entitled_raises_not_entitled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entitlement_service = MagicMock()
    entitlement_service.resolve_effective_entitlement.return_value = (
        EffectiveEntitlement(
            capability_key="purchase", available=False, reason="tenant_toggle_disabled"
        )
    )
    monkeypatch.setattr(
        execution_service_mod,
        "_build_entitlement_service",
        lambda db: entitlement_service,
    )
    with pytest.raises(ReportNotEntitledError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="purchase.summary",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def _patch_installments(
    monkeypatch: pytest.MonkeyPatch, *, available: bool, contract_total: int
) -> None:
    entitlement_service = MagicMock()
    entitlement_service.resolve_effective_entitlement.return_value = (
        EffectiveEntitlement(
            capability_key="installments",
            available=available,
            reason="plan_and_toggle" if available else "tenant_toggle_disabled",
        )
    )
    reporting_service = MagicMock()
    reporting_service.get_contract_register.return_value = ([], contract_total)
    monkeypatch.setattr(
        execution_service_mod,
        "_build_entitlement_service",
        lambda db: entitlement_service,
    )
    monkeypatch.setattr(
        execution_service_mod,
        "_build_installments_reporting_service",
        lambda db: reporting_service,
    )
    monkeypatch.setattr(
        execution_service_mod,
        "user_has_reports_permission",
        lambda *a, **k: True,
    )


def test_installments_case_a_denies_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_installments(monkeypatch, available=False, contract_total=0)
    with pytest.raises(ReportNotEntitledError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="installments.aging",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def test_installments_case_b_denies_plan_performance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_installments(monkeypatch, available=False, contract_total=1)
    with pytest.raises(ReportNotEntitledError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="installments.plan_performance",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def test_installments_case_b_allows_aging_with_continuity_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_installments(monkeypatch, available=False, contract_total=1)
    definition, filters, is_servicing_continuity = _service()._authorize_and_validate(
        MagicMock(),
        company_id=COMPANY_ID,
        user_id=USER_ID,
        report_key="installments.aging",
        raw_filters={},
        sort=None,
        permission_kind="view",
    )
    assert definition.key == "installments.aging"
    assert isinstance(filters, InstallmentAgingFilter)
    assert is_servicing_continuity is True


def test_installments_entitled_full_allows_plan_performance_no_continuity_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_installments(monkeypatch, available=True, contract_total=0)
    definition, filters, is_servicing_continuity = _service()._authorize_and_validate(
        MagicMock(),
        company_id=COMPANY_ID,
        user_id=USER_ID,
        report_key="installments.plan_performance",
        raw_filters={},
        sort=None,
        permission_kind="view",
    )
    assert definition.key == "installments.plan_performance"
    assert isinstance(filters, PlanPerformanceFilter)
    assert is_servicing_continuity is False


def test_permission_denied_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    entitlement_service = MagicMock()
    entitlement_service.resolve_effective_entitlement.return_value = (
        EffectiveEntitlement(
            capability_key="purchase", available=True, reason="plan_and_toggle"
        )
    )
    monkeypatch.setattr(
        execution_service_mod,
        "_build_entitlement_service",
        lambda db: entitlement_service,
    )
    monkeypatch.setattr(
        execution_service_mod, "user_has_reports_permission", lambda *a, **k: False
    )
    with pytest.raises(ReportPermissionDeniedError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="purchase.summary",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def test_short_circuit_entitlement_before_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-RPT-031: a request that fails BOTH entitlement and permission
    must raise the entitlement error, not the permission one — proving
    entitlement is checked first."""
    entitlement_service = MagicMock()
    entitlement_service.resolve_effective_entitlement.return_value = (
        EffectiveEntitlement(
            capability_key="purchase", available=False, reason="tenant_toggle_disabled"
        )
    )
    monkeypatch.setattr(
        execution_service_mod,
        "_build_entitlement_service",
        lambda db: entitlement_service,
    )
    monkeypatch.setattr(
        execution_service_mod, "user_has_reports_permission", lambda *a, **k: False
    )
    with pytest.raises(ReportNotEntitledError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="purchase.summary",
            raw_filters={},
            sort=None,
            permission_kind="view",
        )


def _entitled_permitted(
    monkeypatch: pytest.MonkeyPatch, *, domain: str = "purchase"
) -> None:
    entitlement_service = MagicMock()
    entitlement_service.resolve_effective_entitlement.return_value = (
        EffectiveEntitlement(
            capability_key=domain, available=True, reason="plan_and_toggle"
        )
    )
    monkeypatch.setattr(
        execution_service_mod,
        "_build_entitlement_service",
        lambda db: entitlement_service,
    )
    monkeypatch.setattr(
        execution_service_mod, "user_has_reports_permission", lambda *a, **k: True
    )


def test_filter_validation_error_on_unknown_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _entitled_permitted(monkeypatch)
    with pytest.raises(FilterValidationError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="purchase.summary",
            raw_filters={"not_a_real_field": "x"},
            sort=None,
            permission_kind="view",
        )


def test_unsupported_sort_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _entitled_permitted(monkeypatch)
    with pytest.raises(UnsupportedSortFieldError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="purchase.summary",
            raw_filters={},
            sort="not_a_sortable_field",
            permission_kind="view",
        )


def test_export_permission_none_denies_export_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A report with no ``export_permission`` (e.g. an aggregate KPI
    report) can never satisfy a ``permission_kind="export"`` request."""
    with pytest.raises(ReportPermissionDeniedError):
        _service()._authorize_and_validate(
            MagicMock(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            report_key="installments.dashboard",
            raw_filters={},
            sort=None,
            permission_kind="export",
        )


def test_successful_validation_returns_definition_and_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _entitled_permitted(monkeypatch)
    definition, filters, is_servicing_continuity = _service()._authorize_and_validate(
        MagicMock(),
        company_id=COMPANY_ID,
        user_id=USER_ID,
        report_key="purchase.summary",
        raw_filters={},
        sort=None,
        permission_kind="view",
    )
    assert definition.key == "purchase.summary"
    assert isinstance(filters, PurchaseSummaryFilter)
    assert is_servicing_continuity is False

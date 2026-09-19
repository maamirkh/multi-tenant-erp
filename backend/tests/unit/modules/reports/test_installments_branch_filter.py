"""T120 (correction pass) — branch-filter contract for Installments'
7 "Now" reports.

**Corrected from the original Phase-2 pass**: ``branch_id`` was
previously accepted by 5 filter schemas but never wired to any query —
silently accepted, silently ignored. Per FR-RPT-160/162, a filter that
cannot genuinely be honored through the domain's approved public service
contract MUST NOT be exposed at all. ``InstallmentReportingService`` (the
only approved source contract for these reports) has no ``branch_id``
parameter on any public method, and Installments is not one of the 3
sanctioned T047/T075/T087 bounded-read seams, so no seam exists to add
one. The fix: remove ``branch_id`` from every Installments filter schema
entirely. Since every schema is ``extra="forbid"``, a caller that still
tries to pass ``branch_id`` now gets an explicit ``ValidationError``
(422 at the API layer) rather than having it silently dropped.

This test proves both halves: the field does not exist on any of the 7
filter schemas, and attempting to construct a filter with a ``branch_id``
kwarg is explicitly rejected — it can never again be silently accepted
and ignored.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel, ValidationError

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.registry.definitions import REPORT_REGISTRY, ReportDomain
from modules.reports.schemas.installments import (
    CollectionsFilter,
    ContractRegisterFilter,
    DueOverdueFilter,
    InstallmentAgingFilter,
    InstallmentDashboardFilter,
    PlanPerformanceFilter,
    SettlementWriteoffFilter,
)

_ALL_7_FILTER_CLASSES = (
    ContractRegisterFilter,
    CollectionsFilter,
    DueOverdueFilter,
    InstallmentAgingFilter,
    SettlementWriteoffFilter,
    PlanPerformanceFilter,
    InstallmentDashboardFilter,
)


@pytest.mark.parametrize("filter_cls", _ALL_7_FILTER_CLASSES)
def test_no_installments_filter_schema_has_a_branch_id_field(
    filter_cls: type[BaseModel],
) -> None:
    assert "branch_id" not in filter_cls.model_fields


@pytest.mark.parametrize("filter_cls", _ALL_7_FILTER_CLASSES)
def test_passing_branch_id_is_explicitly_rejected_not_silently_dropped(
    filter_cls: type[BaseModel],
) -> None:
    """``extra='forbid'`` means a caller that still tries to pass
    ``branch_id`` gets a hard validation failure, never a silently
    accepted-and-ignored value."""
    with pytest.raises(ValidationError):
        filter_cls(branch_id=uuid.uuid4())


def test_no_installments_registry_entry_declares_branch_filterable() -> None:
    """The catalog itself must not claim branch-filterability it cannot
    back with a real filter field."""
    installments_defs = [
        d for d in REPORT_REGISTRY.values() if d.domain is ReportDomain.INSTALLMENTS
    ]
    assert len(installments_defs) == 7
    assert all(not d.branch_filterable for d in installments_defs)


def test_contract_drill_down_preserves_no_branch_filter() -> None:
    """The drill-down link's ``preserves_filters`` must not reference a
    filter field that no longer exists on the originating report."""
    installments_defs = [
        d for d in REPORT_REGISTRY.values() if d.domain is ReportDomain.INSTALLMENTS
    ]
    for definition in installments_defs:
        for target in definition.drill_down_targets:
            assert "branch_id" not in target.preserves_filters

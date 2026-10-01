"""T031 — ``registry_service.list_discoverable_reports()`` filtering.

Registers three **fixture** ``ReportDefinition``s directly in this test
(the registry mechanism only exists at Phase 0 — no real domain data
yet): one visible (NOW + permission held), one not visible (NOW,
permission not held), one never visible (DEFERRED, regardless of
permission).
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from modules.reports.registry import definitions as registry_definitions
from modules.reports.registry.definitions import (
    ExportFormat,
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
    register,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.services import registry_service as registry_service_module
from modules.reports.services.registry_service import list_discoverable_reports


class _FixtureFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _make_definition(key: str, *, status: ReportStatus) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        name=key,
        description="fixture",
        domain=ReportDomain.SALES,
        authoritative_source="tests.fixture.not_a_real_callable",
        required_permission=f"{key}.view",
        export_permission=None,
        domain_capability_key=None,
        supported_filters=_FixtureFilters,
        supported_dimensions=(),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(ExportFormat.CSV,),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=status,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


@pytest.fixture
def isolated_registry() -> Iterator[None]:
    """Snapshot/restore the module-global registry dict in place (never
    reassigning the name) so the exported ``REPORT_REGISTRY`` view — bound
    to the same dict object — stays in sync, and this test's fixture
    entries never leak into any other test's registry inspection."""
    snapshot = dict(registry_definitions._REGISTRY)
    yield
    registry_definitions._REGISTRY.clear()
    registry_definitions._REGISTRY.update(snapshot)


def test_filters_to_now_and_permitted_entries(
    isolated_registry: None, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    visible = _make_definition("test.visible", status=ReportStatus.NOW)
    hidden_by_permission = _make_definition(
        "test.hidden_by_permission", status=ReportStatus.NOW
    )
    deferred = _make_definition("test.deferred", status=ReportStatus.DEFERRED)
    register(visible)
    register(hidden_by_permission)
    register(deferred)

    def fake_has_permission(
        db: Session, company_id, user_id, permission_code: str, **kwargs: object
    ) -> bool:
        return permission_code == visible.required_permission

    monkeypatch.setattr(
        registry_service_module, "user_has_reports_permission", fake_has_permission
    )

    result = list_discoverable_reports(db_session, uuid4(), uuid4())
    result_keys = {d.key for d in result}

    assert "test.visible" in result_keys
    assert "test.hidden_by_permission" not in result_keys
    assert "test.deferred" not in result_keys

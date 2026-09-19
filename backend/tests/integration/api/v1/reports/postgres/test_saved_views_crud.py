"""T046 — Gate 1 evidence: real-Postgres Saved Report View CRUD
round-trip (create/list/update/delete, JSONB ``filter_config``).

Soft-delete excludes a view from ``list_views``; the identical
``SavedViewNotFoundError`` is raised for a deleted view, another user's
view, and another tenant's view — no distinguishing signal anywhere
(plan.md §15).
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from modules.reports.exceptions import SavedViewNotFoundError
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
from modules.reports.repositories.saved_report_view import SavedReportViewRepository
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.schemas.saved_view import (
    SavedReportViewCreate,
    SavedReportViewUpdate,
)
from modules.reports.services import saved_view_service

_FIXTURE_KEY = "test.pg_fixture.saved_view"


class _FixtureFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    snapshot = dict(registry_definitions._REGISTRY)
    register(
        ReportDefinition(
            key=_FIXTURE_KEY,
            name="PG Fixture Saved View Report",
            description="fixture",
            domain=ReportDomain.SALES,
            authoritative_source="tests.fixture.not_a_real_callable",
            required_permission="reports.sales.view",
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
            status=ReportStatus.NOW,
            execution_kind=ReportExecutionKind.ADAPTER,
        )
    )
    yield
    registry_definitions._REGISTRY.clear()
    registry_definitions._REGISTRY.update(snapshot)


def test_create_list_update_delete_round_trip(db_session: Session) -> None:
    repo = SavedReportViewRepository(db_session)
    company_id = uuid4()
    owner_id = uuid4()

    created = saved_view_service.save(
        repo,
        company_id=company_id,
        user_id=owner_id,
        payload=SavedReportViewCreate(
            report_key=_FIXTURE_KEY,
            name="My Saved View",
            filter_config={"customer_id": "cust-123"},
        ),
    )
    assert created.id is not None
    assert created.schema_version == 1
    assert created.filter_config == {"customer_id": "cust-123"}

    items, total = saved_view_service.list_views(repo, company_id, owner_id)
    assert total == 1
    assert items[0].id == created.id

    updated = saved_view_service.update(
        repo,
        view_id=created.id,
        company_id=company_id,
        user_id=owner_id,
        payload=SavedReportViewUpdate(name="Renamed View"),
    )
    assert updated.name == "Renamed View"
    assert updated.filter_config == {"customer_id": "cust-123"}

    saved_view_service.delete(
        repo, view_id=created.id, company_id=company_id, user_id=owner_id
    )

    items_after_delete, total_after_delete = saved_view_service.list_views(
        repo, company_id, owner_id
    )
    assert total_after_delete == 0
    assert items_after_delete == []


def test_jsonb_filter_config_round_trips_exactly(db_session: Session) -> None:
    repo = SavedReportViewRepository(db_session)
    company_id = uuid4()
    owner_id = uuid4()

    created = saved_view_service.save(
        repo,
        company_id=company_id,
        user_id=owner_id,
        payload=SavedReportViewCreate(
            report_key=_FIXTURE_KEY,
            name="JSONB Test",
            filter_config={"customer_id": "abc"},
            grouping=["region", "product"],
            visible_columns=["name", "total"],
        ),
    )
    db_session.expire_all()

    reloaded = repo.get_for_owner(created.id, company_id, owner_id)
    assert reloaded is not None
    assert reloaded.filter_config == {"customer_id": "abc"}
    assert reloaded.grouping == ["region", "product"]
    assert reloaded.visible_columns == ["name", "total"]


class TestOwnershipIsolationReturnsIdenticalNotFound:
    def test_other_owner_same_tenant_cannot_update_or_delete(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()
        other_user_id = uuid4()

        created = saved_view_service.save(
            repo,
            company_id=company_id,
            user_id=owner_id,
            payload=SavedReportViewCreate(
                report_key=_FIXTURE_KEY, name="Owner's View", filter_config={}
            ),
        )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=created.id,
                company_id=company_id,
                user_id=other_user_id,
                payload=SavedReportViewUpdate(name="Hijacked"),
            )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.delete(
                repo, view_id=created.id, company_id=company_id, user_id=other_user_id
            )

    def test_other_tenant_cannot_update_or_delete(self, db_session: Session) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()
        other_company_id = uuid4()

        created = saved_view_service.save(
            repo,
            company_id=company_id,
            user_id=owner_id,
            payload=SavedReportViewCreate(
                report_key=_FIXTURE_KEY, name="Owner's View", filter_config={}
            ),
        )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=created.id,
                company_id=other_company_id,
                user_id=owner_id,
                payload=SavedReportViewUpdate(name="Hijacked"),
            )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.delete(
                repo, view_id=created.id, company_id=other_company_id, user_id=owner_id
            )

    def test_deleted_view_returns_identical_not_found_to_update_and_delete(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()

        created = saved_view_service.save(
            repo,
            company_id=company_id,
            user_id=owner_id,
            payload=SavedReportViewCreate(
                report_key=_FIXTURE_KEY, name="Soon Deleted", filter_config={}
            ),
        )
        saved_view_service.delete(
            repo, view_id=created.id, company_id=company_id, user_id=owner_id
        )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=created.id,
                company_id=company_id,
                user_id=owner_id,
                payload=SavedReportViewUpdate(name="Resurrected"),
            )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.delete(
                repo, view_id=created.id, company_id=company_id, user_id=owner_id
            )

    def test_nonexistent_view_id_returns_identical_not_found(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=uuid4(),
                company_id=company_id,
                user_id=owner_id,
                payload=SavedReportViewUpdate(name="Ghost"),
            )

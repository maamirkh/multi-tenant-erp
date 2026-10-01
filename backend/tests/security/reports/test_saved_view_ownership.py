"""T045A — dedicated Saved Report View ownership/security test (micro-
correction-pass Blocker D).

Owner can list/create/update/delete; a same-tenant non-owner and a
cross-tenant user both get the identical ``SavedViewNotFoundError`` a
nonexistent ID would (never a distinguishable 403 — no ID-probing
signal); a soft-deleted view's ID returns that same not-found to both
update and delete; ``update()`` rejects an invalid new ``filter_config``
the same way ``save()`` already does.

Load-time re-authorization (permission/entitlement changed since save) is
a distinct concern covered by Phase 3's T141, not duplicated here.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from modules.reports.exceptions import FilterValidationError, SavedViewNotFoundError
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

_FIXTURE_KEY = "test.security_fixture.saved_view"


class _FixtureFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    snapshot = dict(registry_definitions._REGISTRY)
    register(
        ReportDefinition(
            key=_FIXTURE_KEY,
            name="Security Fixture Saved View Report",
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


def test_owner_can_list_create_update_delete(db_session: Session) -> None:
    repo = SavedReportViewRepository(db_session)
    company_id = uuid4()
    owner_id = uuid4()

    created = saved_view_service.save(
        repo,
        company_id=company_id,
        user_id=owner_id,
        payload=SavedReportViewCreate(
            report_key=_FIXTURE_KEY, name="Mine", filter_config={"customer_id": "c1"}
        ),
    )
    items, total = saved_view_service.list_views(repo, company_id, owner_id)
    assert total == 1 and items[0].id == created.id

    updated = saved_view_service.update(
        repo,
        view_id=created.id,
        company_id=company_id,
        user_id=owner_id,
        payload=SavedReportViewUpdate(name="Mine (renamed)"),
    )
    assert updated.name == "Mine (renamed)"

    saved_view_service.delete(
        repo, view_id=created.id, company_id=company_id, user_id=owner_id
    )
    _, total_after = saved_view_service.list_views(repo, company_id, owner_id)
    assert total_after == 0


class TestNoIdProbingSignal:
    """Every failure mode below must raise the identical
    ``SavedViewNotFoundError`` — never a 403, never a distinguishable
    message — regardless of *why* the row isn't visible to the caller."""

    def _make_owned_view(self, repo: SavedReportViewRepository, company_id, owner_id):
        return saved_view_service.save(
            repo,
            company_id=company_id,
            user_id=owner_id,
            payload=SavedReportViewCreate(
                report_key=_FIXTURE_KEY, name="Owner's", filter_config={}
            ),
        )

    def test_same_tenant_non_owner_gets_not_found_on_update(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()
        non_owner_id = uuid4()
        view = self._make_owned_view(repo, company_id, owner_id)

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=view.id,
                company_id=company_id,
                user_id=non_owner_id,
                payload=SavedReportViewUpdate(name="Stolen"),
            )

    def test_same_tenant_non_owner_gets_not_found_on_delete(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()
        non_owner_id = uuid4()
        view = self._make_owned_view(repo, company_id, owner_id)

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.delete(
                repo, view_id=view.id, company_id=company_id, user_id=non_owner_id
            )

    def test_cross_tenant_user_gets_not_found_on_update(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        other_company_id = uuid4()
        owner_id = uuid4()
        view = self._make_owned_view(repo, company_id, owner_id)

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=view.id,
                company_id=other_company_id,
                user_id=owner_id,
                payload=SavedReportViewUpdate(name="Stolen"),
            )

    def test_cross_tenant_user_gets_not_found_on_delete(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        other_company_id = uuid4()
        owner_id = uuid4()
        view = self._make_owned_view(repo, company_id, owner_id)

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.delete(
                repo, view_id=view.id, company_id=other_company_id, user_id=owner_id
            )

    def test_soft_deleted_view_returns_identical_not_found_on_update(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()
        view = self._make_owned_view(repo, company_id, owner_id)
        saved_view_service.delete(
            repo, view_id=view.id, company_id=company_id, user_id=owner_id
        )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.update(
                repo,
                view_id=view.id,
                company_id=company_id,
                user_id=owner_id,
                payload=SavedReportViewUpdate(name="Resurrected"),
            )

    def test_soft_deleted_view_returns_identical_not_found_on_delete(
        self, db_session: Session
    ) -> None:
        repo = SavedReportViewRepository(db_session)
        company_id = uuid4()
        owner_id = uuid4()
        view = self._make_owned_view(repo, company_id, owner_id)
        saved_view_service.delete(
            repo, view_id=view.id, company_id=company_id, user_id=owner_id
        )

        with pytest.raises(SavedViewNotFoundError):
            saved_view_service.delete(
                repo, view_id=view.id, company_id=company_id, user_id=owner_id
            )

    def test_nonexistent_id_matches_the_same_exception_type(
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


def test_update_rejects_invalid_filter_config_same_as_save(
    db_session: Session,
) -> None:
    repo = SavedReportViewRepository(db_session)
    company_id = uuid4()
    owner_id = uuid4()

    with pytest.raises(FilterValidationError):
        saved_view_service.save(
            repo,
            company_id=company_id,
            user_id=owner_id,
            payload=SavedReportViewCreate(
                report_key=_FIXTURE_KEY,
                name="Bad",
                filter_config={"unregistered_field": "x"},
            ),
        )

    valid_view = saved_view_service.save(
        repo,
        company_id=company_id,
        user_id=owner_id,
        payload=SavedReportViewCreate(
            report_key=_FIXTURE_KEY, name="Good", filter_config={}
        ),
    )

    with pytest.raises(FilterValidationError):
        saved_view_service.update(
            repo,
            view_id=valid_view.id,
            company_id=company_id,
            user_id=owner_id,
            payload=SavedReportViewUpdate(filter_config={"unregistered_field": "x"}),
        )

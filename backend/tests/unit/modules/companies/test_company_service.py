"""Unit tests for CompanyService — business logic layer.

All repositories and sub-services are mocked; no database is required.

Test coverage targets:
- Successful company creation with slug derivation
- Duplicate name raises CompanyNameConflictError
- Duplicate auto-derived slug gets numeric suffix
- Valid status transitions succeed
- Invalid transitions raise InvalidStatusTransitionError
- Company activation fails if required fields are missing
- Soft delete succeeds on active/inactive company
- Restore beyond 90-day window raises CompanyPurgedError
- Currency change without confirm raises CurrencyChangeWarningError
- Slug cannot be changed after activation
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.companies.exceptions import (
    CompanyIncompleteError,
    CompanyNameConflictError,
    CompanyNotFoundError,
    CompanyPurgedError,
    CurrencyChangeWarningError,
    InvalidStatusTransitionError,
    SlugConflictError,
    SlugImmutableError,
)
from modules.companies.models.enums import CompanyStatus
from modules.companies.services.company_service import CompanyService, _derive_slug

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_company(
    status: str = CompanyStatus.active.value,
    deleted_at: datetime | None = None,
    default_currency: str = "USD",
    slug: str = "acme-corp",
) -> MagicMock:
    """Return a mock Company ORM object."""
    company = MagicMock()
    company.id = uuid4()
    company.legal_name = "Acme Corp"
    company.slug = slug
    company.status = status
    company.owner_id = uuid4()
    company.email = "contact@acme.com"
    company.country = "US"
    company.default_currency = default_currency
    company.default_language = "en-US"
    company.default_timezone = "UTC"
    company.trade_name = None
    company.updated_at = datetime.now(UTC)
    company.created_at = datetime.now(UTC)
    company.deleted_at = deleted_at
    company.deletion_reason = None
    return company


def _make_service(
    company_repo: MagicMock | None = None,
    address_repo: MagicMock | None = None,
    audit_log_repo: MagicMock | None = None,
    outbox_repo: MagicMock | None = None,
    audit_service: MagicMock | None = None,
    settings_service: MagicMock | None = None,
) -> CompanyService:
    """Return a CompanyService with all dependencies mocked."""
    db = MagicMock()
    return CompanyService(
        db=db,
        company_repo=company_repo or MagicMock(),
        address_repo=address_repo or MagicMock(),
        audit_log_repo=audit_log_repo or MagicMock(),
        outbox_repo=outbox_repo or MagicMock(),
        audit_service=audit_service or MagicMock(),
        settings_service=settings_service or MagicMock(),
    )


# ---------------------------------------------------------------------------
# Slug derivation helper
# ---------------------------------------------------------------------------


class TestDeriveSlug:
    def test_basic_derivation(self) -> None:
        assert _derive_slug("Acme Corp") == "acme-corp"

    def test_special_characters_become_hyphens(self) -> None:
        assert _derive_slug("Acme & Co. Ltd.") == "acme-co-ltd"

    def test_consecutive_specials_collapse(self) -> None:
        assert _derive_slug("Hello   World") == "hello-world"

    def test_leading_trailing_stripped(self) -> None:
        assert _derive_slug("--Foo Bar--") == "foo-bar"

    def test_numbers_preserved(self) -> None:
        assert _derive_slug("Company 42") == "company-42"


# ---------------------------------------------------------------------------
# create_company
# ---------------------------------------------------------------------------


class TestCreateCompany:
    def test_creates_company_successfully(self) -> None:
        company = _make_company(status=CompanyStatus.pending_setup.value)
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = False
        company_repo.exists_by_slug.return_value = False
        company_repo.create.return_value = company

        service = _make_service(company_repo=company_repo)
        result = service.create_company(
            actor_id=uuid4(),
            data={"legal_name": "Acme Corp", "email": "a@b.com"},
        )

        assert result is company
        company_repo.create.assert_called_once()

    def test_slug_derived_from_legal_name(self) -> None:
        company = _make_company(slug="widget-factory")
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = False
        company_repo.exists_by_slug.return_value = False
        company_repo.create.return_value = company

        service = _make_service(company_repo=company_repo)
        service.create_company(
            actor_id=uuid4(),
            data={"legal_name": "Widget Factory", "email": "w@w.com"},
        )

        call_kwargs = company_repo.create.call_args[0][0]
        assert call_kwargs["slug"] == "widget-factory"

    def test_duplicate_name_raises_conflict(self) -> None:
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = True

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CompanyNameConflictError):
            service.create_company(
                actor_id=uuid4(),
                data={"legal_name": "Acme Corp", "email": "a@b.com"},
            )

    def test_explicit_slug_conflict_raises_error(self) -> None:
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = False
        company_repo.exists_by_slug.return_value = True

        service = _make_service(company_repo=company_repo)
        with pytest.raises(SlugConflictError):
            service.create_company(
                actor_id=uuid4(),
                data={"legal_name": "Acme Corp", "email": "a@b.com", "slug": "taken"},
            )

    def test_auto_slug_gets_numeric_suffix_on_collision(self) -> None:
        company = _make_company(slug="acme-corp-1")
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = False
        # First call (base slug) returns True (collision), second call returns False
        company_repo.exists_by_slug.side_effect = [True, False]
        company_repo.create.return_value = company

        service = _make_service(company_repo=company_repo)
        service.create_company(
            actor_id=uuid4(),
            data={"legal_name": "Acme Corp", "email": "a@b.com"},
        )

        call_kwargs = company_repo.create.call_args[0][0]
        assert call_kwargs["slug"] == "acme-corp-1"

    def test_audit_record_written_on_create(self) -> None:
        company = _make_company()
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = False
        company_repo.exists_by_slug.return_value = False
        company_repo.create.return_value = company
        audit_service = MagicMock()

        service = _make_service(company_repo=company_repo, audit_service=audit_service)
        service.create_company(
            actor_id=uuid4(), data={"legal_name": "X", "email": "x@x.com"}
        )

        audit_service.record.assert_called_once()
        call_kwargs = audit_service.record.call_args[1]
        assert call_kwargs["action"] == "COMPANY_CREATED"

    def test_outbox_event_published_on_create(self) -> None:
        company = _make_company()
        company_repo = MagicMock()
        company_repo.exists_by_name.return_value = False
        company_repo.exists_by_slug.return_value = False
        company_repo.create.return_value = company
        outbox_repo = MagicMock()

        service = _make_service(company_repo=company_repo, outbox_repo=outbox_repo)
        service.create_company(
            actor_id=uuid4(), data={"legal_name": "X", "email": "x@x.com"}
        )

        outbox_repo.create.assert_called_once()


# ---------------------------------------------------------------------------
# update_company
# ---------------------------------------------------------------------------


class TestUpdateCompany:
    def test_updates_fields_successfully(self) -> None:
        company = _make_company()
        updated = _make_company()
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.update.return_value = updated

        service = _make_service(company_repo=company_repo)
        result = service.update_company(
            company_id=company.id,
            actor_id=uuid4(),
            data={"trade_name": "ACME"},
        )

        assert result is updated

    def test_slug_immutable_after_activation(self) -> None:
        company = _make_company(status=CompanyStatus.active.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(SlugImmutableError):
            service.update_company(
                company_id=company.id,
                actor_id=uuid4(),
                data={"slug": "new-slug"},
            )

    def test_currency_change_without_confirm_raises_warning(self) -> None:
        company = _make_company(default_currency="USD")
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CurrencyChangeWarningError):
            service.update_company(
                company_id=company.id,
                actor_id=uuid4(),
                data={"default_currency": "EUR"},
            )

    def test_currency_change_with_confirm_succeeds(self) -> None:
        company = _make_company(default_currency="USD")
        updated = _make_company(default_currency="EUR")
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.update.return_value = updated

        service = _make_service(company_repo=company_repo)
        result = service.update_company(
            company_id=company.id,
            actor_id=uuid4(),
            data={"default_currency": "EUR", "confirm_currency_change": True},
        )

        assert result is updated

    def test_not_found_raises_error(self) -> None:
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = None

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CompanyNotFoundError):
            service.update_company(
                company_id=uuid4(),
                actor_id=uuid4(),
                data={"trade_name": "X"},
            )


# ---------------------------------------------------------------------------
# activate_company
# ---------------------------------------------------------------------------


class TestActivateCompany:
    def test_activates_pending_company(self) -> None:
        company = _make_company(status=CompanyStatus.pending_setup.value)
        company.email = "a@b.com"
        company.country = "US"
        company.default_currency = "USD"
        activated = _make_company(status=CompanyStatus.active.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.update.return_value = activated

        service = _make_service(company_repo=company_repo)
        result = service.activate_company(company_id=company.id, actor_id=uuid4())

        assert result is activated

    def test_activates_inactive_company(self) -> None:
        company = _make_company(status=CompanyStatus.inactive.value)
        company.email = "a@b.com"
        company.country = "US"
        company.default_currency = "USD"
        activated = _make_company(status=CompanyStatus.active.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.update.return_value = activated

        service = _make_service(company_repo=company_repo)
        result = service.activate_company(company_id=company.id, actor_id=uuid4())

        assert result is activated

    def test_activation_fails_when_required_fields_missing(self) -> None:
        company = _make_company(status=CompanyStatus.pending_setup.value)
        company.email = "a@b.com"
        company.country = None  # missing
        company.default_currency = None  # missing
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CompanyIncompleteError) as exc_info:
            service.activate_company(company_id=company.id, actor_id=uuid4())

        assert "country" in exc_info.value.details["missing_fields"]
        assert "default_currency" in exc_info.value.details["missing_fields"]

    def test_invalid_transition_from_deleted_raises_error(self) -> None:
        company = _make_company(status=CompanyStatus.deleted.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(InvalidStatusTransitionError):
            service.activate_company(company_id=company.id, actor_id=uuid4())

    def test_suspended_company_cannot_be_activated_by_owner(self) -> None:
        company = _make_company(status=CompanyStatus.suspended.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(InvalidStatusTransitionError):
            service.activate_company(company_id=company.id, actor_id=uuid4())


# ---------------------------------------------------------------------------
# deactivate_company
# ---------------------------------------------------------------------------


class TestDeactivateCompany:
    def test_deactivates_active_company(self) -> None:
        company = _make_company(status=CompanyStatus.active.value)
        deactivated = _make_company(status=CompanyStatus.inactive.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.update.return_value = deactivated

        service = _make_service(company_repo=company_repo)
        result = service.deactivate_company(
            company_id=company.id, actor_id=uuid4(), reason="No longer needed"
        )

        assert result is deactivated

    def test_deactivate_inactive_company_raises_error(self) -> None:
        company = _make_company(status=CompanyStatus.inactive.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(InvalidStatusTransitionError):
            service.deactivate_company(
                company_id=company.id, actor_id=uuid4(), reason="Test"
            )


# ---------------------------------------------------------------------------
# soft_delete_company
# ---------------------------------------------------------------------------


class TestSoftDeleteCompany:
    def test_soft_deletes_active_company(self) -> None:
        company = _make_company(status=CompanyStatus.active.value)
        deleted = _make_company(status=CompanyStatus.deleted.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.soft_delete.return_value = deleted

        service = _make_service(company_repo=company_repo)
        result = service.soft_delete_company(
            company_id=company.id,
            actor_id=uuid4(),
            reason="Closing down",
        )

        assert result is deleted

    def test_soft_deletes_inactive_company(self) -> None:
        company = _make_company(status=CompanyStatus.inactive.value)
        deleted = _make_company(status=CompanyStatus.deleted.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company
        company_repo.soft_delete.return_value = deleted

        service = _make_service(company_repo=company_repo)
        result = service.soft_delete_company(
            company_id=company.id,
            actor_id=uuid4(),
            reason="Test",
        )

        assert result is deleted

    def test_delete_suspended_raises_invalid_transition(self) -> None:
        company = _make_company(status=CompanyStatus.suspended.value)
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(InvalidStatusTransitionError):
            service.soft_delete_company(
                company_id=company.id,
                actor_id=uuid4(),
                reason="Test",
            )


# ---------------------------------------------------------------------------
# restore_company
# ---------------------------------------------------------------------------


class TestRestoreCompany:
    def test_restores_deleted_company_within_window(self) -> None:
        deleted_at = datetime.now(UTC) - timedelta(days=30)
        company = _make_company(
            status=CompanyStatus.deleted.value, deleted_at=deleted_at
        )
        restored = _make_company(status=CompanyStatus.inactive.value)
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = company
        company_repo.restore.return_value = restored

        service = _make_service(company_repo=company_repo)
        result = service.restore_company(company_id=company.id, actor_id=uuid4())

        assert result is restored

    def test_restore_beyond_window_raises_purged_error(self) -> None:
        deleted_at = datetime.now(UTC) - timedelta(days=91)
        company = _make_company(
            status=CompanyStatus.deleted.value, deleted_at=deleted_at
        )
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CompanyPurgedError):
            service.restore_company(company_id=company.id, actor_id=uuid4())

    def test_restore_non_deleted_raises_invalid_transition(self) -> None:
        company = _make_company(status=CompanyStatus.inactive.value)
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = company

        service = _make_service(company_repo=company_repo)
        with pytest.raises(InvalidStatusTransitionError):
            service.restore_company(company_id=company.id, actor_id=uuid4())

    def test_restore_not_found_raises_error(self) -> None:
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CompanyNotFoundError):
            service.restore_company(company_id=uuid4(), actor_id=uuid4())


# ---------------------------------------------------------------------------
# get_company / list operations
# ---------------------------------------------------------------------------


class TestGetCompany:
    def test_returns_company_for_valid_id(self) -> None:
        company = _make_company()
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = company

        service = _make_service(company_repo=company_repo)
        result = service.get_company(company.id, requester_id=uuid4())

        assert result is company

    def test_raises_not_found_for_missing_company(self) -> None:
        company_repo = MagicMock()
        company_repo.get_by_id_active.return_value = None

        service = _make_service(company_repo=company_repo)
        with pytest.raises(CompanyNotFoundError):
            service.get_company(uuid4(), requester_id=uuid4())


class TestListCompanies:
    def test_list_user_companies(self) -> None:
        company = _make_company()
        company_repo = MagicMock()
        company_repo.list_by_owner.return_value = [company]

        service = _make_service(company_repo=company_repo)
        result = service.list_user_companies(owner_id=uuid4())

        assert result == [company]

    def test_list_all_companies_with_pagination(self) -> None:
        company = _make_company()
        company_repo = MagicMock()
        company_repo.list_all.return_value = ([company], 1)

        service = _make_service(company_repo=company_repo)
        items, total = service.list_all_companies(page=1, page_size=10)

        assert items == [company]
        assert total == 1

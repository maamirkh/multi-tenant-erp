"""Unit tests for company module FastAPI dependency functions.

All external dependencies (DB, services, auth) are mocked so that
these tests run without a database or real JWT tokens.

Tests cover spec Checkpoint 8:
- get_current_company returns company when owner_id matches user
- get_current_company raises 404 when company does not exist
- get_current_company raises 403 with COMPANY_SUSPENDED when suspended
- require_owner() passes for owner, raises 403 for non-owner
- require_super_admin() passes for super_admin, raises 403 for regular user
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from core.auth.interfaces import CurrentUser
from modules.companies.dependencies import (
    get_current_company,
    require_admin_or_above,
    require_owner,
    require_role,
    require_super_admin,
)
from modules.companies.exceptions import CompanyNotFoundError, CompanySuspendedError
from modules.companies.models.enums import CompanyStatus

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_user(
    user_id=None,
    roles: list[str] | None = None,
    is_authenticated: bool = True,
) -> CurrentUser:
    """Return a mock CurrentUser."""
    return CurrentUser(
        user_id=user_id or uuid4(),
        email="test@example.com",
        roles=roles or [],
        is_authenticated=is_authenticated,
    )


def _make_company(
    status: str = CompanyStatus.active.value,
    owner_id=None,
):
    """Return a mock Company ORM object."""
    company = MagicMock()
    company.id = uuid4()
    company.owner_id = owner_id or uuid4()
    company.status = status
    return company


def _make_service(company_obj):
    """Return a mock CompanyService whose _company_repo.get_by_id returns company_obj."""
    service = MagicMock()
    service._company_repo.get_by_id.return_value = company_obj
    return service


# ---------------------------------------------------------------------------
# get_current_company
# ---------------------------------------------------------------------------


class TestGetCurrentCompany:
    def test_returns_company_when_owner_id_matches(self) -> None:
        user_id = uuid4()
        company = _make_company(owner_id=user_id)
        current_user = _make_user(user_id=user_id)
        service = _make_service(company)

        result = get_current_company(
            company_id=company.id,
            current_user=current_user,
            service=service,
        )

        assert result is company

    def test_super_admin_can_access_any_company(self) -> None:
        company = _make_company()  # different owner
        current_user = _make_user(roles=["super_admin"])
        service = _make_service(company)

        result = get_current_company(
            company_id=company.id,
            current_user=current_user,
            service=service,
        )

        assert result is company

    def test_raises_404_when_company_does_not_exist(self) -> None:
        current_user = _make_user()
        service = _make_service(None)  # not found

        with pytest.raises(CompanyNotFoundError):
            get_current_company(
                company_id=uuid4(),
                current_user=current_user,
                service=service,
            )

    def test_raises_403_company_suspended_when_suspended(self) -> None:
        user_id = uuid4()
        company = _make_company(status=CompanyStatus.suspended.value, owner_id=user_id)
        current_user = _make_user(user_id=user_id)
        service = _make_service(company)

        with pytest.raises(CompanySuspendedError):
            get_current_company(
                company_id=company.id,
                current_user=current_user,
                service=service,
            )

    def test_raises_404_when_company_is_deleted(self) -> None:
        user_id = uuid4()
        company = _make_company(status=CompanyStatus.deleted.value, owner_id=user_id)
        current_user = _make_user(user_id=user_id)
        service = _make_service(company)

        with pytest.raises(CompanyNotFoundError):
            get_current_company(
                company_id=company.id,
                current_user=current_user,
                service=service,
            )

    def test_raises_403_when_user_is_not_member(self) -> None:
        company = _make_company()  # owner is a different user
        current_user = _make_user()  # not the owner, not super_admin
        service = _make_service(company)

        with pytest.raises(HTTPException) as exc_info:
            get_current_company(
                company_id=company.id,
                current_user=current_user,
                service=service,
            )

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------


class TestRequireRole:
    def test_passes_when_user_has_required_role(self) -> None:
        current_user = _make_user(roles=["admin"])
        guard = require_role(["admin", "super_admin"])
        result = guard(current_user=current_user)
        assert result is current_user

    def test_raises_403_when_user_lacks_role(self) -> None:
        current_user = _make_user(roles=["viewer"])
        guard = require_role(["admin", "super_admin"])

        with pytest.raises(HTTPException) as exc_info:
            guard(current_user=current_user)

        assert exc_info.value.status_code == 403

    def test_raises_403_when_user_has_no_roles(self) -> None:
        current_user = _make_user(roles=[])
        guard = require_role(["admin"])

        with pytest.raises(HTTPException) as exc_info:
            guard(current_user=current_user)

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_owner
# ---------------------------------------------------------------------------


class TestRequireOwner:
    def test_passes_for_company_owner(self) -> None:
        user_id = uuid4()
        company = _make_company(owner_id=user_id)
        current_user = _make_user(user_id=user_id)
        guard = require_owner()

        result = guard(company=company, current_user=current_user)

        assert result is company

    def test_passes_for_super_admin(self) -> None:
        company = _make_company()  # different owner
        current_user = _make_user(roles=["super_admin"])
        guard = require_owner()

        result = guard(company=company, current_user=current_user)

        assert result is company

    def test_raises_403_for_non_owner(self) -> None:
        company = _make_company()
        current_user = _make_user()  # not owner, not super_admin
        guard = require_owner()

        with pytest.raises(HTTPException) as exc_info:
            guard(company=company, current_user=current_user)

        assert exc_info.value.status_code == 403

    def test_raises_403_for_admin_role_without_ownership(self) -> None:
        company = _make_company()
        current_user = _make_user(roles=["admin"])  # admin but not owner
        guard = require_owner()

        with pytest.raises(HTTPException) as exc_info:
            guard(company=company, current_user=current_user)

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_admin_or_above
# ---------------------------------------------------------------------------


class TestRequireAdminOrAbove:
    def test_passes_for_owner(self) -> None:
        user_id = uuid4()
        company = _make_company(owner_id=user_id)
        current_user = _make_user(user_id=user_id)
        guard = require_admin_or_above()

        result = guard(company=company, current_user=current_user)

        assert result is company

    def test_passes_for_admin_role(self) -> None:
        company = _make_company()
        current_user = _make_user(roles=["admin"])
        guard = require_admin_or_above()

        result = guard(company=company, current_user=current_user)

        assert result is company

    def test_passes_for_super_admin(self) -> None:
        company = _make_company()
        current_user = _make_user(roles=["super_admin"])
        guard = require_admin_or_above()

        result = guard(company=company, current_user=current_user)

        assert result is company

    def test_raises_403_for_viewer_role(self) -> None:
        company = _make_company()
        current_user = _make_user(roles=["viewer"])
        guard = require_admin_or_above()

        with pytest.raises(HTTPException) as exc_info:
            guard(company=company, current_user=current_user)

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_super_admin
# ---------------------------------------------------------------------------


class TestRequireSuperAdmin:
    def test_passes_for_super_admin(self) -> None:
        current_user = _make_user(roles=["super_admin"])
        guard = require_super_admin()
        result = guard(current_user=current_user)
        assert result is current_user

    def test_raises_403_for_regular_user(self) -> None:
        current_user = _make_user(roles=[])
        guard = require_super_admin()

        with pytest.raises(HTTPException) as exc_info:
            guard(current_user=current_user)

        assert exc_info.value.status_code == 403

    def test_raises_403_for_admin_role(self) -> None:
        current_user = _make_user(roles=["admin"])
        guard = require_super_admin()

        with pytest.raises(HTTPException) as exc_info:
            guard(current_user=current_user)

        assert exc_info.value.status_code == 403

    def test_raises_403_for_owner_role(self) -> None:
        current_user = _make_user(roles=["owner"])
        guard = require_super_admin()

        with pytest.raises(HTTPException) as exc_info:
            guard(current_user=current_user)

        assert exc_info.value.status_code == 403

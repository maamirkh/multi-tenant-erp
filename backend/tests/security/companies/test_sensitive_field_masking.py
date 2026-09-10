"""T113 [P] — Sensitive field masking tests.

Verifies that ``tax_number`` and ``registration_number`` are masked to
``"****"`` for roles outside the sensitive-roles set, and unmasked for
privileged roles.

Sensitive roles (schema.py _SENSITIVE_ROLES):
  owner, admin, accountant, super_admin  →  unmasked
  viewer, manager, sales, inventory      →  "****"

Tests:
  1. Schema unit tests: for_role() masks/unmasks correctly for each role.
  2. HTTP integration: owner GETs company → real tax_number in response.
  3. HTTP integration: super_admin GETs company (dependency override) →
     real tax_number in response.

Note: In Phase 3, the HTTP layer can only produce "owner" or "super_admin"
role values (non-owners are blocked at 403 by get_current_company). The
"viewer" masking path is exercised via the schema unit test.

Spec ref: spec.md §6.1 Data Sensitivity, BR-026.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

if TYPE_CHECKING:
    from modules.companies.schemas.company import CompanyDetailResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


_TAX_NUMBER = "123-45-6789"
_REG_NUMBER = "REG-987654"


@pytest.fixture()
def company_with_sensitive_data(test_client: TestClient, db_session: Session):
    """Create a company with tax_number and registration_number set.

    Returns (owner_token, company_id).
    """
    prefix = _uuid.uuid4().hex[:8]
    owner, pwd = create_test_user(db_session, email=f"mask_owner_{prefix}@example.com")
    token = _login(test_client, owner.email, pwd)

    # Create the company
    resp = test_client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Mask Test Corp {prefix}",
            "email": f"mask_{prefix}@example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    company_id = resp.json()["data"]["id"]

    # Patch in the sensitive fields
    resp = test_client.patch(
        f"/api/v1/companies/{company_id}",
        json={"tax_number": _TAX_NUMBER, "registration_number": _REG_NUMBER},
        headers=_auth(token),
    )
    assert resp.status_code == 200

    return token, company_id, owner


# ---------------------------------------------------------------------------
# Schema-level unit tests (for_role method)
# ---------------------------------------------------------------------------


class TestSensitiveFieldMaskingSchema:
    """Direct tests of CompanyDetailResponse.for_role() without HTTP layer."""

    def _make_response(self) -> CompanyDetailResponse:
        from datetime import datetime

        from modules.companies.schemas.company import CompanyDetailResponse

        return CompanyDetailResponse(
            id=_uuid.uuid4(),
            owner_id=_uuid.uuid4(),
            legal_name="Schema Test Corp",
            slug="schema-test-corp",
            email="test@example.com",
            status="active",
            tax_number=_TAX_NUMBER,
            registration_number=_REG_NUMBER,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def test_owner_role_sees_unmasked_tax_number(self) -> None:
        resp = self._make_response()
        data = resp.for_role("owner")
        assert data["tax_number"] == _TAX_NUMBER
        assert data["registration_number"] == _REG_NUMBER

    def test_accountant_role_sees_unmasked_tax_number(self) -> None:
        resp = self._make_response()
        data = resp.for_role("accountant")
        assert data["tax_number"] == _TAX_NUMBER
        assert data["registration_number"] == _REG_NUMBER

    def test_super_admin_role_sees_unmasked_tax_number(self) -> None:
        resp = self._make_response()
        data = resp.for_role("super_admin")
        assert data["tax_number"] == _TAX_NUMBER
        assert data["registration_number"] == _REG_NUMBER

    def test_viewer_role_sees_masked_tax_number(self) -> None:
        resp = self._make_response()
        data = resp.for_role("viewer")
        assert data["tax_number"] == "****"
        assert data["registration_number"] == "****"

    def test_manager_role_sees_masked_tax_number(self) -> None:
        resp = self._make_response()
        data = resp.for_role("manager")
        assert data["tax_number"] == "****"
        assert data["registration_number"] == "****"

    def test_sales_role_sees_masked_tax_number(self) -> None:
        resp = self._make_response()
        data = resp.for_role("sales")
        assert data["tax_number"] == "****"
        assert data["registration_number"] == "****"

    def test_null_sensitive_fields_remain_null_for_viewer(self) -> None:
        from datetime import datetime

        from modules.companies.schemas.company import CompanyDetailResponse

        resp = CompanyDetailResponse(
            id=_uuid.uuid4(),
            owner_id=_uuid.uuid4(),
            legal_name="Null Fields Corp",
            slug="null-fields-corp",
            email="null@example.com",
            status="pending_setup",
            tax_number=None,
            registration_number=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        data = resp.for_role("viewer")
        assert data["tax_number"] is None
        assert data["registration_number"] is None


# ---------------------------------------------------------------------------
# HTTP-level integration tests
# ---------------------------------------------------------------------------


class TestSensitiveFieldMaskingHTTP:
    """Owner GET via HTTP API returns unmasked sensitive fields."""

    def test_owner_get_company_returns_unmasked_tax_number(
        self,
        test_client: TestClient,
        company_with_sensitive_data: tuple[Any, ...],
    ) -> None:
        token, company_id, _ = company_with_sensitive_data
        resp = test_client.get(f"/api/v1/companies/{company_id}", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tax_number"] == _TAX_NUMBER
        assert data["registration_number"] == _REG_NUMBER

    def test_super_admin_get_company_returns_unmasked_tax_number(
        self,
        test_client: TestClient,
        db_session: Session,
        company_with_sensitive_data: tuple[Any, ...],
    ) -> None:
        """SuperAdmin injected via dependency override sees unmasked fields."""
        from core.auth.dependencies import require_authenticated
        from core.auth.interfaces import CurrentUser

        token, company_id, owner = company_with_sensitive_data

        def _fake_super_admin() -> CurrentUser:
            mock = MagicMock(spec=CurrentUser)
            mock.user_id = owner.id
            mock.email = owner.email
            mock.roles = ["super_admin"]
            # Epic 9A T084: get_current_company() now reads .session_id to
            # evaluate the company-access freshness watermark. This fixture's
            # company was never suspended (access_invalidated_at is NULL), so
            # Layer 2 short-circuits before session_id is ever looked up in a
            # real Session table — None is a valid, accurate stand-in here.
            mock.session_id = None
            return mock

        app = cast(FastAPI, test_client.app)
        app.dependency_overrides[require_authenticated] = _fake_super_admin
        try:
            resp = test_client.get(f"/api/v1/companies/{company_id}")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["tax_number"] == _TAX_NUMBER
            assert data["registration_number"] == _REG_NUMBER
        finally:
            app.dependency_overrides.clear()

"""RBAC permission matrix tests — Sales module — Phase 10 T238.

The sales module uses JWT authentication as the authorization boundary.
All authenticated users within a company scope can access sales data
(company scoping is the isolation tested in test_tenant_isolation.py).

This test focuses on:
  - All read operations require authentication (401 without token)
  - All write operations require authentication (401 without token)
  - All lifecycle transitions require authentication (401 without token)
  - Authenticated users can perform all CRUD operations in their company scope
  - Bulk/export operations require authentication
  - Approval operations require authentication

Task: T238
Spec ref: specs/007-sales-management/spec.md §9 RBAC
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "RbacTest@1234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _TEST_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _sales_url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/sales{path}"


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"RBAC Sales Test Co {suffix}",
            "email": f"contact-{suffix}@rbac-sales-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_ctx(test_client: TestClient, db_session: Session):
    email = f"rbac-sales-{uuid.uuid4().hex[:6]}@example.com"
    create_test_user(db_session, email, password=_TEST_PASSWORD)
    token = _login(test_client, email)
    cid = _create_company(test_client, token)
    return test_client, token, cid


# ---------------------------------------------------------------------------
# Read operations — unauthenticated returns 401
# ---------------------------------------------------------------------------

READ_ENDPOINTS: list[str] = [
    "/customers",
    "/quotations",
    "/sales-orders",
    "/delivery-notes",
    "/invoices",
    "/returns",
    "/price-lists",
    "/customer-categories",
    "/customer-groups",
    "/payment-terms",
    "/reason-codes",
    "/configuration",
    "/feature-flags",
    "/kpis",
    "/approval-matrices",
]


class TestReadOperationsRequireAuth:
    """All read (GET) endpoints must return 401 without a valid token."""

    @pytest.mark.parametrize("path_suffix", READ_ENDPOINTS)
    def test_get_requires_auth(self, test_client: TestClient, path_suffix: str) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(_sales_url(cid, path_suffix))
        assert resp.status_code == 401, (
            f"GET {path_suffix} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# Write operations — unauthenticated returns 401
# ---------------------------------------------------------------------------

WRITE_ENDPOINTS: list[tuple[str, dict[str, Any]]] = [
    (
        "/customers",
        {
            "customer_code": "X",
            "legal_name": "X",
            "customer_type": "COMPANY",
            "category_id": str(uuid.uuid4()),
            "currency_code": "USD",
        },
    ),
    (
        "/quotations",
        {
            "customer_id": str(uuid.uuid4()),
            "quotation_date": "2026-08-01",
            "validity_date": "2026-09-30",
            "currency_code": "USD",
            "sales_rep_id": str(uuid.uuid4()),
        },
    ),
    (
        "/sales-orders",
        {
            "customer_id": str(uuid.uuid4()),
            "order_date": "2026-08-01",
            "currency_code": "USD",
            "sales_rep_id": str(uuid.uuid4()),
            "lines": [],
        },
    ),
    ("/delivery-notes", {"order_id": str(uuid.uuid4()), "lines": []}),
    (
        "/invoices",
        {
            "customer_id": str(uuid.uuid4()),
            "invoice_date": "2026-08-01",
            "currency_code": "USD",
            "lines": [],
            "charges": [],
        },
    ),
    (
        "/returns",
        {
            "customer_id": str(uuid.uuid4()),
            "return_date": "2026-08-01",
            "reason_code_id": str(uuid.uuid4()),
            "resolution_type": "CREDIT_NOTE",
            "lines": [
                {"description": "X", "quantity_returned": "1", "unit_price": "10.00"}
            ],
        },
    ),
    ("/customer-categories", {"name": "Test Category"}),
    ("/payment-terms", {"name": "Net 30", "days": 30}),
]


class TestWriteOperationsRequireAuth:
    """All write (POST) endpoints must return 401 without a valid token."""

    @pytest.mark.parametrize("path_suffix,body", WRITE_ENDPOINTS)
    def test_post_requires_auth(
        self, test_client: TestClient, path_suffix: str, body: dict[str, Any]
    ) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.post(_sales_url(cid, path_suffix), json=body)
        assert resp.status_code == 401, (
            f"POST {path_suffix} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# Lifecycle transitions — unauthenticated returns 401
# ---------------------------------------------------------------------------

TRANSITION_ENDPOINTS: list[str] = [
    f"/quotations/{uuid.uuid4()}/send",
    f"/quotations/{uuid.uuid4()}/accept",
    f"/quotations/{uuid.uuid4()}/reject",
    f"/quotations/{uuid.uuid4()}/convert",
    f"/quotations/{uuid.uuid4()}/cancel",
    f"/sales-orders/{uuid.uuid4()}/submit",
    f"/sales-orders/{uuid.uuid4()}/approve",
    f"/sales-orders/{uuid.uuid4()}/reject",
    f"/sales-orders/{uuid.uuid4()}/cancel",
    f"/delivery-notes/{uuid.uuid4()}/dispatch",
    f"/delivery-notes/{uuid.uuid4()}/deliver",
    f"/delivery-notes/{uuid.uuid4()}/cancel",
    f"/invoices/{uuid.uuid4()}/issue",
    f"/invoices/{uuid.uuid4()}/cancel",
    f"/returns/{uuid.uuid4()}/submit",
    f"/returns/{uuid.uuid4()}/approve",
    f"/returns/{uuid.uuid4()}/reject",
    f"/returns/{uuid.uuid4()}/cancel",
]


class TestLifecycleTransitionsRequireAuth:
    """All lifecycle transition endpoints must return 401 without a valid token."""

    @pytest.mark.parametrize("path_suffix", TRANSITION_ENDPOINTS)
    def test_transition_requires_auth(
        self, test_client: TestClient, path_suffix: str
    ) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.post(_sales_url(cid, path_suffix), json={})
        assert resp.status_code == 401, (
            f"POST {path_suffix} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# Authenticated user can perform all operations in their scope
# ---------------------------------------------------------------------------


class TestAuthenticatedUserAccess:
    """Authenticated users get 2xx/4xx (not 401) for all sales operations."""

    def test_authenticated_user_can_list_customers(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.get(_sales_url(cid, "/customers"), headers=_auth(token))
        assert resp.status_code == 200

    def test_authenticated_user_can_create_customer(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.post(
            _sales_url(cid, "/customers"),
            json={
                "customer_code": f"RBAC-{uuid.uuid4().hex[:6].upper()}",
                "legal_name": "RBAC Test Corp",
                "customer_type": "COMPANY",
                "category_id": str(uuid.uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201

    def test_authenticated_user_can_create_quotation(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.post(
            _sales_url(cid, "/quotations"),
            json={
                "customer_id": str(uuid.uuid4()),
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201

    def test_authenticated_user_can_create_order(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": str(uuid.uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
                "lines": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201

    def test_authenticated_user_can_create_invoice(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.post(
            _sales_url(cid, "/invoices"),
            json={
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "RBAC Test Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201

    def test_authenticated_user_can_access_kpis(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.get(
            _sales_url(cid, "/kpis"),
            headers=_auth(token),
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )
        assert resp.status_code == 200

    def test_authenticated_user_can_view_feature_flags(
        self, auth_ctx: tuple[Any, ...]
    ) -> None:
        client, token, cid = auth_ctx
        resp = client.get(_sales_url(cid, "/feature-flags"), headers=_auth(token))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bulk operations require auth
# ---------------------------------------------------------------------------


class TestBulkOperationsRequireAuth:
    """Import and export endpoints must require authentication."""

    def test_customer_import_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.post(
            _sales_url(cid, "/customers/import"),
            files={"file": ("test.csv", b"customer_code,legal_name\n", "text/csv")},
        )
        assert resp.status_code == 401

    def test_customer_export_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(_sales_url(cid, "/customers/export"))
        assert resp.status_code == 401

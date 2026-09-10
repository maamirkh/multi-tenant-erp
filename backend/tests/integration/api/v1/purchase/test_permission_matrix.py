"""RBAC permission matrix tests — Purchase module — Phase 11 T248.

Verifies that authentication is enforced for all write operations and that
the system correctly rejects unauthenticated requests.

The purchase module uses JWT authentication (not role-based row access at
the API layer beyond authentication) — all authenticated users within a
company scope can access purchase data (company scoping is the isolation
boundary tested in test_tenant_isolation.py).

This test focuses on:
  - Write operations require authentication
  - Read operations require authentication
  - Transition actions (submit/approve/reject/confirm/complete) require auth
  - Bulk operations (import, export) require auth

Task: T248
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _base(cid: str) -> str:
    return f"/api/v1/companies/{cid}/purchase"


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Purchase Test Co {suffix}",
            "email": f"contact-{suffix}@purchase-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


@pytest.fixture()
def rbac_auth(test_client: TestClient, db_session: Session):
    user, pw = create_test_user(
        db_session, email="rbac-test@example.com", password="Rbac1!"
    )
    token = _login(test_client, user.email, pw)
    cid = _create_company(test_client, token)
    return test_client, token, cid


def _create_supplier(client: TestClient, token: str, cid: str, code: str) -> str:
    resp = client.post(
        f"{_base(cid)}/suppliers",
        headers=_auth(token),
        json={
            "legal_name": "RBAC Test Supplier",
            "supplier_code": code,
            "supplier_type": "GOODS",
            "currency_code": "USD",
            "payment_terms_days": 30,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    sid = resp.json()["data"]["id"]
    client.post(f"{_base(cid)}/suppliers/{sid}/activate", headers=_auth(token))
    return str(sid)


def _create_po(client: TestClient, token: str, cid: str, supplier_id: str) -> str:
    resp = client.post(
        f"{_base(cid)}/purchase-orders",
        headers=_auth(token),
        json={"supplier_id": supplier_id, "currency_code": "USD"},
    )
    assert resp.status_code in (200, 201), resp.text
    return str(resp.json()["data"]["id"])


# ---------------------------------------------------------------------------
# T248-A: Read endpoints require authentication
# ---------------------------------------------------------------------------

READ_ENDPOINTS = [
    "/suppliers",
    "/purchase-orders",
    "/purchase-requests",
    "/goods-receipts",
    "/vendor-returns",
    "/reports/kpis",
    "/feature-flags",
    "/health",
]


class TestReadEndpointsRequireAuth:
    @pytest.mark.parametrize("path_suffix", READ_ENDPOINTS)
    def test_unauthenticated_read_returns_401(
        self, test_client: TestClient, path_suffix: str
    ):
        cid = str(uuid.uuid4())
        resp = test_client.get(f"{_base(cid)}{path_suffix}")
        assert resp.status_code == 401, (
            f"GET {path_suffix} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# T248-B: Create endpoints require authentication
# ---------------------------------------------------------------------------

CREATE_ENDPOINTS = [
    (
        "/suppliers",
        {
            "legal_name": "X",
            "supplier_code": "X1",
            "supplier_type": "GOODS",
            "currency_code": "USD",
            "payment_terms_days": 30,
        },
    ),
    ("/purchase-orders", {"supplier_id": str(uuid.uuid4()), "currency_code": "USD"}),
    (
        "/purchase-requests",
        {
            "title": "T",
            "department": "IT",
            "required_date": "2030-01-01",
            "reason_code": "OPERATIONAL",
        },
    ),
    (
        "/goods-receipts",
        {"po_id": str(uuid.uuid4()), "received_date": "2026-01-01", "lines": []},
    ),
    (
        "/vendor-returns",
        {"gr_id": str(uuid.uuid4()), "return_reason": "DAMAGED", "lines": []},
    ),
]


class TestCreateEndpointsRequireAuth:
    @pytest.mark.parametrize("path_suffix,payload", CREATE_ENDPOINTS)
    def test_unauthenticated_create_returns_401(
        self, test_client: TestClient, path_suffix: str, payload: dict[str, Any]
    ):
        cid = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}{path_suffix}", json=payload)
        assert resp.status_code == 401, (
            f"POST {path_suffix} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# T248-C: State transition endpoints require authentication
# ---------------------------------------------------------------------------


class TestTransitionEndpointsRequireAuth:
    def test_submit_pr_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/purchase-requests/{fake_id}/submit")
        assert resp.status_code == 401

    def test_approve_pr_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/purchase-requests/{fake_id}/approve")
        assert resp.status_code == 401

    def test_submit_po_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/purchase-orders/{fake_id}/submit")
        assert resp.status_code == 401

    def test_approve_po_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/purchase-orders/{fake_id}/approve")
        assert resp.status_code == 401

    def test_confirm_gr_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/goods-receipts/{fake_id}/confirm")
        assert resp.status_code == 401

    def test_supplier_activate_unauthenticated_returns_401(
        self, test_client: TestClient
    ):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/suppliers/{fake_id}/activate")
        assert resp.status_code == 401

    def test_supplier_deactivate_unauthenticated_returns_401(
        self, test_client: TestClient
    ):
        cid = str(uuid.uuid4())
        fake_id = str(uuid.uuid4())
        resp = test_client.post(f"{_base(cid)}/suppliers/{fake_id}/deactivate")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T248-D: Bulk operations require authentication
# ---------------------------------------------------------------------------


class TestBulkOperationsRequireAuth:
    def test_supplier_import_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        resp = test_client.post(
            f"{_base(cid)}/suppliers/import",
            files={"file": ("s.csv", b"supplier_code,legal_name\n", "text/csv")},
        )
        assert resp.status_code == 401

    def test_po_export_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        fake_po_id = str(uuid.uuid4())
        resp = test_client.get(f"{_base(cid)}/purchase-orders/{fake_po_id}/export/pdf")
        assert resp.status_code == 401

    def test_report_csv_export_unauthenticated_returns_401(
        self, test_client: TestClient
    ):
        cid = str(uuid.uuid4())
        resp = test_client.get(
            f"{_base(cid)}/reports/purchase-order-summary",
            params={"fmt": "csv"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T248-E: Authenticated users can access purchase data
# ---------------------------------------------------------------------------


class TestAuthenticatedAccess:
    def test_authenticated_user_can_list_suppliers(self, rbac_auth):
        client, token, cid = rbac_auth
        resp = client.get(f"{_base(cid)}/suppliers", headers=_auth(token))
        assert resp.status_code == 200

    def test_authenticated_user_can_create_supplier(self, rbac_auth):
        client, token, cid = rbac_auth
        resp = client.post(
            f"{_base(cid)}/suppliers",
            headers=_auth(token),
            json={
                "legal_name": "RBAC Auth Supplier",
                "supplier_code": "RBAC-AUTH-001",
                "supplier_type": "GOODS",
                "currency_code": "USD",
                "payment_terms_days": 30,
            },
        )
        assert resp.status_code in (200, 201)

    def test_authenticated_user_can_list_pos(self, rbac_auth):
        client, token, cid = rbac_auth
        resp = client.get(f"{_base(cid)}/purchase-orders", headers=_auth(token))
        assert resp.status_code == 200

    def test_authenticated_user_can_view_feature_flags(self, rbac_auth):
        client, token, cid = rbac_auth
        resp = client.get(f"{_base(cid)}/feature-flags", headers=_auth(token))
        assert resp.status_code == 200

    def test_authenticated_user_can_view_kpis(self, rbac_auth):
        client, token, cid = rbac_auth
        resp = client.get(
            f"{_base(cid)}/reports/kpis",
            headers=_auth(token),
            params={"date_from": "2020-01-01", "date_to": "2030-12-31"},
        )
        assert resp.status_code == 200

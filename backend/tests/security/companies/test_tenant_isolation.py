"""T111 — Tenant isolation tests.

Verifies that cross-tenant access to company resources is always denied
with HTTP 403.  The status must be 403 (not 404) to avoid leaking whether
the target company exists to an outsider.

Spec ref: spec.md §8 Authorization, AC-security-tenant.
"""

from __future__ import annotations

import json as _json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, name: str, email: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.json()}"
    return resp.json()["data"]["id"]


@pytest.fixture()
def two_tenants(test_client: TestClient, db_session: Session):
    """Seed two users each owning one company.

    Returns (token_a, company_a_id, token_b, company_b_id).
    """
    prefix = uuid.uuid4().hex[:8]

    user_a, pwd_a = create_test_user(db_session, email=f"tenant_a_{prefix}@example.com")
    user_b, pwd_b = create_test_user(db_session, email=f"tenant_b_{prefix}@example.com")

    token_a = _login(test_client, user_a.email, pwd_a)
    token_b = _login(test_client, user_b.email, pwd_b)

    company_a_id = _create_company(
        test_client, token_a, f"Tenant A Corp {prefix}", f"ta_{prefix}@example.com"
    )
    company_b_id = _create_company(
        test_client, token_b, f"Tenant B Corp {prefix}", f"tb_{prefix}@example.com"
    )

    return token_a, company_a_id, token_b, company_b_id


class TestCrossTenantIsolation:
    """User B cannot access User A's company resources."""

    def test_get_other_tenant_company_returns_403(
        self, test_client: TestClient, two_tenants: tuple
    ) -> None:
        _, company_a_id, token_b, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_a_id}", headers=_auth(token_b)
        )
        assert resp.status_code == 403

    def test_patch_other_tenant_company_returns_403(
        self, test_client: TestClient, two_tenants: tuple
    ) -> None:
        _, company_a_id, token_b, _ = two_tenants
        resp = test_client.patch(
            f"/api/v1/companies/{company_a_id}",
            json={"trade_name": "Injected"},
            headers=_auth(token_b),
        )
        assert resp.status_code == 403

    def test_delete_other_tenant_company_returns_403(
        self, test_client: TestClient, two_tenants: tuple
    ) -> None:
        _, company_a_id, token_b, _ = two_tenants
        resp = test_client.request(
            "DELETE",
            f"/api/v1/companies/{company_a_id}",
            content=_json.dumps({"reason": "attack", "confirm_delete": True}),
            headers={
                "Authorization": f"Bearer {token_b}",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 403

    def test_get_other_tenant_audit_log_returns_403(
        self, test_client: TestClient, two_tenants: tuple
    ) -> None:
        _, company_a_id, token_b, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_a_id}/audit-logs", headers=_auth(token_b)
        )
        assert resp.status_code == 403

    def test_post_other_tenant_address_returns_403(
        self, test_client: TestClient, two_tenants: tuple
    ) -> None:
        _, company_a_id, token_b, _ = two_tenants
        resp = test_client.post(
            f"/api/v1/companies/{company_a_id}/addresses",
            json={
                "address_type": "billing",
                "street_line_1": "1 Hack St",
                "city": "Hackville",
                "country": "US",
            },
            headers=_auth(token_b),
        )
        assert resp.status_code == 403

    def test_cross_tenant_response_is_not_404(
        self, test_client: TestClient, two_tenants: tuple
    ) -> None:
        """Existence of company_a must not be revealed to tenant_b via 404 path."""
        _, company_a_id, token_b, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_a_id}", headers=_auth(token_b)
        )
        assert resp.status_code == 403, (
            "Cross-tenant GET must return 403 (not 404) to prevent existence leakage. "
            f"Got {resp.status_code}"
        )
        assert resp.status_code != 404

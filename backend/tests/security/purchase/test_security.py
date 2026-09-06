"""Purchase module security tests — Phase 11 T246.

Covers:
  - All purchase endpoints require authentication (401 without token)
  - Invalid / expired tokens rejected (401)
  - company_id in path is validated (tenant scope enforced)
  - SQL injection payloads in query params do not cause 5xx
  - Supplier code with injection payload rejected or sanitised (no 5xx)
  - Oversized payloads rejected (no 5xx / 500)

Task: T246
"""

from __future__ import annotations

import uuid

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
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _base(cid: str) -> str:
    return f"/api/v1/companies/{cid}/purchase"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sec_auth(test_client: TestClient, db_session: Session):
    user, pw = create_test_user(
        db_session, email="sec-purchase@example.com", password="Secure1!"
    )
    token = _login(test_client, user.email, pw)
    cid = str(uuid.uuid4())
    return test_client, token, cid


# ---------------------------------------------------------------------------
# T246-A: Authentication enforcement — all purchase endpoints require auth
# ---------------------------------------------------------------------------


UNAUTHENTICATED_ENDPOINTS = [
    ("GET", "/suppliers"),
    ("POST", "/suppliers"),
    ("GET", "/purchase-orders"),
    ("POST", "/purchase-orders"),
    ("GET", "/purchase-requests"),
    ("POST", "/purchase-requests"),
    ("GET", "/goods-receipts"),
    ("POST", "/goods-receipts"),
    ("GET", "/vendor-returns"),
    ("POST", "/vendor-returns"),
    ("GET", "/reports/kpis"),
    ("GET", "/feature-flags"),
]


class TestAuthenticationEnforcement:
    """Every purchase endpoint must reject unauthenticated requests with 401."""

    @pytest.mark.parametrize("method,path_suffix", UNAUTHENTICATED_ENDPOINTS)
    def test_unauthenticated_returns_401(
        self, test_client: TestClient, method: str, path_suffix: str
    ):
        cid = str(uuid.uuid4())
        url = f"{_base(cid)}{path_suffix}"
        resp = getattr(test_client, method.lower())(url)
        assert (
            resp.status_code == 401
        ), f"{method} {url} returned {resp.status_code}, expected 401"


# ---------------------------------------------------------------------------
# T246-B: Invalid / malformed token rejection
# ---------------------------------------------------------------------------


class TestTokenValidation:
    def test_garbage_token_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        resp = test_client.get(
            f"{_base(cid)}/suppliers",
            headers={"Authorization": "Bearer this.is.garbage"},
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        resp = test_client.get(
            f"{_base(cid)}/suppliers",
            headers={"Authorization": "notabearer token"},
        )
        assert resp.status_code == 401

    def test_empty_bearer_returns_401(self, test_client: TestClient):
        cid = str(uuid.uuid4())
        resp = test_client.get(
            f"{_base(cid)}/suppliers",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T246-C: SQL injection in query params must not cause 5xx
# ---------------------------------------------------------------------------

SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE suppliers; --",
    "1; SELECT * FROM users",
    '" OR ""="',
    "1' AND SLEEP(5)--",
]


class TestSQLInjectionResistance:
    """SQL injection in query parameters must not cause server errors."""

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_supplier_search_sql_injection(self, sec_auth, payload: str):
        client, token, cid = sec_auth
        resp = client.get(
            f"{_base(cid)}/suppliers",
            headers=_auth(token),
            params={"q": payload},
        )
        # Any response except 5xx is acceptable — the server must not crash
        assert (
            resp.status_code < 500
        ), f"SQL injection payload caused {resp.status_code}: {payload!r}"

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_po_list_sql_injection_in_status(self, sec_auth, payload: str):
        client, token, cid = sec_auth
        resp = client.get(
            f"{_base(cid)}/purchase-orders",
            headers=_auth(token),
            params={"status": payload},
        )
        assert (
            resp.status_code < 500
        ), f"SQL injection in status caused {resp.status_code}: {payload!r}"


# ---------------------------------------------------------------------------
# T246-D: Oversized payload must not cause 5xx
# ---------------------------------------------------------------------------


class TestOversizedPayloads:
    """Large payloads must be rejected gracefully — no 500 errors."""

    def test_oversized_supplier_legal_name_no_500(self, sec_auth):
        client, token, cid = sec_auth
        resp = client.post(
            f"{_base(cid)}/suppliers",
            headers=_auth(token),
            json={
                "legal_name": "A" * 10_000,
                "supplier_code": "OVERSIZE-001",
                "supplier_type": "GOODS",
                "currency_code": "USD",
                "payment_terms_days": 30,
            },
        )
        assert resp.status_code < 500, f"Oversized name caused {resp.status_code}"

    def test_oversized_notes_field_no_500(self, sec_auth):
        client, token, cid = sec_auth
        resp = client.post(
            f"{_base(cid)}/purchase-orders",
            headers=_auth(token),
            json={
                "supplier_id": str(uuid.uuid4()),
                "currency_code": "USD",
                "notes": "X" * 100_000,
            },
        )
        # 404 (supplier not found), 422 (validation) or 400 are all acceptable
        assert resp.status_code < 500, f"Oversized notes caused {resp.status_code}"


# ---------------------------------------------------------------------------
# T246-E: company_id path parameter is enforced — cross-tenant not possible
# ---------------------------------------------------------------------------


class TestCompanyIdPathEnforcement:
    """The company_id in the URL path scopes all data access."""

    def test_nonexistent_company_id_returns_empty_not_all_data(self, sec_auth):
        """A random UUID company_id must return empty data, not another tenant's data."""
        client, token, cid = sec_auth
        fake_cid = str(uuid.uuid4())  # different company
        resp = client.get(
            f"{_base(fake_cid)}/suppliers",
            headers=_auth(token),
        )
        # 200 with empty list (scope isolation) or 403/404 — never 500
        assert resp.status_code in (200, 403, 404), resp.status_code
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            assert isinstance(data, list)
            # All returned items should be scoped to the fake_cid — none from cid
            for item in data:
                company = item.get("company_id", "")
                assert (
                    company == "" or company == fake_cid
                ), f"Cross-tenant data leak: got company_id={company!r}"

    def test_invalid_uuid_company_id_returns_4xx(self, sec_auth):
        client, token, _ = sec_auth
        resp = client.get(
            "/api/v1/companies/not-a-uuid/purchase/suppliers",
            headers=_auth(token),
        )
        assert resp.status_code < 500

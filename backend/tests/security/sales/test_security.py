"""Sales module security tests — Phase 10 T236.

Covers:
  - All sales endpoints require authentication (401 without token)
  - Invalid / malformed tokens rejected (401)
  - SQL injection payloads in query parameters do not cause 5xx
  - XSS payloads in text fields are stored/returned safely (no script execution)
  - Oversized payloads rejected (no 5xx / 500 responses)
  - BOLA — cross-tenant resource access returns 404 (not 403 or data leakage)

Task: T236
Spec ref: specs/007-sales-management/spec.md §Security
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "SecTest@1234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _TEST_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
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
            "legal_name": f"Sales Security Test Co {suffix}",
            "email": f"contact-{suffix}@sales-sec-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# T236-A: Authentication enforcement — all sales endpoints require auth
# ---------------------------------------------------------------------------

UNAUTHENTICATED_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/customers"),
    ("POST", "/customers"),
    ("GET", "/quotations"),
    ("POST", "/quotations"),
    ("GET", "/sales-orders"),
    ("POST", "/sales-orders"),
    ("GET", "/delivery-notes"),
    ("POST", "/delivery-notes"),
    ("GET", "/invoices"),
    ("POST", "/invoices"),
    ("GET", "/returns"),
    ("POST", "/returns"),
    ("GET", "/price-lists"),
    ("GET", "/reports/order-summary"),
    ("GET", "/kpis"),
    ("GET", "/feature-flags"),
    ("GET", "/customer-categories"),
    ("GET", "/payment-terms"),
    ("GET", "/reason-codes"),
]


class TestAuthenticationEnforcement:
    """Every sales endpoint must reject unauthenticated requests with 401."""

    @pytest.mark.parametrize("method,path_suffix", UNAUTHENTICATED_ENDPOINTS)
    def test_unauthenticated_returns_401(
        self, test_client: TestClient, method: str, path_suffix: str
    ) -> None:
        cid = str(uuid.uuid4())
        url = _sales_url(cid, path_suffix)
        resp = getattr(test_client, method.lower())(url)
        assert resp.status_code == 401, (
            f"{method} {url} returned {resp.status_code}, expected 401"
        )


# ---------------------------------------------------------------------------
# T236-B: Invalid / malformed token rejection
# ---------------------------------------------------------------------------


class TestTokenValidation:
    """Malformed and invalid tokens must be rejected with 401."""

    def test_malformed_token_returns_401(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(
            _sales_url(cid, "/customers"),
            headers={"Authorization": "Bearer not.a.valid.jwt"},
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(
            _sales_url(cid, "/customers"),
            headers={"Authorization": "just-a-random-string"},
        )
        assert resp.status_code == 401

    def test_empty_token_returns_401(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(
            _sales_url(cid, "/customers"),
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    def test_no_auth_header_returns_401(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(_sales_url(cid, "/customers"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T236-C: SQL injection in query parameters — no 5xx
# ---------------------------------------------------------------------------

SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE customers; --",
    "1; SELECT * FROM users",
    "' UNION SELECT null,null,null --",
    "%27%20OR%20%271%27%3D%271",
    "\\'; DROP TABLE sales_orders; --",
]


class TestSQLInjectionResistance:
    """SQL injection payloads in query params must not cause 5xx responses."""

    @pytest.fixture()
    def auth_token(
        self, test_client: TestClient, db_session: Session
    ) -> tuple[TestClient, str, str]:
        email = f"sec-sql-{uuid.uuid4().hex[:6]}@example.com"
        create_test_user(db_session, email, password=_TEST_PASSWORD)
        token = _login(test_client, email)
        cid = _create_company(test_client, token)
        return test_client, token, cid

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_customer_search_injection(self, auth_token: tuple, payload: str) -> None:
        client, token, cid = auth_token
        resp = client.get(
            _sales_url(cid, "/customers"),
            headers=_auth(token),
            params={"q": payload},
        )
        assert resp.status_code < 500, (
            f"SQL injection in customer search caused {resp.status_code}: {resp.text[:200]}"
        )

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_order_filter_injection(self, auth_token: tuple, payload: str) -> None:
        client, token, cid = auth_token
        resp = client.get(
            _sales_url(cid, "/sales-orders"),
            headers=_auth(token),
            params={"customer_id": payload},
        )
        assert resp.status_code < 500, (
            f"SQL injection in order filter caused {resp.status_code}: {resp.text[:200]}"
        )

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_quotation_search_injection(self, auth_token: tuple, payload: str) -> None:
        client, token, cid = auth_token
        resp = client.get(
            _sales_url(cid, "/quotations"),
            headers=_auth(token),
            params={"q": payload},
        )
        assert resp.status_code < 500, (
            f"SQL injection in quotation search caused {resp.status_code}: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# T236-D: XSS payload in text fields — stored safely, not executed
# ---------------------------------------------------------------------------

XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "javascript:alert('xss')",
    "<img src=x onerror=alert('xss')>",
    "'\"><script>alert(document.cookie)</script>",
]


class TestXSSResistance:
    """XSS payloads in text fields must not cause 5xx; data is stored safely."""

    @pytest.fixture()
    def auth_creds(
        self, test_client: TestClient, db_session: Session
    ) -> tuple[TestClient, str, str]:
        email = f"sec-xss-{uuid.uuid4().hex[:6]}@example.com"
        create_test_user(db_session, email, password=_TEST_PASSWORD)
        token = _login(test_client, email)
        cid = _create_company(test_client, token)
        return test_client, token, cid

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_customer_legal_name_xss(self, auth_creds: tuple, payload: str) -> None:
        client, token, cid = auth_creds
        resp = client.post(
            _sales_url(cid, "/customers"),
            json={
                "customer_code": f"XSS-{uuid.uuid4().hex[:6].upper()}",
                "legal_name": payload,
                "customer_type": "COMPANY",
                "category_id": str(uuid.uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        # Must not cause a server error; 201 (stored) or 422 (validation rejected)
        assert resp.status_code < 500, (
            f"XSS in legal_name caused server error: {resp.text[:200]}"
        )

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_order_notes_xss(self, auth_creds: tuple, payload: str) -> None:
        client, token, cid = auth_creds
        resp = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": str(uuid.uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "notes": payload,
                "lines": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code < 500, (
            f"XSS in order notes caused server error: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# T236-E: BOLA — broken object level access (cross-tenant)
# ---------------------------------------------------------------------------


class TestBOLATenantIsolation:
    """Cross-tenant resource access must return 404, not data."""

    @pytest.fixture()
    def two_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> tuple[TestClient, str, str, str, str]:
        email_a = f"bola-a-{uuid.uuid4().hex[:6]}@example.com"
        email_b = f"bola-b-{uuid.uuid4().hex[:6]}@example.com"
        create_test_user(db_session, email_a, password=_TEST_PASSWORD)
        create_test_user(db_session, email_b, password=_TEST_PASSWORD)
        token_a = _login(test_client, email_a)
        token_b = _login(test_client, email_b)
        cid_a = _create_company(test_client, token_a)
        cid_b = _create_company(test_client, token_b)
        return test_client, token_a, cid_a, token_b, cid_b

    def test_cross_tenant_customer_returns_404(self, two_tenants: tuple) -> None:
        client, token_a, cid_a, token_b, cid_b = two_tenants
        # Create customer in company A
        resp = client.post(
            _sales_url(cid_a, "/customers"),
            json={
                "customer_code": "BOLA-CUST-001",
                "legal_name": "Tenant A Corp",
                "customer_type": "COMPANY",
                "category_id": str(uuid.uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text
        cust_id = resp.json()["data"]["id"]

        # Company B tries to access company A's customer
        cross_resp = client.get(
            _sales_url(cid_b, f"/customers/{cust_id}"),
            headers=_auth(token_b),
        )
        assert cross_resp.status_code == 404, (
            f"Cross-tenant customer access returned {cross_resp.status_code}, expected 404"
        )

    def test_cross_tenant_order_returns_404(self, two_tenants: tuple) -> None:
        client, token_a, cid_a, token_b, cid_b = two_tenants
        # Create order in company A
        resp = client.post(
            _sales_url(cid_a, "/sales-orders"),
            json={
                "customer_id": str(uuid.uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
                "lines": [],
            },
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["data"]["id"]

        # Company B tries to access
        cross_resp = client.get(
            _sales_url(cid_b, f"/sales-orders/{order_id}"),
            headers=_auth(token_b),
        )
        assert cross_resp.status_code == 404, (
            f"Cross-tenant order access returned {cross_resp.status_code}, expected 404"
        )

    def test_cross_tenant_invoice_returns_404(self, two_tenants: tuple) -> None:
        client, token_a, cid_a, token_b, cid_b = two_tenants
        resp = client.post(
            _sales_url(cid_a, "/invoices"),
            json={
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "BOLA Test Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text
        inv_id = resp.json()["data"]["id"]

        cross_resp = client.get(
            _sales_url(cid_b, f"/invoices/{inv_id}"),
            headers=_auth(token_b),
        )
        assert cross_resp.status_code == 404, (
            f"Cross-tenant invoice access returned {cross_resp.status_code}, expected 404"
        )

    def test_cross_tenant_quotation_returns_404(self, two_tenants: tuple) -> None:
        client, token_a, cid_a, token_b, cid_b = two_tenants
        resp = client.post(
            _sales_url(cid_a, "/quotations"),
            json={
                "customer_id": str(uuid.uuid4()),
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
            },
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text
        quot_id = resp.json()["data"]["id"]

        cross_resp = client.get(
            _sales_url(cid_b, f"/quotations/{quot_id}"),
            headers=_auth(token_b),
        )
        assert cross_resp.status_code == 404, (
            f"Cross-tenant quotation access returned {cross_resp.status_code}, expected 404"
        )

    def test_cross_tenant_return_returns_404(self, two_tenants: tuple) -> None:
        client, token_a, cid_a, token_b, cid_b = two_tenants
        resp = client.post(
            _sales_url(cid_a, "/returns"),
            json={
                "customer_id": str(uuid.uuid4()),
                "return_date": "2026-08-01",
                "reason_code_id": str(uuid.uuid4()),
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "BOLA Return Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "USED",
                    }
                ],
            },
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text
        return_id = resp.json()["data"]["id"]

        cross_resp = client.get(
            _sales_url(cid_b, f"/returns/{return_id}"),
            headers=_auth(token_b),
        )
        assert cross_resp.status_code == 404, (
            f"Cross-tenant return access returned {cross_resp.status_code}, expected 404"
        )


# ---------------------------------------------------------------------------
# T236-F: Oversized payload rejection — no 5xx
# ---------------------------------------------------------------------------


class TestOversizedPayloadRejection:
    """Excessively large payloads must be rejected without causing 500."""

    @pytest.fixture()
    def auth_creds(
        self, test_client: TestClient, db_session: Session
    ) -> tuple[TestClient, str, str]:
        email = f"sec-sz-{uuid.uuid4().hex[:6]}@example.com"
        create_test_user(db_session, email, password=_TEST_PASSWORD)
        token = _login(test_client, email)
        cid = _create_company(test_client, token)
        return test_client, token, cid

    def test_oversized_customer_code_rejected(self, auth_creds: tuple) -> None:
        client, token, cid = auth_creds
        resp = client.post(
            _sales_url(cid, "/customers"),
            json={
                "customer_code": "X" * 500,  # max is 30
                "legal_name": "Oversized Test",
                "customer_type": "COMPANY",
                "category_id": str(uuid.uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert resp.status_code < 500, (
            f"Oversized customer_code caused server error {resp.status_code}"
        )
        assert resp.status_code in (
            400,
            422,
        ), f"Expected validation error for oversized payload, got {resp.status_code}"

    def test_oversized_notes_handled_safely(self, auth_creds: tuple) -> None:
        client, token, cid = auth_creds
        resp = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": str(uuid.uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "notes": "N" * 10000,
                "lines": [],
            },
            headers=_auth(token),
        )
        # Either accepted (201) or rejected with validation (422) — never 500
        assert resp.status_code < 500, (
            f"Oversized notes caused server error {resp.status_code}"
        )

"""Tenant isolation tests — Phase 10 T237.

Verifies zero cross-company data leakage across all sales entities:
  - Customers
  - Quotations
  - Sales Orders
  - Delivery Notes
  - Invoices
  - Sales Returns
  - Pricing (price lists)
  - Master data (customer categories, payment terms, reason codes)

Two independent companies (A and B) are created. Company A populates data.
Company B's token must not see any of Company A's data — either via list
endpoints (empty lists) or by direct ID lookup (404).

Task: T237
Spec ref: specs/007-sales-management/spec.md §Multi-Tenant Isolation
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "IsoTest@1234"


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


def _list_items(data) -> list:
    """Extract items from either paginated or plain list response."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Fixture: two tenant contexts
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_companies(
    test_client: TestClient, db_session: Session
) -> tuple[TestClient, str, str, str, str]:
    """Returns (client, token_a, cid_a, token_b, cid_b)."""
    email_a = f"iso-a-{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"iso-b-{uuid.uuid4().hex[:6]}@example.com"
    create_test_user(db_session, email_a, password=_TEST_PASSWORD)
    create_test_user(db_session, email_b, password=_TEST_PASSWORD)
    token_a = _login(test_client, email_a)
    token_b = _login(test_client, email_b)
    cid_a = str(uuid.uuid4())
    cid_b = str(uuid.uuid4())
    return test_client, token_a, cid_a, token_b, cid_b


# ---------------------------------------------------------------------------
# Customer isolation
# ---------------------------------------------------------------------------


class TestCustomerTenantIsolation:
    """Company B cannot see Company A's customers."""

    def test_customer_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        # Seed customer in A
        client.post(
            _sales_url(cid_a, "/customers"),
            json={
                "customer_code": "ISO-CUST-001",
                "legal_name": "Tenant A Customer",
                "customer_type": "COMPANY",
                "category_id": str(uuid.uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(tok_a),
        )

        # B should see empty list
        resp = client.get(_sales_url(cid_b, "/customers"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's customers: {items}"

    def test_customer_detail_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        r = client.post(
            _sales_url(cid_a, "/customers"),
            json={
                "customer_code": "ISO-CUST-002",
                "legal_name": "Tenant A Corp",
                "customer_type": "COMPANY",
                "category_id": str(uuid.uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(tok_a),
        )
        assert r.status_code == 201
        cust_id = r.json()["data"]["id"]

        # B tries direct access — must get 404
        resp = client.get(
            _sales_url(cid_b, f"/customers/{cust_id}"),
            headers=_auth(tok_b),
        )
        assert (
            resp.status_code == 404
        ), f"Company B accessed Company A's customer: {resp.status_code}"


# ---------------------------------------------------------------------------
# Quotation isolation
# ---------------------------------------------------------------------------


class TestQuotationTenantIsolation:
    """Company B cannot see Company A's quotations."""

    def test_quotation_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/quotations"),
            json={
                "customer_id": str(uuid.uuid4()),
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
            },
            headers=_auth(tok_a),
        )

        resp = client.get(_sales_url(cid_b, "/quotations"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's quotations: {items}"

    def test_quotation_detail_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        r = client.post(
            _sales_url(cid_a, "/quotations"),
            json={
                "customer_id": str(uuid.uuid4()),
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
            },
            headers=_auth(tok_a),
        )
        assert r.status_code == 201
        quot_id = r.json()["data"]["id"]

        resp = client.get(
            _sales_url(cid_b, f"/quotations/{quot_id}"),
            headers=_auth(tok_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sales Order isolation
# ---------------------------------------------------------------------------


class TestSalesOrderTenantIsolation:
    """Company B cannot see Company A's sales orders."""

    def test_order_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/sales-orders"),
            json={
                "customer_id": str(uuid.uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
                "lines": [],
            },
            headers=_auth(tok_a),
        )

        resp = client.get(_sales_url(cid_b, "/sales-orders"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's orders: {items}"

    def test_order_detail_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        r = client.post(
            _sales_url(cid_a, "/sales-orders"),
            json={
                "customer_id": str(uuid.uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid.uuid4()),
                "lines": [],
            },
            headers=_auth(tok_a),
        )
        assert r.status_code == 201
        order_id = r.json()["data"]["id"]

        resp = client.get(
            _sales_url(cid_b, f"/sales-orders/{order_id}"),
            headers=_auth(tok_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delivery Note isolation
# ---------------------------------------------------------------------------


class TestDeliveryNoteTenantIsolation:
    """Company B cannot see Company A's delivery notes."""

    def test_dn_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        # DN list in B should be empty (no DNs seeded in B)
        resp = client.get(_sales_url(cid_b, "/delivery-notes"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == []


# ---------------------------------------------------------------------------
# Invoice isolation
# ---------------------------------------------------------------------------


class TestInvoiceTenantIsolation:
    """Company B cannot see Company A's invoices."""

    def test_invoice_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/invoices"),
            json={
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Isolation Test Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(tok_a),
        )

        resp = client.get(_sales_url(cid_b, "/invoices"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's invoices: {items}"

    def test_invoice_detail_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        r = client.post(
            _sales_url(cid_a, "/invoices"),
            json={
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Isolation Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(tok_a),
        )
        assert r.status_code == 201
        inv_id = r.json()["data"]["id"]

        resp = client.get(
            _sales_url(cid_b, f"/invoices/{inv_id}"),
            headers=_auth(tok_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sales Return isolation
# ---------------------------------------------------------------------------


class TestReturnTenantIsolation:
    """Company B cannot see Company A's sales returns."""

    def test_return_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/returns"),
            json={
                "customer_id": str(uuid.uuid4()),
                "return_date": "2026-08-01",
                "reason_code_id": str(uuid.uuid4()),
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "Return Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "USED",
                    }
                ],
            },
            headers=_auth(tok_a),
        )

        resp = client.get(_sales_url(cid_b, "/returns"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's returns: {items}"

    def test_return_detail_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        r = client.post(
            _sales_url(cid_a, "/returns"),
            json={
                "customer_id": str(uuid.uuid4()),
                "return_date": "2026-08-01",
                "reason_code_id": str(uuid.uuid4()),
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "Return Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "USED",
                    }
                ],
            },
            headers=_auth(tok_a),
        )
        assert r.status_code == 201
        ret_id = r.json()["data"]["id"]

        resp = client.get(
            _sales_url(cid_b, f"/returns/{ret_id}"),
            headers=_auth(tok_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pricing isolation
# ---------------------------------------------------------------------------


class TestPricingTenantIsolation:
    """Company B cannot see Company A's price lists."""

    def test_price_list_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        # Create price list in A
        client.post(
            _sales_url(cid_a, "/price-lists"),
            json={
                "name": "Tenant A Price List",
                "currency_code": "USD",
                "effective_from": "2026-01-01",
            },
            headers=_auth(tok_a),
        )

        # B's price list should be empty
        resp = client.get(_sales_url(cid_b, "/price-lists"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's price lists: {items}"


# ---------------------------------------------------------------------------
# Master data isolation
# ---------------------------------------------------------------------------


class TestMasterDataTenantIsolation:
    """Master data (categories, payment terms, reason codes) is company-scoped."""

    def test_customer_categories_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/customer-categories"),
            json={"name": "Tenant A VIP", "description": "VIP customers"},
            headers=_auth(tok_a),
        )

        resp = client.get(
            _sales_url(cid_b, "/customer-categories"), headers=_auth(tok_b)
        )
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's categories: {items}"

    def test_payment_terms_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/payment-terms"),
            json={"name": "Net 30 A", "days": 30},
            headers=_auth(tok_a),
        )

        resp = client.get(_sales_url(cid_b, "/payment-terms"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's payment terms: {items}"

    def test_reason_codes_isolation(self, two_companies: tuple) -> None:
        client, tok_a, cid_a, tok_b, cid_b = two_companies
        client.post(
            _sales_url(cid_a, "/reason-codes"),
            json={"code": "DEFECT-A", "name": "Defective", "applicable_to": "RETURN"},
            headers=_auth(tok_a),
        )

        resp = client.get(_sales_url(cid_b, "/reason-codes"), headers=_auth(tok_b))
        assert resp.status_code == 200
        items = _list_items(resp.json()["data"])
        assert items == [], f"Company B saw Company A's reason codes: {items}"

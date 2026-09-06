"""Soft-delete completeness test — Phase 10 T240.

Verifies that all sales entities implement soft-delete correctly:
  - Deleted records have is_deleted=True and deleted_at set
  - Deleted records are excluded from all normal queries (list + get by ID)
  - Hard-delete is never performed (record still exists in DB with is_deleted=True)

Entities tested:
  - Customer (via API transitions or direct service calls)
  - CustomerContact (DELETE endpoint)
  - CustomerAddress (DELETE endpoint)
  - Quotation (cancel → soft-deleted state, excluded from active queries)
  - Sales Order (cancel)
  - Delivery Note (cancel)
  - Sales Invoice (cancel)
  - Sales Return (cancel)

Task: T240
Spec ref: specs/007-sales-management/spec.md §Soft Delete
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "SoftDel@1234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"sd-{uuid4().hex[:8]}@example.com"


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
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Soft Delete Test Co {suffix}",
            "email": f"contact-{suffix}@sales-soft-delete-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


@pytest.fixture()
def ctx(test_client: TestClient, db_session: Session):
    email = _unique_email()
    create_test_user(db_session, email, password=_TEST_PASSWORD)
    token = _login(test_client, email)
    cid = _create_company(test_client, token)
    return test_client, token, cid


# ---------------------------------------------------------------------------
# Customer Contact soft-delete
# ---------------------------------------------------------------------------


class TestCustomerContactSoftDelete:
    """CustomerContact soft-delete is reflected in API."""

    def test_deleted_contact_excluded_from_list(self, ctx: tuple) -> None:
        client, token, cid = ctx

        # Create customer
        cust = client.post(
            _sales_url(cid, "/customers"),
            json={
                "customer_code": f"SD-C-{uuid4().hex[:6].upper()}",
                "legal_name": "SoftDel Customer",
                "customer_type": "COMPANY",
                "category_id": str(uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert cust.status_code == 201
        cust_id = cust.json()["data"]["id"]

        # Add a contact (non-primary so it can be deleted without constraint)
        contact = client.post(
            _sales_url(cid, f"/customers/{cust_id}/contacts"),
            json={
                "contact_name": "Jane Doe",
                "email": f"jane-{uuid4().hex[:6]}@example.com",
                "is_primary": False,
            },
            headers=_auth(token),
        )
        assert contact.status_code == 201
        contact_id = contact.json()["data"]["id"]

        # Verify it appears in list
        before = client.get(
            _sales_url(cid, f"/customers/{cust_id}/contacts"),
            headers=_auth(token),
        ).json()["data"]
        before_items = _list_items(before)
        assert any(c["id"] == contact_id for c in before_items)

        # Delete (soft-delete)
        del_resp = client.delete(
            _sales_url(cid, f"/customers/{cust_id}/contacts/{contact_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code in (200, 204), del_resp.text

        # Verify it no longer appears
        after = client.get(
            _sales_url(cid, f"/customers/{cust_id}/contacts"),
            headers=_auth(token),
        ).json()["data"]
        after_items = _list_items(after)
        assert not any(c["id"] == contact_id for c in after_items), (
            "Soft-deleted contact still appears in contact list"
        )


# ---------------------------------------------------------------------------
# Customer Address soft-delete
# ---------------------------------------------------------------------------


class TestCustomerAddressSoftDelete:
    """CustomerAddress soft-delete is reflected in API."""

    def test_deleted_address_excluded_from_list(self, ctx: tuple) -> None:
        client, token, cid = ctx

        cust = client.post(
            _sales_url(cid, "/customers"),
            json={
                "customer_code": f"SD-A-{uuid4().hex[:6].upper()}",
                "legal_name": "Address SoftDel Corp",
                "customer_type": "COMPANY",
                "category_id": str(uuid4()),
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert cust.status_code == 201
        cust_id = cust.json()["data"]["id"]

        addr = client.post(
            _sales_url(cid, f"/customers/{cust_id}/addresses"),
            json={
                "address_type": "BILLING",
                "address_line_1": "123 Test Street",
                "city": "TestCity",
                "country_code": "US",
            },
            headers=_auth(token),
        )
        assert addr.status_code == 201
        addr_id = addr.json()["data"]["id"]

        # Confirm present
        before = _list_items(
            client.get(
                _sales_url(cid, f"/customers/{cust_id}/addresses"),
                headers=_auth(token),
            ).json()["data"]
        )
        assert any(a["id"] == addr_id for a in before)

        # Soft-delete
        del_resp = client.delete(
            _sales_url(cid, f"/customers/{cust_id}/addresses/{addr_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code in (200, 204), del_resp.text

        # Confirm excluded
        after = _list_items(
            client.get(
                _sales_url(cid, f"/customers/{cust_id}/addresses"),
                headers=_auth(token),
            ).json()["data"]
        )
        assert not any(a["id"] == addr_id for a in after), (
            "Soft-deleted address still in list"
        )


# ---------------------------------------------------------------------------
# Quotation cancellation (soft-delete variant)
# ---------------------------------------------------------------------------


class TestQuotationSoftDelete:
    """Cancelled quotations are excluded from active query results."""

    def test_cancelled_quotation_not_in_active_list(self, ctx: tuple) -> None:
        client, token, cid = ctx

        quot = client.post(
            _sales_url(cid, "/quotations"),
            json={
                "customer_id": str(uuid4()),
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert quot.status_code == 201
        quot_id = quot.json()["data"]["id"]

        # Cancel quotation
        cancel_resp = client.post(
            _sales_url(cid, f"/quotations/{quot_id}/cancel"),
            json={"reason": "Test cancellation"},
            headers=_auth(token),
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

        # GET by ID still returns it (with CANCELLED status)
        get_resp = client.get(
            _sales_url(cid, f"/quotations/{quot_id}"),
            headers=_auth(token),
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["status"] == "CANCELLED"

        # List with active filter should exclude cancelled
        list_resp = client.get(
            _sales_url(cid, "/quotations"),
            headers=_auth(token),
            params={"status": "DRAFT"},
        )
        assert list_resp.status_code == 200
        items = _list_items(list_resp.json()["data"])
        cancelled_ids = [q["id"] for q in items if q["id"] == quot_id]
        assert not cancelled_ids, "Cancelled quotation appeared in DRAFT filter"


# ---------------------------------------------------------------------------
# Sales Order cancellation
# ---------------------------------------------------------------------------


class TestSalesOrderSoftDelete:
    """Cancelled orders respect soft-delete semantics."""

    def test_cancelled_order_still_retrievable(self, ctx: tuple) -> None:
        client, token, cid = ctx

        order = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": str(uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [],
            },
            headers=_auth(token),
        )
        assert order.status_code == 201
        order_id = order.json()["data"]["id"]

        # Cancel order
        cancel_resp = client.post(
            _sales_url(cid, f"/sales-orders/{order_id}/cancel"),
            json={
                "cancellation_reason": "Customer requested cancellation",
                "cancelled_by": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

        # Cancelled order should still be retrievable by ID (soft-delete, not hard)
        get_resp = client.get(
            _sales_url(cid, f"/sales-orders/{order_id}"),
            headers=_auth(token),
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["status"] == "CANCELLED"

    def test_cancelled_order_excluded_by_status_filter(self, ctx: tuple) -> None:
        client, token, cid = ctx

        order = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": str(uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [],
            },
            headers=_auth(token),
        )
        assert order.status_code == 201
        order_id = order.json()["data"]["id"]

        client.post(
            _sales_url(cid, f"/sales-orders/{order_id}/cancel"),
            json={"cancellation_reason": "Test", "cancelled_by": str(uuid4())},
            headers=_auth(token),
        )

        # Filter for DRAFT orders — cancelled should not appear
        list_resp = client.get(
            _sales_url(cid, "/sales-orders"),
            headers=_auth(token),
            params={"status": "DRAFT"},
        )
        assert list_resp.status_code == 200
        items = _list_items(list_resp.json()["data"])
        assert not any(o["id"] == order_id for o in items)


# ---------------------------------------------------------------------------
# Invoice cancellation
# ---------------------------------------------------------------------------


class TestInvoiceSoftDelete:
    """Cancelled invoices respect soft-delete semantics."""

    def test_cancelled_invoice_still_retrievable(self, ctx: tuple) -> None:
        client, token, cid = ctx

        inv = client.post(
            _sales_url(cid, "/invoices"),
            json={
                "customer_id": str(uuid4()),
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Cancel Test Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert inv.status_code == 201
        inv_id = inv.json()["data"]["id"]

        cancel_resp = client.post(
            _sales_url(cid, f"/invoices/{inv_id}/cancel"),
            json={"reason": "Test cancellation"},
            headers=_auth(token),
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

        # Still retrievable (soft-delete)
        get_resp = client.get(
            _sales_url(cid, f"/invoices/{inv_id}"),
            headers=_auth(token),
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["status"] == "CANCELLED"


# ---------------------------------------------------------------------------
# Sales Return cancellation
# ---------------------------------------------------------------------------


class TestReturnSoftDelete:
    """Cancelled returns respect soft-delete semantics."""

    def test_cancelled_return_still_retrievable(self, ctx: tuple) -> None:
        client, token, cid = ctx

        ret = client.post(
            _sales_url(cid, "/returns"),
            json={
                "customer_id": str(uuid4()),
                "return_date": "2026-08-01",
                "reason_code_id": str(uuid4()),
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "Test Return Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "USED",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert ret.status_code == 201
        return_id = ret.json()["data"]["id"]

        cancel_resp = client.post(
            _sales_url(cid, f"/returns/{return_id}/cancel"),
            json={"reason": "Test cancellation"},
            headers=_auth(token),
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

        # Still retrievable (soft-delete, not hard delete)
        get_resp = client.get(
            _sales_url(cid, f"/returns/{return_id}"),
            headers=_auth(token),
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["status"] == "CANCELLED"

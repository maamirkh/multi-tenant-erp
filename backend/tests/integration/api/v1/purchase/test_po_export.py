"""Integration tests for Purchase Order PDF Export — Phase 10 T240.

The PO export endpoint (/purchase-orders/{po_id}/export/pdf) returns a JSON
payload containing all PO fields suitable for client-side PDF rendering.

Full PDF generation (reportlab/WeasyPrint) is deferred to a future phase;
these tests verify the export payload structure and data completeness.

Covers:
  - Export returns 200 with correct structure for a DRAFT PO
  - Payload contains required fields: po_number, status, supplier_id,
    currency_code, total, lines[], charges[], notes
  - Lines and charges are serialised as lists
  - Export for a multi-line, multi-charge PO returns all data
  - 404 on non-existent PO
  - 401 on unauthenticated request
  - Tenant isolation: cannot export another company's PO

Task: T240
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/purchase-orders{path}"


def _supplier_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/suppliers{path}"


def _create_supplier(
    client: TestClient, token: str, company_id: str, code: str = "SUP-EXPORT"
) -> str:
    resp = client.post(
        _supplier_url(company_id),
        headers=_auth(token),
        json={
            "legal_name": "Export Test Supplier Ltd",
            "supplier_code": code,
            "supplier_type": "GOODS",
            "currency_code": "USD",
            "payment_terms_days": 30,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    supplier_id = resp.json()["data"]["id"]
    # Activate supplier
    client.post(
        _supplier_url(company_id, f"/{supplier_id}/activate"), headers=_auth(token)
    )
    return supplier_id


def _create_po(
    client: TestClient, token: str, company_id: str, supplier_id: str
) -> str:
    resp = client.post(
        _url(company_id),
        headers=_auth(token),
        json={
            "supplier_id": supplier_id,
            "currency_code": "USD",
            "notes": "Export test PO",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


def _add_line(
    client: TestClient,
    token: str,
    company_id: str,
    po_id: str,
    description: str = "Test Item",
    qty: str = "5.000",
    price: str = "100.00",
) -> str:
    resp = client.post(
        _url(company_id, f"/{po_id}/lines"),
        headers=_auth(token),
        json={
            "product_description": description,
            "quantity_ordered": qty,
            "unit_cost": price,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["lines"][-1]["id"]


def _add_charge(client: TestClient, token: str, company_id: str, po_id: str) -> None:
    client.post(
        _url(company_id, f"/{po_id}/charges"),
        headers=_auth(token),
        json={
            "charge_type": "FREIGHT",
            "amount": "50.00",
            "description": "Freight charge",
        },
    )


def _export_url(company_id: str, po_id: str) -> str:
    return _url(company_id, f"/{po_id}/export/pdf")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth(test_client: TestClient, db_session):
    user, pw = create_test_user(
        db_session, email="po-export@example.com", password="Export1!"
    )
    token = _login(test_client, user.email, pw)
    cid = str(uuid.uuid4())
    return test_client, token, cid


@pytest.fixture()
def auth2(test_client: TestClient, db_session):
    user, pw = create_test_user(
        db_session, email="po-export-b@example.com", password="Export2!"
    )
    token = _login(test_client, user.email, pw)
    cid = str(uuid.uuid4())
    return test_client, token, cid


@pytest.fixture()
def po_id(auth):
    client, token, cid = auth
    supplier_id = _create_supplier(client, token, cid, code="SUP-EXP-01")
    return _create_po(client, token, cid, supplier_id)


# ===========================================================================
# Test: Export payload structure
# ===========================================================================


class TestPOExportStructure:
    """Validate the export response structure and required fields."""

    def test_export_returns_200_for_draft_po(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        assert resp.status_code == 200, resp.text

    def test_export_contains_po_number(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "po_number" in data
        assert data["po_number"].startswith("PO-")

    def test_export_contains_status(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "status" in data
        assert data["status"] == "DRAFT"

    def test_export_contains_supplier_id(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "supplier_id" in data
        assert data["supplier_id"] is not None

    def test_export_contains_currency_code(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "currency_code" in data
        assert data["currency_code"] == "USD"

    def test_export_contains_total(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "total" in data
        # total is a decimal string
        float(data["total"])  # must be parseable as decimal

    def test_export_contains_lines_list(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "lines" in data
        assert isinstance(data["lines"], list)

    def test_export_contains_charges_list(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "charges" in data
        assert isinstance(data["charges"], list)

    def test_export_contains_notes(self, auth, po_id):
        client, token, cid = auth
        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        data = resp.json()["data"]
        assert "notes" in data
        assert data["notes"] == "Export test PO"


# ===========================================================================
# Test: Multi-line, multi-charge PO export
# ===========================================================================


class TestPOExportMultiLineMultiCharge:
    """Export payload must include all lines and charges."""

    def test_export_includes_all_lines(self, auth):
        client, token, cid = auth
        supplier_id = _create_supplier(client, token, cid, code="SUP-EXP-02")
        po_id = _create_po(client, token, cid, supplier_id)

        # Add 3 lines
        _add_line(
            client, token, cid, po_id, description="Item A", qty="10.000", price="50.00"
        )
        _add_line(
            client, token, cid, po_id, description="Item B", qty="5.000", price="200.00"
        )
        _add_line(
            client, token, cid, po_id, description="Item C", qty="1.000", price="999.99"
        )

        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["lines"]) == 3

    def test_export_includes_all_charges(self, auth):
        client, token, cid = auth
        supplier_id = _create_supplier(client, token, cid, code="SUP-EXP-03")
        po_id = _create_po(client, token, cid, supplier_id)

        _add_line(client, token, cid, po_id)
        # Add 2 charges
        client.post(
            _url(cid, f"/{po_id}/charges"),
            headers=_auth(token),
            json={
                "charge_type": "FREIGHT",
                "amount": "50.00",
                "description": "Courier freight",
            },
        )
        client.post(
            _url(cid, f"/{po_id}/charges"),
            headers=_auth(token),
            json={
                "charge_type": "HANDLING",
                "amount": "25.00",
                "description": "Handling fee",
            },
        )

        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["charges"]) == 2

    def test_export_total_reflects_lines_and_charges(self, auth):
        """Total = (line subtotal) + (additional charges)."""
        client, token, cid = auth
        supplier_id = _create_supplier(client, token, cid, code="SUP-EXP-04")
        po_id = _create_po(client, token, cid, supplier_id)

        _add_line(
            client, token, cid, po_id, qty="2.000", price="100.00"
        )  # subtotal = 200
        client.post(
            _url(cid, f"/{po_id}/charges"),
            headers=_auth(token),
            json={
                "charge_type": "FREIGHT",
                "amount": "30.00",
                "description": "Courier freight",
            },
        )  # total should be 230

        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        total = float(data["total"])
        assert total == pytest.approx(230.0, abs=0.01)

    def test_line_fields_present(self, auth):
        """Each line in export contains expected fields."""
        client, token, cid = auth
        supplier_id = _create_supplier(client, token, cid, code="SUP-EXP-05")
        po_id = _create_po(client, token, cid, supplier_id)
        _add_line(client, token, cid, po_id, description="Field Check Item")

        resp = client.get(_export_url(cid, po_id), headers=_auth(token))
        assert resp.status_code == 200
        line = resp.json()["data"]["lines"][0]
        # Verify key line fields are present (schema uses product_description, quantity_ordered, unit_cost)
        assert "product_description" in line or "description" in line
        assert "quantity_ordered" in line or "quantity" in line or "qty" in line


# ===========================================================================
# Test: Error cases
# ===========================================================================


class TestPOExportErrors:
    def test_export_nonexistent_po_returns_404(self, auth):
        client, token, cid = auth
        fake_id = str(uuid.uuid4())
        resp = client.get(_export_url(cid, fake_id), headers=_auth(token))
        assert resp.status_code == 404

    def test_export_unauthenticated_returns_401(self, auth, po_id):
        client, _, cid = auth
        resp = client.get(_export_url(cid, po_id))
        assert resp.status_code == 401


# ===========================================================================
# Test: Tenant isolation
# ===========================================================================


class TestPOExportTenantIsolation:
    def test_cannot_export_other_company_po(self, auth, auth2, po_id):
        """Company B user cannot export Company A's PO."""
        client, _, cid_a = auth
        _, token_b, cid_b = auth2

        # Attempt export using company B's URL with company A's PO ID
        resp = client.get(
            _export_url(cid_b, po_id),
            headers=_auth(token_b),
        )
        # Should return 404 (not found in company B's scope)
        assert resp.status_code == 404

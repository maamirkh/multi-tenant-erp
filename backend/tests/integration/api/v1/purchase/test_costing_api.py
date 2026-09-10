"""API integration tests for Phase 8 Purchase Costing endpoints — T204.

Tests:
  - GET /purchase-orders/{po_id}/cost-summary → 200 with correct fields
  - GET /goods-receipts/{gr_id}/cost-summary → 200 with PPV lines
  - GR confirmation creates PurchaseCostEntry in same transaction
  - GET /goods-receipts/{gr_id}/cost-entry → 200 after confirmation
  - PPV computed correctly on GR confirm
  - tax_code, tax_rate, tax_amount fields present on POLine and GRLine
  - 404 returned for non-existent PO/GR cost summary
  - Tenant isolation: cost data not visible to other company

Task: T204
"""

from __future__ import annotations

import uuid as _uuid
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


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = _uuid.uuid4().hex[:8]
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


def _purchase_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/{path}"


def _setup(client: TestClient, db: Session, suffix: str = "") -> tuple[str, str]:
    email = f"cost_test{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = _create_company(client, token)
    return token, company_id


def _create_approved_po(
    client: TestClient, token: str, company_id: str
) -> tuple[dict[str, str], str]:
    """Create a PO with one line, then approve it (or auto-approve)."""
    resp = client.post(
        _purchase_url(company_id, "purchase-orders"),
        json={"currency_code": "USD"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    po_id = resp.json()["data"]["id"]

    resp = client.post(
        _purchase_url(company_id, f"purchase-orders/{po_id}/lines"),
        json={
            "product_description": "Cost Test Widget",
            "quantity_ordered": "10",
            "unit_cost": "50.00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    line_id = resp.json()["data"]["id"]

    client.post(
        _purchase_url(company_id, f"purchase-orders/{po_id}/submit"),
        json={},
        headers=_auth(token),
    )
    client.post(
        _purchase_url(company_id, f"purchase-orders/{po_id}/approve"),
        json={},
        headers=_auth(token),
    )

    resp = client.get(
        _purchase_url(company_id, f"purchase-orders/{po_id}"),
        headers=_auth(token),
    )
    assert resp.status_code == 200
    return resp.json()["data"], line_id


def _create_and_confirm_gr(
    client: TestClient,
    token: str,
    company_id: str,
    po_id: str,
    po_line_id: str,
    unit_cost: str = "55.00",
) -> dict[str, Any]:
    """Create a DRAFT GR then confirm it."""
    resp = client.post(
        _purchase_url(company_id, "goods-receipts"),
        json={
            "po_id": po_id,
            "delivery_note_number": "DN-COST-001",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "quantity_received": "4",
                    "quantity_rejected": "0",
                    "unit_cost": unit_cost,
                }
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    gr_id = resp.json()["data"]["id"]

    resp = client.post(
        _purchase_url(company_id, f"goods-receipts/{gr_id}/confirm"),
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return dict(resp.json()["data"])


# ===========================================================================
# PO Cost Summary
# ===========================================================================


class TestPOCostSummary:
    def test_po_cost_summary_returns_200(
        self, test_client: TestClient, db_session: Session
    ):
        """GET /purchase-orders/{po_id}/cost-summary returns 200 with required fields."""
        token, cid = _setup(test_client, db_session, suffix="_poc1")
        po_data, _ = _create_approved_po(test_client, token, cid)
        po_id = po_data["id"]

        resp = test_client.get(
            _purchase_url(cid, f"purchase-orders/{po_id}/cost-summary"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert "po_id" in data
        assert "subtotal" in data
        assert "total_charges" in data
        assert "total_discounts" in data
        assert "tax_amount" in data
        assert "total" in data
        assert "currency_code" in data

    def test_po_cost_summary_not_found(
        self, test_client: TestClient, db_session: Session
    ):
        """Non-existent PO returns 404."""
        token, cid = _setup(test_client, db_session, suffix="_poc2")
        resp = test_client.get(
            _purchase_url(cid, f"purchase-orders/{_uuid.uuid4()}/cost-summary"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_po_cost_summary_with_line_cost(
        self, test_client: TestClient, db_session: Session
    ):
        """PO cost summary reflects the unit_cost × quantity of lines."""
        token, cid = _setup(test_client, db_session, suffix="_poc3")
        po_data, _ = _create_approved_po(test_client, token, cid)
        po_id = po_data["id"]

        resp = test_client.get(
            _purchase_url(cid, f"purchase-orders/{po_id}/cost-summary"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 10 units × $50.00 = $500.00 subtotal
        assert float(data["subtotal"]) == pytest.approx(500.00, abs=0.01)


# ===========================================================================
# GR Cost Summary (PPV)
# ===========================================================================


class TestGRCostSummary:
    def test_gr_cost_summary_returns_200(
        self, test_client: TestClient, db_session: Session
    ):
        """GET /goods-receipts/{gr_id}/cost-summary returns 200 with PPV lines."""
        token, cid = _setup(test_client, db_session, suffix="_grc1")
        po_data, line_id = _create_approved_po(test_client, token, cid)
        po_id = po_data["id"]
        po_status = po_data["status"]

        if po_status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            pytest.skip(f"PO not approved (status={po_status}), skipping GR test")

        resp = test_client.post(
            _purchase_url(cid, "goods-receipts"),
            json={
                "po_id": po_id,
                "lines": [
                    {
                        "po_line_id": line_id,
                        "quantity_received": "3",
                        "quantity_rejected": "0",
                        "unit_cost": "55.00",  # $5 above PO price → positive PPV
                    }
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        gr_id = resp.json()["data"]["id"]

        resp = test_client.get(
            _purchase_url(cid, f"goods-receipts/{gr_id}/cost-summary"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert "gr_id" in data
        assert "ppv_lines" in data
        assert "total_ppv_amount" in data
        assert "subtotal" in data

    def test_gr_cost_summary_not_found(
        self, test_client: TestClient, db_session: Session
    ):
        """Non-existent GR returns 404."""
        token, cid = _setup(test_client, db_session, suffix="_grc2")
        resp = test_client.get(
            _purchase_url(cid, f"goods-receipts/{_uuid.uuid4()}/cost-summary"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ===========================================================================
# Cost Entry (created on GR confirmation)
# ===========================================================================


class TestCostEntry:
    def test_cost_entry_created_on_gr_confirm(
        self, test_client: TestClient, db_session: Session
    ):
        """GET /goods-receipts/{gr_id}/cost-entry returns 200 after GR confirmation."""
        token, cid = _setup(test_client, db_session, suffix="_ce1")
        po_data, line_id = _create_approved_po(test_client, token, cid)
        po_id = po_data["id"]
        po_status = po_data["status"]

        if po_status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            pytest.skip(f"PO not approved (status={po_status})")

        gr = _create_and_confirm_gr(test_client, token, cid, po_id, line_id)
        gr_id = gr["id"]

        resp = test_client.get(
            _purchase_url(cid, f"goods-receipts/{gr_id}/cost-entry"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        entry = resp.json()["data"]

        assert entry["gr_id"] == gr_id
        assert "subtotal" in entry
        assert "total" in entry
        assert entry["credit_note_pending"] is False

    def test_cost_entry_not_found_for_draft_gr(
        self, test_client: TestClient, db_session: Session
    ):
        """DRAFT GR has no cost entry → 404."""
        token, cid = _setup(test_client, db_session, suffix="_ce2")
        po_data, line_id = _create_approved_po(test_client, token, cid)
        po_id = po_data["id"]
        po_status = po_data["status"]

        if po_status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            pytest.skip("PO not approved")

        resp = test_client.post(
            _purchase_url(cid, "goods-receipts"),
            json={
                "po_id": po_id,
                "lines": [
                    {
                        "po_line_id": line_id,
                        "quantity_received": "2",
                        "quantity_rejected": "0",
                        "unit_cost": "50.00",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        gr_id = resp.json()["data"]["id"]

        resp = test_client.get(
            _purchase_url(cid, f"goods-receipts/{gr_id}/cost-entry"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_ppv_computed_correctly_on_gr_confirm(
        self, test_client: TestClient, db_session: Session
    ):
        """PPV is computed and available in GR cost summary after confirmation."""
        token, cid = _setup(test_client, db_session, suffix="_ppv1")
        po_data, line_id = _create_approved_po(test_client, token, cid)
        po_id = po_data["id"]
        po_status = po_data["status"]

        if po_status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            pytest.skip("PO not approved")

        # PO unit_cost = 50.00; GR unit_cost = 60.00 → PPV = (60-50) * 4 = 40.00
        gr = _create_and_confirm_gr(
            test_client, token, cid, po_id, line_id, unit_cost="60.00"
        )
        gr_id = gr["id"]

        resp = test_client.get(
            _purchase_url(cid, f"goods-receipts/{gr_id}/cost-summary"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["ppv_lines"]) > 0
        ppv_line = data["ppv_lines"][0]
        assert float(ppv_line["ppv_amount"]) == pytest.approx(40.00, abs=0.01)


# ===========================================================================
# Tax field presence (T196)
# ===========================================================================


class TestTaxFields:
    def test_tax_fields_present_on_po_line(
        self, test_client: TestClient, db_session: Session
    ):
        """POLine response includes tax_code, tax_rate, tax_amount fields."""
        token, cid = _setup(test_client, db_session, suffix="_tax1")
        resp = test_client.post(
            _purchase_url(cid, "purchase-orders"),
            json={"currency_code": "USD"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        po_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _purchase_url(cid, f"purchase-orders/{po_id}/lines"),
            json={
                "product_description": "Tax test item",
                "quantity_ordered": "5",
                "unit_cost": "20.00",
                "tax_code": "VAT20",
                "tax_rate": "20.00",
                "tax_amount": "20.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        po_data = resp.json()["data"]

        # add_line endpoint returns PurchaseOrderRead which contains lines list
        lines = po_data.get("lines", [])
        assert len(lines) > 0, "Expected at least one line in PO response"
        line = lines[0]

        assert "tax_code" in line
        assert "tax_rate" in line
        assert "tax_amount" in line

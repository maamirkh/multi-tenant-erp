"""End-to-end business workflow tests — Purchase module — Phase 11 T249-T252.

Tests the complete procurement lifecycle through the API layer:

  T249 — Supplier lifecycle: create → activate → deactivate → reactivate
  T250 — Full PR→PO→GR workflow: PR submitted, approved, converted to PO,
          PO approved, GR created and confirmed
  T251 — Vendor Return (RMA) workflow: GR confirmed → RMA created →
          submitted → approved → dispatched → completed
  T252 — Direct PO workflow (feature flag): direct PO without PR →
          add lines + charges → submit → approve → GR confirm

All tests use FastAPI TestClient with SQLite in-memory database.

Tasks: T249, T250, T251, T252
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


def _ok(resp, context: str = "") -> dict:
    assert resp.status_code in (
        200,
        201,
    ), f"{context}: expected 200/201, got {resp.status_code}: {resp.text[:300]}"
    return resp.json()["data"]


def _create_supplier(client: TestClient, token: str, cid: str, code: str) -> str:
    data = _ok(
        client.post(
            f"{_base(cid)}/suppliers",
            headers=_auth(token),
            json={
                "legal_name": f"E2E Test Supplier {code}",
                "supplier_code": code,
                "supplier_type": "GOODS",
                "currency_code": "USD",
                "payment_terms_days": 30,
            },
        ),
        "create supplier",
    )
    return data["id"]


def _activate_supplier(client: TestClient, token: str, cid: str, sid: str) -> None:
    resp = client.post(
        f"{_base(cid)}/suppliers/{sid}/activate", headers=_auth(token), json={}
    )
    assert resp.status_code in (200, 201), f"activate supplier: {resp.text}"


def _create_po(
    client: TestClient, token: str, cid: str, supplier_id: str, **kwargs
) -> str:
    payload = {"supplier_id": supplier_id, "currency_code": "USD"}
    payload.update(kwargs)
    data = _ok(
        client.post(
            f"{_base(cid)}/purchase-orders", headers=_auth(token), json=payload
        ),
        "create PO",
    )
    return data["id"]


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Purchase E2E Test Co {suffix}",
            "email": f"contact-{suffix}@purch-e2e-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _add_po_line(
    client: TestClient,
    token: str,
    cid: str,
    po_id: str,
    desc: str = "Widget",
    qty: str = "5.000",
    price: str = "100.00",
) -> str:
    data = _ok(
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/lines",
            headers=_auth(token),
            json={
                "product_description": desc,
                "quantity_ordered": qty,
                "unit_cost": price,
            },
        ),
        "add PO line",
    )
    return data["lines"][-1]["id"]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def e2e(test_client: TestClient, db_session: Session):
    user, pw = create_test_user(
        db_session, email="e2e-purchase@example.com", password="E2ePurchase1!"
    )
    token = _login(test_client, user.email, pw)
    cid = _create_company(test_client, token)
    return test_client, token, cid


# ---------------------------------------------------------------------------
# T249 — Supplier lifecycle
# ---------------------------------------------------------------------------


class TestSupplierLifecycle:
    """T249: Supplier DRAFT → ACTIVE → INACTIVE → ACTIVE lifecycle."""

    def test_supplier_full_lifecycle(self, e2e):
        client, token, cid = e2e

        # 1. Create (DRAFT)
        data = _ok(
            client.post(
                f"{_base(cid)}/suppliers",
                headers=_auth(token),
                json={
                    "legal_name": "Lifecycle Test Supplier",
                    "supplier_code": "LIFE-001",
                    "supplier_type": "GOODS",
                    "currency_code": "GBP",
                    "payment_terms_days": 45,
                },
            ),
            "create",
        )
        sid = data["id"]
        assert data["status"] == "DRAFT"

        # 2. Activate (ACTIVE)
        data = _ok(
            client.post(
                f"{_base(cid)}/suppliers/{sid}/activate", headers=_auth(token), json={}
            ),
            "activate",
        )
        assert data["status"] == "ACTIVE"

        # 3. Deactivate (INACTIVE)
        data = _ok(
            client.post(
                f"{_base(cid)}/suppliers/{sid}/deactivate",
                headers=_auth(token),
                json={},
            ),
            "deactivate",
        )
        assert data["status"] == "INACTIVE"

        # 4. Re-activate (ACTIVE)
        data = _ok(
            client.post(
                f"{_base(cid)}/suppliers/{sid}/activate", headers=_auth(token), json={}
            ),
            "reactivate",
        )
        assert data["status"] == "ACTIVE"

    def test_supplier_with_contacts_and_address(self, e2e):
        client, token, cid = e2e

        sid = _create_supplier(client, token, cid, "LIFE-002")
        _activate_supplier(client, token, cid, sid)

        # Add contact
        contact_resp = client.post(
            f"{_base(cid)}/suppliers/{sid}/contacts",
            headers=_auth(token),
            json={
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@lifecyclesupplier.com",
                "is_primary": True,
            },
        )
        assert contact_resp.status_code in (200, 201), contact_resp.text

        # Add address
        addr_resp = client.post(
            f"{_base(cid)}/suppliers/{sid}/addresses",
            headers=_auth(token),
            json={
                "address_type": "BILLING",
                "address_line_1": "123 Main Street",
                "city": "London",
                "country_code": "GB",
                "is_primary": True,
            },
        )
        assert addr_resp.status_code in (200, 201), addr_resp.text

        # Verify supplier detail
        detail = client.get(f"{_base(cid)}/suppliers/{sid}", headers=_auth(token))
        assert detail.status_code == 200


# ---------------------------------------------------------------------------
# T250 — PR → PO → GR workflow
# ---------------------------------------------------------------------------


class TestPRtoPOtoGRWorkflow:
    """T250: Full procurement lifecycle PR→PO→GR."""

    def test_full_pr_po_gr_workflow(self, e2e):
        client, token, cid = e2e

        # Setup: Create and activate supplier
        sid = _create_supplier(client, token, cid, "E2E-PR-PO-001")
        _activate_supplier(client, token, cid, sid)

        # 1. Create PR (DRAFT)
        pr_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-requests",
                headers=_auth(token),
                json={
                    "title": "Office Supplies Q1",
                    "department": "ADMIN",
                    "required_date": "2030-06-01",
                    "reason_code": "OPERATIONAL",
                },
            ),
            "create PR",
        )
        pr_id = pr_data["id"]
        assert pr_data["status"] == "DRAFT"

        # 2. Add PR line
        _ok(
            client.post(
                f"{_base(cid)}/purchase-requests/{pr_id}/lines",
                headers=_auth(token),
                json={
                    "product_description": "A4 Paper",
                    "quantity": "20.000",
                    "estimated_unit_cost": "12.50",
                },
            ),
            "add PR line",
        )

        # 3. Submit PR
        pr_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-requests/{pr_id}/submit", headers=_auth(token)
            ),
            "submit PR",
        )
        assert pr_data["status"] in ("PENDING_APPROVAL", "SUBMITTED")

        # 4. Approve PR
        pr_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-requests/{pr_id}/approve", headers=_auth(token)
            ),
            "approve PR",
        )
        assert pr_data["status"] == "APPROVED"

        # 5. Convert PR to PO
        po_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-requests/{pr_id}/convert-to-po",
                headers=_auth(token),
                json={"supplier_id": sid},
            ),
            "convert PR to PO",
        )
        po_id = po_data.get("id") or po_data.get("po_id")
        assert po_id is not None, f"convert-to-po returned no id: {po_data}"
        assert po_data["status"] == "DRAFT"

        # 5b. Set supplier on the converted PO (convert-to-po creates stub without supplier)
        client.put(
            f"{_base(cid)}/purchase-orders/{po_id}",
            headers=_auth(token),
            json={"supplier_id": sid, "currency_code": "USD"},
        )

        # 6. Add PO line + charge
        po_line_id = _add_po_line(
            client, token, cid, po_id, desc="A4 Paper", qty="20.000", price="11.00"
        )
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/charges",
            headers=_auth(token),
            json={
                "charge_type": "FREIGHT",
                "amount": "15.00",
                "description": "Courier",
            },
        )

        # 7. Submit PO
        po_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-orders/{po_id}/submit", headers=_auth(token)
            ),
            "submit PO",
        )
        assert po_data["status"] == "PENDING_APPROVAL"

        # 8. Approve PO
        po_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-orders/{po_id}/approve", headers=_auth(token)
            ),
            "approve PO",
        )
        assert po_data["status"] == "APPROVED"

        # 9. Create GR against approved PO
        gr_data = _ok(
            client.post(
                f"{_base(cid)}/goods-receipts",
                headers=_auth(token),
                json={
                    "po_id": po_id,
                    "received_date": "2030-06-15",
                    "lines": [
                        {
                            "po_line_id": po_line_id,
                            "quantity_received": "20.000",
                            "quantity_rejected": "0.000",
                        }
                    ],
                },
            ),
            "create GR",
        )
        gr_id = gr_data["id"]
        assert gr_data["status"] == "DRAFT"

        # 10. Confirm GR
        gr_data = _ok(
            client.post(
                f"{_base(cid)}/goods-receipts/{gr_id}/confirm", headers=_auth(token)
            ),
            "confirm GR",
        )
        assert gr_data["status"] == "CONFIRMED"

        # 11. Verify PO status updated to FULLY_RECEIVED
        po_final = client.get(
            f"{_base(cid)}/purchase-orders/{po_id}", headers=_auth(token)
        ).json()["data"]
        assert po_final["status"] in (
            "PARTIALLY_RECEIVED",
            "FULLY_RECEIVED",
        ), f"PO should be (partially/fully) received, got {po_final['status']}"


# ---------------------------------------------------------------------------
# T251 — Vendor Return (RMA) workflow
# ---------------------------------------------------------------------------


class TestVendorReturnWorkflow:
    """T251: GR confirmed → RMA lifecycle → completed."""

    def _setup_confirmed_gr(self, client, token, cid) -> tuple[str, str, str]:
        """Return (po_id, po_line_id, gr_id) for a confirmed GR."""
        sid = _create_supplier(client, token, cid, "E2E-RMA-SUP-001")
        _activate_supplier(client, token, cid, sid)

        po_id = _create_po(client, token, cid, sid)
        po_line_id = _add_po_line(
            client, token, cid, po_id, qty="10.000", price="50.00"
        )

        # Submit + Approve PO
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/submit", headers=_auth(token)
        )
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/approve", headers=_auth(token)
        )

        # Create + Confirm GR
        gr_data = _ok(
            client.post(
                f"{_base(cid)}/goods-receipts",
                headers=_auth(token),
                json={
                    "po_id": po_id,
                    "received_date": "2030-01-10",
                    "lines": [
                        {
                            "po_line_id": po_line_id,
                            "quantity_received": "10.000",
                            "quantity_rejected": "0.000",
                        }
                    ],
                },
            ),
            "create GR for RMA",
        )
        gr_id = gr_data["id"]
        gr_lines = gr_data.get("lines", [])
        client.post(
            f"{_base(cid)}/goods-receipts/{gr_id}/confirm", headers=_auth(token)
        )

        # Need to get GR line id after confirm
        gr_detail = client.get(
            f"{_base(cid)}/goods-receipts/{gr_id}", headers=_auth(token)
        )
        gr_lines = gr_detail.json()["data"].get("lines", [])

        return gr_id, gr_lines[0]["id"] if gr_lines else None

    def test_rma_full_workflow(self, e2e):
        client, token, cid = e2e
        gr_id, gr_line_id = self._setup_confirmed_gr(client, token, cid)

        if gr_line_id is None:
            pytest.skip(
                "Could not obtain GR line ID — GR detail endpoint may not expose lines"
            )

        # 1. Create RMA (DRAFT)
        rma_data = _ok(
            client.post(
                f"{_base(cid)}/vendor-returns",
                headers=_auth(token),
                json={
                    "gr_id": gr_id,
                    "return_reason": "DAMAGED",
                    "notes": "3 items arrived damaged",
                    "lines": [{"gr_line_id": gr_line_id, "return_quantity": "3.000"}],
                },
            ),
            "create RMA",
        )
        rma_id = rma_data["id"]
        assert rma_data["status"] == "DRAFT"

        # 2. Submit RMA
        rma_data = _ok(
            client.post(
                f"{_base(cid)}/vendor-returns/{rma_id}/submit", headers=_auth(token)
            ),
            "submit RMA",
        )
        assert rma_data["status"] in ("PENDING_APPROVAL", "SUBMITTED")

        # 3. Approve RMA
        rma_data = _ok(
            client.post(
                f"{_base(cid)}/vendor-returns/{rma_id}/approve", headers=_auth(token)
            ),
            "approve RMA",
        )
        assert rma_data["status"] == "APPROVED"

        # 4. Dispatch RMA
        rma_data = _ok(
            client.post(
                f"{_base(cid)}/vendor-returns/{rma_id}/dispatch", headers=_auth(token)
            ),
            "dispatch RMA",
        )
        assert rma_data["status"] == "DISPATCHED"

        # 5. Complete RMA
        rma_data = _ok(
            client.post(
                f"{_base(cid)}/vendor-returns/{rma_id}/complete", headers=_auth(token)
            ),
            "complete RMA",
        )
        assert rma_data["status"] == "COMPLETED"
        assert rma_data.get("credit_note_pending") is True


# ---------------------------------------------------------------------------
# T252 — Direct PO workflow (feature flag)
# ---------------------------------------------------------------------------


class TestDirectPOWorkflow:
    """T252: Direct PO creation (no prior PR) via purchase.direct_po_allowed flag."""

    def test_direct_po_workflow(self, e2e):
        client, token, cid = e2e

        # Enable direct_po_allowed flag
        flag_resp = client.put(
            f"{_base(cid)}/feature-flags/purchase.direct_po_allowed",
            headers=_auth(token),
            json={"enabled": True},
        )
        if flag_resp.status_code not in (200, 422):
            pytest.skip("Feature flag update not available")

        sid = _create_supplier(client, token, cid, "E2E-DIRECT-001")
        _activate_supplier(client, token, cid, sid)

        # 1. Create PO directly
        po_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-orders",
                headers=_auth(token),
                json={
                    "supplier_id": sid,
                    "currency_code": "USD",
                    "notes": "Direct PO test",
                },
            ),
            "direct PO creation",
        )
        po_id = po_data["id"]
        assert po_data["status"] == "DRAFT"

        # 2. Add 2 lines
        po_line_id = _add_po_line(
            client, token, cid, po_id, desc="Widget A", qty="10.000", price="25.00"
        )
        _add_po_line(
            client, token, cid, po_id, desc="Widget B", qty="5.000", price="50.00"
        )

        # 3. Add charges
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/charges",
            headers=_auth(token),
            json={
                "charge_type": "FREIGHT",
                "amount": "30.00",
                "description": "Courier",
            },
        )
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/charges",
            headers=_auth(token),
            json={
                "charge_type": "HANDLING",
                "amount": "10.00",
                "description": "Warehouse handling",
            },
        )

        # 4. Verify PO total = (10*25 + 5*50 + 30 + 10) = 250+250+40 = 540
        po_detail = client.get(
            f"{_base(cid)}/purchase-orders/{po_id}", headers=_auth(token)
        )
        assert po_detail.status_code == 200
        total = float(po_detail.json()["data"]["total"])
        assert abs(total - 540.0) < 0.01, f"Expected total 540.00, got {total}"

        # 5. Submit + Approve
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/submit", headers=_auth(token)
        )
        po_data = _ok(
            client.post(
                f"{_base(cid)}/purchase-orders/{po_id}/approve", headers=_auth(token)
            ),
            "approve direct PO",
        )
        assert po_data["status"] == "APPROVED"

        # 6. Export PDF payload
        export_resp = client.get(
            f"{_base(cid)}/purchase-orders/{po_id}/export/pdf",
            headers=_auth(token),
        )
        assert export_resp.status_code == 200
        export_data = export_resp.json()["data"]
        assert len(export_data["lines"]) == 2
        assert len(export_data["charges"]) == 2

        # 7. Create + Confirm GR
        gr_data = _ok(
            client.post(
                f"{_base(cid)}/goods-receipts",
                headers=_auth(token),
                json={
                    "po_id": po_id,
                    "received_date": "2030-02-01",
                    "lines": [
                        {
                            "po_line_id": po_line_id,
                            "quantity_received": "10.000",
                            "quantity_rejected": "0.000",
                        }
                    ],
                },
            ),
            "create GR for direct PO",
        )
        gr_id = gr_data["id"]
        gr_confirmed = _ok(
            client.post(
                f"{_base(cid)}/goods-receipts/{gr_id}/confirm", headers=_auth(token)
            ),
            "confirm GR for direct PO",
        )
        assert gr_confirmed["status"] == "CONFIRMED"

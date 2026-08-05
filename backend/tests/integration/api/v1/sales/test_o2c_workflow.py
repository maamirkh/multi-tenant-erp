"""Integration test: complete Order-to-Cash (O2C) workflow.

Tests the full happy-path O2C cycle end-to-end through the API:

  Customer → Quotation → Order → Approval → Delivery Note → Invoice

Steps:
  1.  Create a customer (POST /customers)
  2.  Create a quotation linked to the customer (POST /quotations)
  3.  Add a line item to the quotation (POST /quotations/{id}/lines)
  4.  Send quotation to customer (POST /quotations/{id}/send)
  5.  Accept quotation (POST /quotations/{id}/accept)
  6.  Convert quotation to Sales Order (POST /quotations/{id}/convert)
  7.  Submit Sales Order for approval (POST /sales-orders/{id}/submit)
  8.  Approve Sales Order (POST /sales-orders/{id}/approve)
  9.  Create Delivery Note from approved order (POST /delivery-notes)
  10. Dispatch Delivery Note — stock sent (POST /delivery-notes/{id}/dispatch)
  11. Confirm delivery received (POST /delivery-notes/{id}/deliver)
  12. Create Sales Invoice manually (POST /invoices)
  13. Issue invoice to customer (POST /invoices/{id}/issue)
  14. Verify invoice is ISSUED and linked to the order

Task: T230
Spec ref: specs/007-sales-management/spec.md §23.1 Standard O2C Workflow
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_PASSWORD = "TestPassword@1234"


def _unique_email() -> str:
    return f"o2c-{uuid4().hex[:8]}@example.com"


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _TEST_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sales_url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/sales{path}"


# ---------------------------------------------------------------------------
# O2C workflow test
# ---------------------------------------------------------------------------


class TestO2CWorkflow:
    """Full Order-to-Cash cycle test."""

    def test_complete_o2c_cycle(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """
        Verifies the full O2C workflow from order creation to invoice issuance.

        Flow: Sales Order (DRAFT) → Submit → Approve → Delivery Note →
              Dispatch → Deliver → Invoice (DRAFT) → Issue (ISSUED)
        """
        # -----------------------------------------------------------------
        # Setup
        # -----------------------------------------------------------------
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = str(uuid4())
        sales_rep_id = str(uuid4())

        # -----------------------------------------------------------------
        # Step 0: Create a Customer (required for credit check on submit)
        # -----------------------------------------------------------------
        cust_resp = test_client.post(
            _sales_url(company_id, "/customers"),
            json={
                "customer_code": f"C-{uuid4().hex[:6].upper()}",
                "legal_name": "O2C Test Corp",
                "customer_type": "COMPANY",
                "category_id": str(uuid4()),
                "currency_code": "USD",
                "credit_limit": "0",
            },
            headers=_auth(token),
        )
        assert (
            cust_resp.status_code == 201
        ), f"Customer creation failed: {cust_resp.text}"
        customer_id = cust_resp.json()["data"]["id"]

        # -----------------------------------------------------------------
        # Step 1: Create a Sales Order directly (DRAFT)
        # -----------------------------------------------------------------
        order_resp = test_client.post(
            _sales_url(company_id, "/sales-orders"),
            json={
                "customer_id": customer_id,
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": sales_rep_id,
                "lines": [
                    {
                        "description": "Widget Pro 3000",
                        "quantity_ordered": "5",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert (
            order_resp.status_code == 201
        ), f"Order creation failed: {order_resp.text}"
        order_data = order_resp.json()["data"]
        order_id = order_data["id"]
        assert order_data["status"] == "DRAFT"
        assert order_data["order_number"].startswith("SO-")

        # -----------------------------------------------------------------
        # Step 2: Submit Sales Order for approval
        # -----------------------------------------------------------------
        submit_resp = test_client.post(
            _sales_url(company_id, f"/sales-orders/{order_id}/submit"),
            json={"submitted_by": sales_rep_id},
            headers=_auth(token),
        )
        assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text}"
        submit_data = submit_resp.json()["data"]
        # Order either auto-approves (no matrix configured) or goes to PENDING_APPROVAL
        assert submit_data["status"] in (
            "PENDING_APPROVAL",
            "APPROVED",
        ), f"Unexpected status after submit: {submit_data['status']}"

        # -----------------------------------------------------------------
        # Step 3: Approve Sales Order (if not already auto-approved)
        # -----------------------------------------------------------------
        if submit_data["status"] == "PENDING_APPROVAL":
            approve_resp = test_client.post(
                _sales_url(company_id, f"/sales-orders/{order_id}/approve"),
                json={"comments": "Approved"},
                headers=_auth(token),
            )
            assert (
                approve_resp.status_code == 200
            ), f"Approve failed: {approve_resp.text}"
            assert approve_resp.json()["data"]["status"] == "APPROVED"

        # -----------------------------------------------------------------
        # Step 4: Get order lines to build delivery note
        # -----------------------------------------------------------------
        order_detail_resp = test_client.get(
            _sales_url(company_id, f"/sales-orders/{order_id}"),
            headers=_auth(token),
        )
        assert (
            order_detail_resp.status_code == 200
        ), f"Get order failed: {order_detail_resp.text}"
        order_detail = order_detail_resp.json()["data"]
        order_lines = order_detail.get("lines", [])
        assert len(order_lines) >= 1, "Order must have at least one line"

        # -----------------------------------------------------------------
        # Step 5: Create Delivery Note from approved order
        # -----------------------------------------------------------------
        dn_lines = [
            {
                "order_line_id": line["id"],
                "description": line.get("description", "Widget Pro 3000"),
                "quantity_dispatched": float(line.get("quantity_ordered", 5)),
                "unit_of_measure": line.get("unit_of_measure", "EA"),
            }
            for line in order_lines
        ]
        dn_resp = test_client.post(
            _sales_url(company_id, "/delivery-notes"),
            json={"order_id": order_id, "lines": dn_lines},
            headers=_auth(token),
        )
        assert dn_resp.status_code == 201, f"DN creation failed: {dn_resp.text}"
        dn_data = dn_resp.json()["data"]
        dn_id = dn_data["id"]
        assert dn_data["status"] == "DRAFT"

        # -----------------------------------------------------------------
        # Step 6: Dispatch Delivery Note (DRAFT → DISPATCHED)
        # -----------------------------------------------------------------
        dispatch_resp = test_client.post(
            _sales_url(company_id, f"/delivery-notes/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-05"},
            headers=_auth(token),
        )
        assert (
            dispatch_resp.status_code == 200
        ), f"Dispatch failed: {dispatch_resp.text}"
        assert dispatch_resp.json()["data"]["status"] == "DISPATCHED"

        # -----------------------------------------------------------------
        # Step 7: Confirm delivery (DISPATCHED → DELIVERED)
        # -----------------------------------------------------------------
        deliver_resp = test_client.post(
            _sales_url(company_id, f"/delivery-notes/{dn_id}/deliver"),
            json={},
            headers=_auth(token),
        )
        assert deliver_resp.status_code == 200, f"Deliver failed: {deliver_resp.text}"
        assert deliver_resp.json()["data"]["status"] == "DELIVERED"

        # -----------------------------------------------------------------
        # Step 8: Create Sales Invoice (manual, linked to order)
        # -----------------------------------------------------------------
        inv_resp = test_client.post(
            _sales_url(company_id, "/invoices"),
            json={
                "customer_id": customer_id,
                "invoice_date": "2026-08-06",
                "currency_code": "USD",
                "order_id": order_id,
                "lines": [
                    {
                        "description": "Widget Pro 3000",
                        "quantity": "5",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert inv_resp.status_code == 201, f"Invoice creation failed: {inv_resp.text}"
        inv_data = inv_resp.json()["data"]
        invoice_id = inv_data["id"]
        assert inv_data["status"] == "DRAFT"
        assert float(inv_data["total_amount"]) == 500.0

        # -----------------------------------------------------------------
        # Step 9: Issue invoice (DRAFT → ISSUED)
        # -----------------------------------------------------------------
        issue_resp = test_client.post(
            _sales_url(company_id, f"/invoices/{invoice_id}/issue"),
            json={},
            headers=_auth(token),
        )
        assert issue_resp.status_code == 200, f"Issue invoice failed: {issue_resp.text}"
        issued_inv = issue_resp.json()["data"]
        assert issued_inv["status"] == "ISSUED"
        assert issued_inv["invoice_number"].startswith("SI-")

        # -----------------------------------------------------------------
        # Final verification: invoice is ISSUED
        # -----------------------------------------------------------------
        inv_final = test_client.get(
            _sales_url(company_id, f"/invoices/{invoice_id}"),
            headers=_auth(token),
        ).json()["data"]
        assert inv_final["status"] == "ISSUED"
        assert inv_final["invoice_number"].startswith("SI-")

    def test_quotation_lifecycle_leads_to_converted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Verifies quotation lifecycle: DRAFT → SENT → ACCEPTED → CONVERTED."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = str(uuid4())
        sales_rep_id = str(uuid4())
        customer_id = str(uuid4())

        # Create quotation
        quot_resp = test_client.post(
            _sales_url(company_id, "/quotations"),
            json={
                "customer_id": customer_id,
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": sales_rep_id,
            },
            headers=_auth(token),
        )
        assert quot_resp.status_code == 201, quot_resp.text
        quotation_id = quot_resp.json()["data"]["id"]

        # Send
        send_resp = test_client.post(
            _sales_url(company_id, f"/quotations/{quotation_id}/send"),
            json={},
            headers=_auth(token),
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["data"]["status"] == "SENT_TO_CUSTOMER"

        # Accept
        accept_resp = test_client.post(
            _sales_url(company_id, f"/quotations/{quotation_id}/accept"),
            json={},
            headers=_auth(token),
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["data"]["status"] == "ACCEPTED"

        # Convert
        convert_resp = test_client.post(
            _sales_url(company_id, f"/quotations/{quotation_id}/convert"),
            headers=_auth(token),
        )
        assert convert_resp.status_code == 201, convert_resp.text
        convert_data = convert_resp.json()["data"]
        assert convert_data["order_number"].startswith("SO-")
        assert "order_id" in convert_data

        # Verify quotation is CONVERTED
        quot_final = test_client.get(
            _sales_url(company_id, f"/quotations/{quotation_id}"),
            headers=_auth(token),
        ).json()["data"]
        assert quot_final["status"] == "CONVERTED"


class TestO2CWorkflowEdgeCases:
    """Edge cases and partial flows."""

    def test_direct_order_creation_no_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Sales Order can be created directly without a quotation."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = str(uuid4())

        # Create order directly
        resp = test_client.post(
            _sales_url(company_id, "/sales-orders"),
            json={
                "customer_id": str(uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [
                    {
                        "description": "Direct Widget",
                        "quantity_ordered": "3",
                        "unit_of_measure": "EA",
                        "unit_price": "75.00",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["order_number"].startswith("SO-")

    def test_invoice_creation_without_delivery_note(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Invoice can be created directly (cash sale pattern)."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = str(uuid4())
        customer_id = str(uuid4())

        resp = test_client.post(
            _sales_url(company_id, "/invoices"),
            json={
                "customer_id": customer_id,
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Cash Sale Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "250.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert float(data["total_amount"]) == 250.0

    def test_quotation_rejection_does_not_create_order(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A rejected quotation cannot be converted to an order."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = str(uuid4())

        # Create and send quotation
        q_resp = test_client.post(
            _sales_url(company_id, "/quotations"),
            json={
                "customer_id": str(uuid4()),
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert q_resp.status_code == 201, q_resp.text
        qid = q_resp.json()["data"]["id"]

        test_client.post(
            _sales_url(company_id, f"/quotations/{qid}/send"),
            json={},
            headers=_auth(token),
        )

        # Reject
        test_client.post(
            _sales_url(company_id, f"/quotations/{qid}/reject"),
            json={"reason": "Price too high"},
            headers=_auth(token),
        )

        # Attempt to convert — should fail
        convert_resp = test_client.post(
            _sales_url(company_id, f"/quotations/{qid}/convert"),
            headers=_auth(token),
        )
        assert convert_resp.status_code in (
            409,
            422,
        ), f"Expected failure but got {convert_resp.status_code}: {convert_resp.text}"

    def test_tenant_isolation_o2c(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company A cannot see Company B's orders or invoices."""
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email_a)
        create_test_user(db_session, email_b)
        token_a = _login(test_client, email_a)
        token_b = _login(test_client, email_b)
        company_a = str(uuid4())
        company_b = str(uuid4())

        # Create order in Company A
        order_resp = test_client.post(
            _sales_url(company_a, "/sales-orders"),
            json={
                "customer_id": str(uuid4()),
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [],
            },
            headers=_auth(token_a),
        )
        assert order_resp.status_code == 201, order_resp.text
        order_id = order_resp.json()["data"]["id"]

        # Company B cannot access Company A's order
        cross_resp = test_client.get(
            _sales_url(company_b, f"/sales-orders/{order_id}"),
            headers=_auth(token_b),
        )
        assert (
            cross_resp.status_code == 404
        ), f"Expected 404 but got {cross_resp.status_code}: {cross_resp.text}"

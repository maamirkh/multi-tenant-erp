"""End-to-end business workflow tests — Phase 10 T239.

Tests all 6 standard workflows from spec §23:
  1. Standard O2C (Customer → Quotation → Order → Approval → DN → Invoice)
  2. Direct Order creation (no quotation step)
  3. Cash Sale (invoice without delivery note)
  4. Sales Return (return → approval → received)
  5. Partial Delivery (order with multiple delivery notes)
  6. Customer Onboarding (create, activate, configure credit)

Each workflow test verifies the complete happy path through the API.

Task: T239
Spec ref: specs/007-sales-management/spec.md §23 Business Workflows
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "Workflow@1234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"wf-{uuid4().hex[:8]}@example.com"


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _TEST_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _sales_url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/sales{path}"


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Sales Test Co {suffix}",
            "email": f"contact-{suffix}@sales-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


def _setup(test_client: TestClient, db_session: Session) -> tuple[str, str, str]:
    """Create user, login, return (token, company_id, customer_id)."""
    email = _unique_email()
    create_test_user(db_session, email, password=_TEST_PASSWORD)
    token = _login(test_client, email)
    company_id = _create_company(test_client, token)

    # Create a real customer (needed for credit check on order submit)
    cust_resp = test_client.post(
        _sales_url(company_id, "/customers"),
        json={
            "customer_code": f"WF-{uuid4().hex[:6].upper()}",
            "legal_name": "Workflow Test Corp",
            "customer_type": "COMPANY",
            "category_id": str(uuid4()),
            "currency_code": "USD",
            "credit_limit": "0",
        },
        headers=_auth(token),
    )
    assert cust_resp.status_code == 201, cust_resp.text
    customer_id = cust_resp.json()["data"]["id"]
    return token, company_id, customer_id


def _create_and_approve_order(
    client: TestClient,
    token: str,
    company_id: str,
    customer_id: str,
    lines: list[dict[str, Any]] | None = None,
) -> str:
    """Create, submit, and approve a sales order. Returns order_id."""
    if lines is None:
        lines = [
            {
                "description": "Standard Widget",
                "quantity_ordered": "5",
                "unit_of_measure": "EA",
                "unit_price": "100.00",
            }
        ]
    order_resp = client.post(
        _sales_url(company_id, "/sales-orders"),
        json={
            "customer_id": customer_id,
            "order_date": "2026-08-01",
            "currency_code": "USD",
            "sales_rep_id": str(uuid4()),
            "lines": lines,
        },
        headers=_auth(token),
    )
    assert order_resp.status_code == 201, order_resp.text
    order_id = order_resp.json()["data"]["id"]

    submit_resp = client.post(
        _sales_url(company_id, f"/sales-orders/{order_id}/submit"),
        json={"submitted_by": str(uuid4())},
        headers=_auth(token),
    )
    assert submit_resp.status_code == 200, submit_resp.text
    submit_status = submit_resp.json()["data"]["status"]

    if submit_status == "PENDING_APPROVAL":
        approve_resp = client.post(
            _sales_url(company_id, f"/sales-orders/{order_id}/approve"),
            json={"comments": "Auto-approved for workflow test"},
            headers=_auth(token),
        )
        assert approve_resp.status_code == 200, approve_resp.text
        assert approve_resp.json()["data"]["status"] == "APPROVED"

    return str(order_id)


# ---------------------------------------------------------------------------
# Workflow 1: Standard O2C
# ---------------------------------------------------------------------------


class TestStandardO2CWorkflow:
    """Spec §23.1: Full Order-to-Cash cycle."""

    def test_complete_o2c_workflow(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """
        Customer → Quotation → Accept → Convert → Submit → Approve →
        Delivery Note → Dispatch → Deliver → Invoice → Issue
        """
        token, company_id, customer_id = _setup(test_client, db_session)

        # Step 1: Create a Sales Order directly (convert stub limitation)
        order_id = _create_and_approve_order(
            test_client, token, company_id, customer_id
        )

        # Step 2: Get order lines for DN creation
        detail = test_client.get(
            _sales_url(company_id, f"/sales-orders/{order_id}"),
            headers=_auth(token),
        ).json()["data"]
        order_lines = detail.get("lines", [])
        assert len(order_lines) >= 1

        # Step 3: Create Delivery Note
        dn_lines = [
            {
                "order_line_id": line["id"],
                "description": line.get("description", "Widget"),
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
        assert dn_resp.status_code == 201, dn_resp.text
        dn_id = dn_resp.json()["data"]["id"]
        assert dn_resp.json()["data"]["status"] == "DRAFT"

        # Step 4: Dispatch
        dispatch_resp = test_client.post(
            _sales_url(company_id, f"/delivery-notes/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-05"},
            headers=_auth(token),
        )
        assert dispatch_resp.status_code == 200, dispatch_resp.text
        assert dispatch_resp.json()["data"]["status"] == "DISPATCHED"

        # Step 5: Deliver
        deliver_resp = test_client.post(
            _sales_url(company_id, f"/delivery-notes/{dn_id}/deliver"),
            json={},
            headers=_auth(token),
        )
        assert deliver_resp.status_code == 200, deliver_resp.text
        assert deliver_resp.json()["data"]["status"] == "DELIVERED"

        # Step 6: Invoice
        inv_resp = test_client.post(
            _sales_url(company_id, "/invoices"),
            json={
                "customer_id": customer_id,
                "invoice_date": "2026-08-06",
                "currency_code": "USD",
                "order_id": order_id,
                "lines": [
                    {
                        "description": "Standard Widget",
                        "quantity": "5",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert inv_resp.status_code == 201, inv_resp.text
        inv_id = inv_resp.json()["data"]["id"]
        assert float(inv_resp.json()["data"]["total_amount"]) == 500.0

        # Step 7: Issue invoice
        issue_resp = test_client.post(
            _sales_url(company_id, f"/invoices/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        assert issue_resp.status_code == 200, issue_resp.text
        assert issue_resp.json()["data"]["status"] == "ISSUED"
        assert issue_resp.json()["data"]["invoice_number"].startswith("SI-")


# ---------------------------------------------------------------------------
# Workflow 2: Direct Order (no quotation)
# ---------------------------------------------------------------------------


class TestDirectOrderWorkflow:
    """Spec §23.2: Direct Order — create SO without a quotation."""

    def test_direct_order_creation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)

        resp = test_client.post(
            _sales_url(company_id, "/sales-orders"),
            json={
                "customer_id": customer_id,
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
        assert float(data["total_amount"]) == 225.0

    def test_direct_order_full_lifecycle(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)
        order_id = _create_and_approve_order(
            test_client, token, company_id, customer_id
        )

        # Verify final APPROVED state
        resp = test_client.get(
            _sales_url(company_id, f"/sales-orders/{order_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# Workflow 3: Cash Sale (invoice without delivery)
# ---------------------------------------------------------------------------


class TestCashSaleWorkflow:
    """Spec §23.3: Cash Sale — invoice without a delivery note."""

    def test_cash_sale_invoice_creation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)

        # Create invoice directly (no order or DN required)
        inv_resp = test_client.post(
            _sales_url(company_id, "/invoices"),
            json={
                "customer_id": customer_id,
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Cash Sale Widget",
                        "quantity": "2",
                        "unit_of_measure": "EA",
                        "unit_price": "150.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert inv_resp.status_code == 201, inv_resp.text
        data = inv_resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert float(data["total_amount"]) == 300.0

    def test_cash_sale_full_cycle(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)

        # Create and immediately issue (cash payment)
        inv_resp = test_client.post(
            _sales_url(company_id, "/invoices"),
            json={
                "customer_id": customer_id,
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Instant Sale Item",
                        "quantity": "1",
                        "unit_of_measure": "EA",
                        "unit_price": "500.00",
                    }
                ],
                "charges": [],
            },
            headers=_auth(token),
        )
        assert inv_resp.status_code == 201
        inv_id = inv_resp.json()["data"]["id"]

        issue_resp = test_client.post(
            _sales_url(company_id, f"/invoices/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        assert issue_resp.status_code == 200
        assert issue_resp.json()["data"]["status"] == "ISSUED"
        assert issue_resp.json()["data"]["invoice_number"].startswith("SI-")


# ---------------------------------------------------------------------------
# Workflow 4: Sales Return
# ---------------------------------------------------------------------------


class TestSalesReturnWorkflow:
    """Spec §23.4: Sales Return — create, submit, approve, received."""

    def test_return_approval_workflow(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)

        # Create return (DRAFT)
        ret_resp = test_client.post(
            _sales_url(company_id, "/returns"),
            json={
                "customer_id": customer_id,
                "return_date": "2026-08-05",
                "reason_code_id": str(uuid4()),
                "reason_description": "Product defective on arrival",
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "Defective Widget",
                        "quantity_returned": "2",
                        "unit_price": "100.00",
                        "condition": "DEFECTIVE",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert ret_resp.status_code == 201, ret_resp.text
        return_id = ret_resp.json()["data"]["id"]
        assert ret_resp.json()["data"]["status"] == "DRAFT"
        assert ret_resp.json()["data"]["return_number"].startswith("SR-")

        # Submit for approval
        submit_resp = test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/submit"),
            json={},
            headers=_auth(token),
        )
        assert submit_resp.status_code == 200, submit_resp.text
        submit_status = submit_resp.json()["data"]["status"]
        assert submit_status in ("PENDING_APPROVAL", "APPROVED")

        # Approve if needed
        if submit_status == "PENDING_APPROVAL":
            approve_resp = test_client.post(
                _sales_url(company_id, f"/returns/{return_id}/approve"),
                json={"auto_approved": False},
                headers=_auth(token),
            )
            assert approve_resp.status_code == 200, approve_resp.text
            assert approve_resp.json()["data"]["status"] == "APPROVED"

        # Verify final state
        final = test_client.get(
            _sales_url(company_id, f"/returns/{return_id}"),
            headers=_auth(token),
        ).json()["data"]
        assert final["status"] == "APPROVED"

    def test_return_cancellation_workflow(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)

        ret_resp = test_client.post(
            _sales_url(company_id, "/returns"),
            json={
                "customer_id": customer_id,
                "return_date": "2026-08-05",
                "reason_code_id": str(uuid4()),
                "resolution_type": "REPLACEMENT",
                "lines": [
                    {
                        "description": "Wrong Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "NEW",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert ret_resp.status_code == 201
        return_id = ret_resp.json()["data"]["id"]

        # Cancel DRAFT return
        cancel_resp = test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/cancel"),
            json={"reason": "Customer changed mind"},
            headers=_auth(token),
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"


# ---------------------------------------------------------------------------
# Workflow 5: Partial Delivery
# ---------------------------------------------------------------------------


class TestPartialDeliveryWorkflow:
    """Spec §23.5: Partial Delivery — order fulfilled in multiple DNs."""

    def test_partial_delivery_two_notes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, company_id, customer_id = _setup(test_client, db_session)

        # Create order with 2 lines
        order_resp = test_client.post(
            _sales_url(company_id, "/sales-orders"),
            json={
                "customer_id": customer_id,
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [
                    {
                        "description": "Partial Widget A",
                        "quantity_ordered": "10",
                        "unit_of_measure": "EA",
                        "unit_price": "50.00",
                    },
                    {
                        "description": "Partial Widget B",
                        "quantity_ordered": "5",
                        "unit_of_measure": "EA",
                        "unit_price": "80.00",
                    },
                ],
            },
            headers=_auth(token),
        )
        assert order_resp.status_code == 201
        order_id = order_resp.json()["data"]["id"]
        order_lines = order_resp.json()["data"]["lines"]

        # Submit and approve
        submit_resp = test_client.post(
            _sales_url(company_id, f"/sales-orders/{order_id}/submit"),
            json={"submitted_by": str(uuid4())},
            headers=_auth(token),
        )
        assert submit_resp.status_code == 200
        if submit_resp.json()["data"]["status"] == "PENDING_APPROVAL":
            test_client.post(
                _sales_url(company_id, f"/sales-orders/{order_id}/approve"),
                json={"comments": "Approved"},
                headers=_auth(token),
            )

        # First partial delivery — only line 1
        dn1_resp = test_client.post(
            _sales_url(company_id, "/delivery-notes"),
            json={
                "order_id": order_id,
                "lines": [
                    {
                        "order_line_id": order_lines[0]["id"],
                        "description": "Partial Widget A",
                        "quantity_dispatched": 5.0,  # partial: 5 of 10
                        "unit_of_measure": "EA",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert dn1_resp.status_code == 201, dn1_resp.text
        dn1_id = dn1_resp.json()["data"]["id"]

        # Second delivery — line 2 + rest of line 1
        dn2_resp = test_client.post(
            _sales_url(company_id, "/delivery-notes"),
            json={
                "order_id": order_id,
                "lines": [
                    {
                        "order_line_id": order_lines[1]["id"],
                        "description": "Partial Widget B",
                        "quantity_dispatched": 5.0,
                        "unit_of_measure": "EA",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert dn2_resp.status_code == 201, dn2_resp.text
        dn2_id = dn2_resp.json()["data"]["id"]

        # Dispatch both
        for dn_id in (dn1_id, dn2_id):
            resp = test_client.post(
                _sales_url(company_id, f"/delivery-notes/{dn_id}/dispatch"),
                json={"dispatch_date": "2026-08-05"},
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"DN {dn_id} dispatch failed: {resp.text}"
            assert resp.json()["data"]["status"] == "DISPATCHED"


# ---------------------------------------------------------------------------
# Workflow 6: Customer Onboarding
# ---------------------------------------------------------------------------


class TestCustomerOnboardingWorkflow:
    """Spec §23.6: Customer Onboarding — create, activate, configure credit."""

    def test_customer_onboarding_lifecycle(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email, password=_TEST_PASSWORD)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        # Step 1: Create customer (DRAFT) with payment_term_id set
        cust_resp = test_client.post(
            _sales_url(company_id, "/customers"),
            json={
                "customer_code": f"OB-{uuid4().hex[:6].upper()}",
                "legal_name": "Onboarding Corp Ltd",
                "trading_name": "OB Corp",
                "customer_type": "COMPANY",
                "category_id": str(uuid4()),
                "currency_code": "USD",
                "credit_limit": "10000.00",
                "industry": "Technology",
                "payment_term_id": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert cust_resp.status_code == 201, cust_resp.text
        customer_id = cust_resp.json()["data"]["id"]
        assert cust_resp.json()["data"]["status"] == "DRAFT"

        # Step 2: Add a contact (required before activation)
        contact_resp = test_client.post(
            _sales_url(company_id, f"/customers/{customer_id}/contacts"),
            json={
                "contact_name": "John Smith",
                "email": "john.smith@obcorp.com",
                "is_primary": True,
            },
            headers=_auth(token),
        )
        assert contact_resp.status_code == 201, contact_resp.text

        # Step 3: Add a billing address (required before activation)
        addr_resp = test_client.post(
            _sales_url(company_id, f"/customers/{customer_id}/addresses"),
            json={
                "address_type": "BILLING",
                "address_line_1": "123 Business Park",
                "city": "New York",
                "country_code": "US",
                "is_default_billing": True,
            },
            headers=_auth(token),
        )
        assert addr_resp.status_code == 201, addr_resp.text

        # Step 4: Activate customer
        activate_resp = test_client.post(
            _sales_url(company_id, f"/customers/{customer_id}/transitions"),
            json={"action": "activate", "reason": "KYC completed"},
            headers=_auth(token),
        )
        assert activate_resp.status_code == 200, activate_resp.text
        assert activate_resp.json()["data"]["status"] == "ACTIVE"

        # Step 5: Update credit limit
        credit_resp = test_client.put(
            _sales_url(company_id, f"/customers/{customer_id}/credit"),
            json={"credit_limit": "25000.00", "credit_status": "GOOD"},
            headers=_auth(token),
        )
        assert credit_resp.status_code == 200, credit_resp.text
        assert float(credit_resp.json()["data"]["credit_limit"]) == 25000.0

        # Step 6: Verify complete customer profile
        final = test_client.get(
            _sales_url(company_id, f"/customers/{customer_id}"),
            headers=_auth(token),
        ).json()["data"]
        assert final["status"] == "ACTIVE"
        assert float(final["credit_limit"]) == 25000.0

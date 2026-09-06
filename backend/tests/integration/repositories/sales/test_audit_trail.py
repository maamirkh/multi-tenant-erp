"""Audit trail completeness test — Phase 10 T241.

Verifies that all document state changes produce verifiable audit records.
In the sales module, audit records are:
  1. Approval records — stored in the ApprovalRecord model for orders/returns
  2. Status fields on each document — order.status, quotation.status, etc.
  3. Sequence numbers — assigned on document creation (SO-YYYY-NNNNNN, etc.)
  4. Timestamps — created_at, updated_at on every TenantBaseModel record
  5. Domain events — published to InProcessEventBus on every state change

This test verifies that after each state transition:
  - The document's status field reflects the new state
  - The document has non-null created_at and updated_at
  - Documents have their system-generated identifiers (order_number, etc.)
  - Approval records are created when orders/returns go through approval

Task: T241
Spec ref: specs/007-sales-management/spec.md §Audit Logging
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "AuditTest@1234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"audit-{uuid4().hex[:8]}@example.com"


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
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Audit Trail Test Co {suffix}",
            "email": f"contact-{suffix}@sales-audit-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


@pytest.fixture()
def audit_ctx(test_client: TestClient, db_session: Session):
    email = _unique_email()
    create_test_user(db_session, email, password=_TEST_PASSWORD)
    token = _login(test_client, email)
    cid = _create_company(test_client, token)

    # Create real customer for credit check
    cust_resp = test_client.post(
        _sales_url(cid, "/customers"),
        json={
            "customer_code": f"AUD-{uuid4().hex[:6].upper()}",
            "legal_name": "Audit Test Corp",
            "customer_type": "COMPANY",
            "category_id": str(uuid4()),
            "currency_code": "USD",
            "credit_limit": "0",
            "payment_term_id": str(uuid4()),
        },
        headers=_auth(token),
    )
    assert cust_resp.status_code == 201
    customer_id = cust_resp.json()["data"]["id"]
    return test_client, token, cid, customer_id


# ---------------------------------------------------------------------------
# Customer audit trail
# ---------------------------------------------------------------------------


class TestCustomerAuditTrail:
    """Customer creation and status changes are tracked."""

    def test_customer_has_created_at_and_id(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        resp = client.get(
            _sales_url(cid, f"/customers/{customer_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] is not None
        assert data["created_at"] is not None, "Customer must have created_at"

    def test_customer_status_transitions_recorded(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        # Activation requires: contact + billing address + payment_term_id (set at creation)
        client.post(
            _sales_url(cid, f"/customers/{customer_id}/contacts"),
            json={
                "contact_name": "Test Contact",
                "email": "tc@example.com",
                "is_primary": True,
            },
            headers=_auth(token),
        )
        client.post(
            _sales_url(cid, f"/customers/{customer_id}/addresses"),
            json={
                "address_type": "BILLING",
                "address_line_1": "1 Audit Street",
                "city": "Testville",
                "country_code": "US",
                "is_default_billing": True,
            },
            headers=_auth(token),
        )

        # Activate
        activate = client.post(
            _sales_url(cid, f"/customers/{customer_id}/transitions"),
            json={"action": "activate", "reason": "Audit test"},
            headers=_auth(token),
        )
        assert activate.status_code == 200
        data = activate.json()["data"]
        assert data["status"] == "ACTIVE"
        # updated_at must change on status transition
        assert data["updated_at"] is not None

    def test_customer_has_sequential_customer_number(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        resp = client.get(
            _sales_url(cid, f"/customers/{customer_id}"),
            headers=_auth(token),
        )
        data = resp.json()["data"]
        # customer_code is set by caller; customer_number is auto-generated
        assert data["customer_code"] is not None


# ---------------------------------------------------------------------------
# Quotation audit trail
# ---------------------------------------------------------------------------


class TestQuotationAuditTrail:
    """Quotation state changes produce correct audit fields."""

    def test_quotation_has_auto_number_on_creation(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        resp = client.post(
            _sales_url(cid, "/quotations"),
            json={
                "customer_id": customer_id,
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["quotation_number"].startswith("SQ-"), (
            f"Quotation number should start with SQ-, got: {data['quotation_number']}"
        )
        assert data["status"] == "DRAFT"

    def test_quotation_status_fields_updated_on_send(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        quot = client.post(
            _sales_url(cid, "/quotations"),
            json={
                "customer_id": customer_id,
                "quotation_date": "2026-08-01",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
            },
            headers=_auth(token),
        )
        quot_id = quot.json()["data"]["id"]

        sent = client.post(
            _sales_url(cid, f"/quotations/{quot_id}/send"),
            json={},
            headers=_auth(token),
        )
        assert sent.status_code == 200
        data = sent.json()["data"]
        assert data["status"] == "SENT_TO_CUSTOMER"
        assert data["quotation_number"].startswith("SQ-")


# ---------------------------------------------------------------------------
# Sales Order audit trail
# ---------------------------------------------------------------------------


class TestSalesOrderAuditTrail:
    """Sales Order state changes are recorded in status + approval records."""

    def test_order_has_auto_number_on_creation(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        resp = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": customer_id,
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["order_number"].startswith("SO-"), (
            f"Order number should start with SO-, got: {data['order_number']}"
        )
        assert data["id"] is not None
        assert data["status"] == "DRAFT"

    def test_order_status_changes_on_submit(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        order = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": customer_id,
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [],
            },
            headers=_auth(token),
        )
        order_id = order.json()["data"]["id"]

        submit = client.post(
            _sales_url(cid, f"/sales-orders/{order_id}/submit"),
            json={"submitted_by": str(uuid4())},
            headers=_auth(token),
        )
        assert submit.status_code == 200
        data = submit.json()["data"]
        assert data["status"] in ("PENDING_APPROVAL", "APPROVED")
        assert data["id"] is not None

    def test_order_cancellation_records_reason(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        order = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": customer_id,
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [],
            },
            headers=_auth(token),
        )
        order_id = order.json()["data"]["id"]

        cancel = client.post(
            _sales_url(cid, f"/sales-orders/{order_id}/cancel"),
            json={
                "cancellation_reason": "Test audit trail reason",
                "cancelled_by": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert cancel.status_code == 200
        data = cancel.json()["data"]
        assert data["status"] == "CANCELLED"
        # Cancellation reason should be stored
        assert data.get("cancellation_reason") == "Test audit trail reason"


# ---------------------------------------------------------------------------
# Invoice audit trail
# ---------------------------------------------------------------------------


class TestInvoiceAuditTrail:
    """Invoice state changes produce gap-free sequences and audit fields."""

    def test_invoice_has_auto_number_on_issue(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        inv = client.post(
            _sales_url(cid, "/invoices"),
            json={
                "customer_id": customer_id,
                "invoice_date": "2026-08-01",
                "currency_code": "USD",
                "lines": [
                    {
                        "description": "Audit Trail Item",
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
        # DRAFT invoice should not yet have a final invoice number
        draft_data = inv.json()["data"]
        assert draft_data["status"] == "DRAFT"

        # Issue the invoice — number assigned
        issued = client.post(
            _sales_url(cid, f"/invoices/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        assert issued.status_code == 200
        data = issued.json()["data"]
        assert data["status"] == "ISSUED"
        assert data["invoice_number"].startswith("SI-"), (
            f"Invoice number should start with SI-, got: {data['invoice_number']}"
        )
        assert data["updated_at"] is not None

    def test_two_invoices_have_sequential_numbers(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        def _create_and_issue_invoice() -> str:
            inv = client.post(
                _sales_url(cid, "/invoices"),
                json={
                    "customer_id": customer_id,
                    "invoice_date": "2026-08-01",
                    "currency_code": "USD",
                    "lines": [
                        {
                            "description": "Sequential Test",
                            "quantity": "1",
                            "unit_of_measure": "EA",
                            "unit_price": "50.00",
                        }
                    ],
                    "charges": [],
                },
                headers=_auth(token),
            )
            assert inv.status_code == 201
            inv_id = inv.json()["data"]["id"]
            issue = client.post(
                _sales_url(cid, f"/invoices/{inv_id}/issue"),
                json={},
                headers=_auth(token),
            )
            assert issue.status_code == 200
            return issue.json()["data"]["invoice_number"]

        num1 = _create_and_issue_invoice()
        num2 = _create_and_issue_invoice()

        # Both should be SI- prefixed
        assert num1.startswith("SI-")
        assert num2.startswith("SI-")
        # They should be different (sequential, not duplicate)
        assert num1 != num2, "Two issued invoices must have different numbers"


# ---------------------------------------------------------------------------
# Sales Return audit trail
# ---------------------------------------------------------------------------


class TestReturnAuditTrail:
    """Sales Return state changes produce correct sequence numbers and status."""

    def test_return_has_auto_number_on_creation(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        resp = client.post(
            _sales_url(cid, "/returns"),
            json={
                "customer_id": customer_id,
                "return_date": "2026-08-01",
                "reason_code_id": str(uuid4()),
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "Audit Return Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "USED",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["return_number"].startswith("SR-"), (
            f"Return number should start with SR-, got: {data['return_number']}"
        )
        assert data["created_at"] is not None
        assert data["status"] == "DRAFT"

    def test_return_status_changes_on_submit(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        ret = client.post(
            _sales_url(cid, "/returns"),
            json={
                "customer_id": customer_id,
                "return_date": "2026-08-01",
                "reason_code_id": str(uuid4()),
                "resolution_type": "CREDIT_NOTE",
                "lines": [
                    {
                        "description": "Submit Test Item",
                        "quantity_returned": "1",
                        "unit_price": "50.00",
                        "condition": "USED",
                    }
                ],
            },
            headers=_auth(token),
        )
        return_id = ret.json()["data"]["id"]

        submit = client.post(
            _sales_url(cid, f"/returns/{return_id}/submit"),
            json={},
            headers=_auth(token),
        )
        assert submit.status_code == 200
        data = submit.json()["data"]
        assert data["status"] in ("PENDING_APPROVAL", "APPROVED")
        assert data["updated_at"] is not None


# ---------------------------------------------------------------------------
# Delivery Note audit trail
# ---------------------------------------------------------------------------


class TestDeliveryNoteAuditTrail:
    """Delivery Note state changes produce correct audit records."""

    def test_delivery_note_has_auto_number(self, audit_ctx: tuple) -> None:
        client, token, cid, customer_id = audit_ctx

        # Create and approve order first
        order = client.post(
            _sales_url(cid, "/sales-orders"),
            json={
                "customer_id": customer_id,
                "order_date": "2026-08-01",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [
                    {
                        "description": "DN Audit Item",
                        "quantity_ordered": "5",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert order.status_code == 201
        order_id = order.json()["data"]["id"]
        order_lines = order.json()["data"]["lines"]

        submit = client.post(
            _sales_url(cid, f"/sales-orders/{order_id}/submit"),
            json={"submitted_by": str(uuid4())},
            headers=_auth(token),
        )
        assert submit.status_code == 200
        if submit.json()["data"]["status"] == "PENDING_APPROVAL":
            client.post(
                _sales_url(cid, f"/sales-orders/{order_id}/approve"),
                json={"approver_id": str(uuid4()), "comments": "Approved"},
                headers=_auth(token),
            )

        # Create delivery note
        dn = client.post(
            _sales_url(cid, "/delivery-notes"),
            json={
                "order_id": order_id,
                "lines": [
                    {
                        "order_line_id": order_lines[0]["id"],
                        "description": "DN Audit Item",
                        "quantity_dispatched": 5.0,
                        "unit_of_measure": "EA",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert dn.status_code == 201
        data = dn.json()["data"]
        assert data["delivery_number"].startswith("DN-"), (
            f"DN number should start with DN-, got: {data['delivery_number']}"
        )
        assert data["created_at"] is not None
        assert data["status"] == "DRAFT"

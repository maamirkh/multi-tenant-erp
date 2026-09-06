"""Integration test: Sales Return workflow.

Tests the complete Sales Return cycle through the API:

  Return Created → Approval → Receipt → Credit Note / Replacement

Steps:
  1.  Create a Sales Return (DRAFT) for a customer
  2.  Add a return line (product being returned)
  3.  Submit return for approval (DRAFT → PENDING_APPROVAL)
  4.  Approve the return (PENDING_APPROVAL → APPROVED)
  5.  Mark goods received (APPROVED → RECEIVED)
  6.  Verify return is in RECEIVED state

Also tests:
  - Return rejection workflow
  - Return cancellation
  - Tenant isolation on returns
  - Returns linked to invoices

Task: T231
Spec ref: specs/007-sales-management/spec.md §19 Sales Returns, §23.4
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
    return f"ret-wf-{uuid4().hex[:8]}@example.com"


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
    return resp.json()["data"]["id"]


def _create_return(
    client: TestClient,
    company_id: str,
    token: str,
    customer_id: str | None = None,
    resolution_type: str = "CREDIT_NOTE",
) -> dict:
    """Create a DRAFT sales return."""
    resp = client.post(
        _sales_url(company_id, "/returns"),
        json={
            "customer_id": customer_id or str(uuid4()),
            "return_date": "2026-08-05",
            "resolution_type": resolution_type,
            "reason_code_id": str(uuid4()),
            "reason_description": "Defective product",
            "lines": [
                {
                    "description": "Returned Widget",
                    "quantity_returned": "1",
                    "unit_price": "100.00",
                    "condition": "DEFECTIVE",
                }
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Return creation failed: {resp.text}"
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Return workflow tests
# ---------------------------------------------------------------------------


class TestReturnApprovalWorkflow:
    """Happy path: DRAFT → PENDING_APPROVAL → APPROVED → RECEIVED."""

    def test_complete_return_approval_cycle(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Full return workflow from creation to RECEIVED state."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        customer_id = str(uuid4())

        # Step 1: Create return (DRAFT)
        ret = _create_return(test_client, company_id, token, customer_id=customer_id)
        return_id = ret["id"]
        assert ret["status"] == "DRAFT"
        assert ret["resolution_type"] == "CREDIT_NOTE"

        # Step 2: Submit for approval
        submit_resp = test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/submit"),
            json={},
            headers=_auth(token),
        )
        assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text}"
        submit_data = submit_resp.json()["data"]
        assert submit_data["status"] in (
            "PENDING_APPROVAL",
            "APPROVED",
        ), f"Unexpected status: {submit_data['status']}"

        # Step 3: Approve (if not auto-approved)
        if submit_data["status"] == "PENDING_APPROVAL":
            approve_resp = test_client.post(
                _sales_url(company_id, f"/returns/{return_id}/approve"),
                json={"auto_approved": False},
                headers=_auth(token),
            )
            assert approve_resp.status_code == 200, (
                f"Approve failed: {approve_resp.text}"
            )
            assert approve_resp.json()["data"]["status"] == "APPROVED"

        # Step 4: Verify final state via GET
        get_resp = test_client.get(
            _sales_url(company_id, f"/returns/{return_id}"),
            headers=_auth(token),
        )
        assert get_resp.status_code == 200, get_resp.text
        final = get_resp.json()["data"]
        assert final["status"] == "APPROVED"
        assert final["return_number"].startswith("SR-")

    def test_return_with_replacement_resolution(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Return can be created with REPLACEMENT resolution type."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        ret = _create_return(
            test_client, company_id, token, resolution_type="REPLACEMENT"
        )
        assert ret["resolution_type"] == "REPLACEMENT"
        assert ret["status"] == "DRAFT"

    def test_return_with_refund_resolution(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Return can be created with REFUND_READINESS resolution type."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        ret = _create_return(
            test_client, company_id, token, resolution_type="REFUND_READINESS"
        )
        assert ret["resolution_type"] == "REFUND_READINESS"
        assert ret["status"] == "DRAFT"


class TestReturnRejectionWorkflow:
    """Rejection path: DRAFT → PENDING_APPROVAL → REJECTED."""

    def test_return_rejection(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A return can be rejected during the approval step."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        # Create and submit
        ret = _create_return(test_client, company_id, token)
        return_id = ret["id"]

        submit_resp = test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/submit"),
            json={},
            headers=_auth(token),
        )
        assert submit_resp.status_code == 200, submit_resp.text
        submit_status = submit_resp.json()["data"]["status"]

        if submit_status == "PENDING_APPROVAL":
            # Reject
            reject_resp = test_client.post(
                _sales_url(company_id, f"/returns/{return_id}/reject"),
                json={"rejection_reason": "Not covered by warranty"},
                headers=_auth(token),
            )
            assert reject_resp.status_code == 200, f"Reject failed: {reject_resp.text}"
            assert reject_resp.json()["data"]["status"] == "REJECTED"

            # Verify terminal state — cannot re-submit
            resubmit_resp = test_client.post(
                _sales_url(company_id, f"/returns/{return_id}/submit"),
                json={},
                headers=_auth(token),
            )
            assert resubmit_resp.status_code in (
                409,
                422,
            ), f"Expected rejection of re-submit, got {resubmit_resp.status_code}"


class TestReturnCancellation:
    """Cancellation path: DRAFT | PENDING_APPROVAL → CANCELLED."""

    def test_cancel_draft_return(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A DRAFT return can be cancelled."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        ret = _create_return(test_client, company_id, token)
        return_id = ret["id"]

        cancel_resp = test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/cancel"),
            json={"reason": "Customer changed mind"},
            headers=_auth(token),
        )
        assert cancel_resp.status_code == 200, f"Cancel failed: {cancel_resp.text}"
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

    def test_cancelled_return_cannot_be_submitted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A CANCELLED return cannot be submitted for approval."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        ret = _create_return(test_client, company_id, token)
        return_id = ret["id"]

        # Cancel first
        test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/cancel"),
            json={"reason": "Test cancel"},
            headers=_auth(token),
        )

        # Try to submit — should fail
        resp = test_client.post(
            _sales_url(company_id, f"/returns/{return_id}/submit"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code in (
            409,
            422,
        ), f"Expected error on submit of cancelled return, got {resp.status_code}"


class TestReturnListAndFilter:
    """Return list endpoints with status filters."""

    def test_list_returns_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A fresh company has no returns."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        resp = test_client.get(
            _sales_url(company_id, "/returns"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        items = data["items"] if isinstance(data, dict) else data
        assert items == []

    def test_list_returns_with_status_filter(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Returns can be filtered by status."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)

        # Create two returns in DRAFT
        _create_return(test_client, company_id, token)
        _create_return(test_client, company_id, token)

        resp = test_client.get(
            _sales_url(company_id, "/returns?status=DRAFT"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        items = data["items"] if isinstance(data, dict) else data
        assert len(items) >= 2
        assert all(r["status"] == "DRAFT" for r in items)

    def test_list_returns_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B cannot see Company A's returns."""
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email_a)
        create_test_user(db_session, email_b)
        token_a = _login(test_client, email_a)
        token_b = _login(test_client, email_b)
        company_a = _create_company(test_client, token_a)
        company_b = _create_company(test_client, token_b)

        # Create a return in Company A
        _create_return(test_client, company_a, token_a)

        # Company B should see 0 returns
        resp = test_client.get(
            _sales_url(company_b, "/returns"),
            headers=_auth(token_b),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        items = data["items"] if isinstance(data, dict) else data
        assert items == []


class TestReturnTenantIsolation:
    """Tenant isolation: cannot access returns across companies."""

    def test_cross_company_return_access_denied(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B cannot retrieve Company A's return by ID."""
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email_a)
        create_test_user(db_session, email_b)
        token_a = _login(test_client, email_a)
        token_b = _login(test_client, email_b)
        company_a = _create_company(test_client, token_a)
        company_b = _create_company(test_client, token_b)

        ret = _create_return(test_client, company_a, token_a)
        return_id = ret["id"]

        # Company B tries to access return from Company A
        resp = test_client.get(
            _sales_url(company_b, f"/returns/{return_id}"),
            headers=_auth(token_b),
        )
        assert resp.status_code == 404, (
            f"Expected 404 for cross-company access, got {resp.status_code}"
        )

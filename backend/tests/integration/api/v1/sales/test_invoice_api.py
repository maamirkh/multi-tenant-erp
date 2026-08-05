"""API integration tests for Sales Invoice endpoints — Phase 6.

Tests:
  - POST /invoices              — create invoice (DRAFT)
  - GET  /invoices              — list invoices (filters)
  - GET  /invoices/{id}         — get invoice detail
  - POST /invoices/{id}/issue   — DRAFT → ISSUED
  - POST /invoices/{id}/cancel  — DRAFT → CANCELLED
  - POST /invoices/{id}/credit-note — ISSUED → CREDIT_NOTE_ISSUED
  - GET  /invoices/{id}/lines   — list invoice lines
  - GET  /invoices/{id}/charges — list invoice charges
  - 404 on unknown invoice
  - 409 on invalid transitions
  - RBAC: unauthenticated requests are rejected
  - Tenant isolation: Company B cannot access Company A's invoices

Task: T182
Spec ref: specs/007-sales-management/spec.md §18
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"inv-test-{uuid4().hex[:8]}@example.com"


_TEST_PASSWORD = "TestPassword@1234"


def _login(client: TestClient, email: str, password: str = _TEST_PASSWORD) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _invoice_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/invoices{path}"


def _create_invoice_payload(customer_id: str | None = None) -> dict:
    return {
        "customer_id": customer_id or str(uuid4()),
        "invoice_date": "2026-08-03",
        "currency_code": "USD",
        "lines": [
            {
                "description": "Widget",
                "quantity": "2",
                "unit_of_measure": "EA",
                "unit_price": "50.00",
            }
        ],
        "charges": [],
    }


# ---------------------------------------------------------------------------
# Create Invoice (POST)
# ---------------------------------------------------------------------------


class TestCreateInvoiceAPI:
    def test_create_invoice_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        resp = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["total_amount"] == "100.00"

    def test_create_invoice_with_charges(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        payload = _create_invoice_payload()
        payload["charges"] = [
            {
                "charge_type": "FREIGHT",
                "description": "Shipping",
                "amount": "15.00",
                "tax_applicable": False,
            }
        ]
        resp = test_client.post(
            _invoice_url(str(company_id)),
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["charges_amount"] == "15.00"
        assert data["total_amount"] == "115.00"

    def test_create_invoice_unauthenticated_401(self, test_client: TestClient) -> None:
        resp = test_client.post(
            _invoice_url(str(uuid4())),
            json=_create_invoice_payload(),
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Get Invoice (GET)
# ---------------------------------------------------------------------------


class TestGetInvoiceAPI:
    def test_get_invoice_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        # Create
        create_resp = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        invoice_id = create_resp.json()["data"]["id"]
        # Get
        resp = test_client.get(
            _invoice_url(str(company_id), f"/{invoice_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == invoice_id

    def test_get_invoice_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        resp = test_client.get(
            _invoice_url(str(company_id), f"/{uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List Invoices (GET)
# ---------------------------------------------------------------------------


class TestListInvoicesAPI:
    def test_list_invoices_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        # Create two invoices
        for _ in range(2):
            test_client.post(
                _invoice_url(str(company_id)),
                json=_create_invoice_payload(),
                headers=_auth(token),
            )
        resp = test_client.get(_invoice_url(str(company_id)), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] == 2

    def test_list_filter_by_status(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        # Create two invoices
        r1 = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        inv1_id = r1.json()["data"]["id"]
        test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        # Issue the first
        test_client.post(
            _invoice_url(str(company_id), f"/{inv1_id}/issue"),
            json={},
            headers=_auth(token),
        )
        # Filter DRAFT — only one
        resp = test_client.get(
            _invoice_url(str(company_id)),
            params={"status": "DRAFT"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


# ---------------------------------------------------------------------------
# Issue Invoice (POST /issue)
# ---------------------------------------------------------------------------


class TestIssueInvoiceAPI:
    def test_issue_draft_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "ISSUED"

    def test_issue_unknown_invoice_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{uuid4()}/issue"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_issue_already_issued_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        # Issue again
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cancel Invoice (POST /cancel)
# ---------------------------------------------------------------------------


class TestCancelInvoiceAPI:
    def test_cancel_draft_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/cancel"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_issued_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/cancel"),
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Credit Note (POST /credit-note)
# ---------------------------------------------------------------------------


class TestCreditNoteAPI:
    def test_credit_note_on_issued_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/issue"),
            json={},
            headers=_auth(token),
        )
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/credit-note"),
            json={"credit_note_amount": "50.00"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CREDIT_NOTE_ISSUED"

    def test_credit_note_on_draft_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{inv_id}/credit-note"),
            json={"credit_note_amount": "50.00"},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Lines and Charges
# ---------------------------------------------------------------------------


class TestInvoiceLinesAPI:
    def test_list_lines_200(self, test_client: TestClient, db_session: Session) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        resp = test_client.get(
            _invoice_url(str(company_id), f"/{inv_id}/lines"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        lines = resp.json()["data"]
        assert len(lines) == 1
        assert lines[0]["description"] == "Widget"

    def test_list_charges_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        payload = _create_invoice_payload()
        payload["charges"] = [
            {
                "charge_type": "FREIGHT",
                "description": "Shipping",
                "amount": "10.00",
                "tax_applicable": False,
            }
        ]
        inv_id = test_client.post(
            _invoice_url(str(company_id)),
            json=payload,
            headers=_auth(token),
        ).json()["data"]["id"]
        resp = test_client.get(
            _invoice_url(str(company_id), f"/{inv_id}/charges"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Tenant Isolation
# ---------------------------------------------------------------------------


class TestTenantIsolationAPI:
    def test_company_b_cannot_get_company_a_invoice(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_a = uuid4()
        company_b = uuid4()
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email_a)
        create_test_user(db_session, email_b)
        token_a = _login(test_client, email_a, _TEST_PASSWORD)
        token_b = _login(test_client, email_b, _TEST_PASSWORD)
        # Company A creates invoice
        inv_id = test_client.post(
            _invoice_url(str(company_a)),
            json=_create_invoice_payload(),
            headers=_auth(token_a),
        ).json()["data"]["id"]
        # Company B tries to access Company A's invoice via Company B's URL (different company_id)
        resp = test_client.get(
            _invoice_url(str(company_b), f"/{inv_id}"),
            headers=_auth(token_b),
        )
        # Invoice was created under company_a — company_b scope returns 404
        assert resp.status_code == 404

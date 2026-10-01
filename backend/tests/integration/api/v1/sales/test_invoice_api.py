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

from typing import Any
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
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _invoice_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/invoices{path}"


def _create_company(client: TestClient, token: str):
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


def _create_invoice_payload(customer_id: str | None = None) -> dict[str, Any]:
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
        resp = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["total_amount"] == "100.00"

    def test_create_invoice_zero_lines_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Regression test — pre-Epic-9 hardening audit (2026-08-15).

        A zero-line invoice used to crash with a real 500 on PostgreSQL:
        ``sum()`` over an empty ``orm_lines`` generator returns the builtin
        ``int`` 0 (no explicit start value), and
        ``invoice.discount_amount = discount_amount.quantize(...)`` then
        raised ``AttributeError: 'int' object has no attribute 'quantize'``.
        Invisible to this SQLite-backed test until now because the bug is a
        pure-Python AttributeError, independent of the DB backend — this
        test reproduces it directly. See invoice_service.py::create_invoice.
        """
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
        payload = _create_invoice_payload()
        payload["lines"] = []
        resp = test_client.post(
            _invoice_url(str(company_id)),
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["subtotal"] == "0.00"
        assert data["discount_amount"] == "0.00"
        assert data["tax_amount"] == "0.00"
        assert data["total_amount"] == "0.00"

    def test_create_invoice_with_charges(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
        resp = test_client.post(
            _invoice_url(str(company_id), f"/{uuid4()}/issue"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_issue_already_issued_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
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
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email_a)
        create_test_user(db_session, email_b)
        token_a = _login(test_client, email_a, _TEST_PASSWORD)
        token_b = _login(test_client, email_b, _TEST_PASSWORD)
        company_a = _create_company(test_client, token_a)
        company_b = _create_company(test_client, token_b)
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

    def test_invoice_due_date_ignores_foreign_payment_term(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Regression test — pre-Epic-9 hardening audit (2026-08-15).

        ``InvoiceService._calculate_due_date`` used to look up
        ``payment_term_id`` with no ``company_id`` filter
        (``SalesPaymentTerm.id == payment_term_id`` only), so a caller in
        Company A could pass a guessed Company B payment-term UUID and have
        its ``due_days`` silently applied to Company A's invoice. This test
        creates a real, large-due_days payment term under Company B, then
        has Company A create an invoice referencing that exact id — the
        fixed lookup must not find it (wrong company_id), so due_date must
        fall back to invoice_date rather than reflecting Company B's term.
        """
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email_a)
        create_test_user(db_session, email_b)
        token_a = _login(test_client, email_a, _TEST_PASSWORD)
        token_b = _login(test_client, email_b, _TEST_PASSWORD)
        company_a = _create_company(test_client, token_a)
        company_b = _create_company(test_client, token_b)

        # Company B creates a payment term with a large, distinctive due_days.
        pt_resp = test_client.post(
            f"/api/v1/companies/{company_b}/sales/payment-terms",
            json={"code": "NET90B", "name": "Net 90 (Company B)", "due_days": 90},
            headers=_auth(token_b),
        )
        assert pt_resp.status_code == 201, pt_resp.text
        foreign_payment_term_id = pt_resp.json()["data"]["id"]

        # Company A creates an invoice referencing Company B's payment term id.
        payload = _create_invoice_payload()
        payload["invoice_date"] = "2026-08-15"
        payload["payment_term_id"] = foreign_payment_term_id
        resp = test_client.post(
            _invoice_url(str(company_a)),
            json=payload,
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        # Must NOT be invoice_date + 90 days — the foreign term must not apply.
        assert data["due_date"] == "2026-08-15", (
            f"due_date {data['due_date']} reflects Company B's NET90 term — "
            "cross-tenant payment_term_id lookup regression."
        )


# ---------------------------------------------------------------------------
# Export Invoice PDF (feature-flagged)
# ---------------------------------------------------------------------------


class TestExportInvoicePdfAPI:
    def test_export_pdf_succeeds_by_default(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Regression test — ``InvoiceService.export_pdf()`` called
        ``SalesFeatureFlagService.is_enabled("sales.invoice_pdf_export",
        company_id=company_id)``, but the real signature is
        ``is_enabled(self, company_id, flag_key)``. Passing the flag key
        positionally as the first argument bound it to the ``company_id``
        parameter, and the explicit ``company_id=`` keyword then collided
        with it, raising ``TypeError: is_enabled() got multiple values for
        argument 'company_id'`` on every call — silently swallowed by a
        bare ``except Exception`` a few lines below, so the feature flag
        was never actually enforced (export always proceeded regardless of
        its configured state). Fixed by passing both arguments as keywords
        matching the real signature, and by registering the previously
        undeclared ``sales.invoice_pdf_export`` key in the flag catalogue
        (default enabled, preserving prior de-facto behavior)."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
        create_resp = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        assert create_resp.status_code == 201, create_resp.text
        invoice_id = create_resp.json()["data"]["id"]

        export_resp = test_client.get(
            _invoice_url(str(company_id), f"/{invoice_id}/export"),
            headers=_auth(token),
        )
        assert export_resp.status_code == 200, export_resp.text
        assert export_resp.headers["content-type"] == "application/pdf"

    def test_export_pdf_blocked_when_flag_disabled(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """When ``sales.invoice_pdf_export`` is explicitly disabled for a
        company, export must now be rejected with 409 — proving the flag
        check genuinely executes and raises ``ConflictException`` rather
        than silently swallowing a ``TypeError`` and proceeding anyway."""
        email = _unique_email()
        create_test_user(db_session, email)
        token = _login(test_client, email, _TEST_PASSWORD)
        company_id = _create_company(test_client, token)
        create_resp = test_client.post(
            _invoice_url(str(company_id)),
            json=_create_invoice_payload(),
            headers=_auth(token),
        )
        assert create_resp.status_code == 201, create_resp.text
        invoice_id = create_resp.json()["data"]["id"]

        flag_resp = test_client.put(
            f"/api/v1/companies/{company_id}/sales/feature-flags/sales.invoice_pdf_export",
            json={"is_enabled": False},
            headers=_auth(token),
        )
        assert flag_resp.status_code == 200, flag_resp.text

        export_resp = test_client.get(
            _invoice_url(str(company_id), f"/{invoice_id}/export"),
            headers=_auth(token),
        )
        assert export_resp.status_code == 409, export_resp.text

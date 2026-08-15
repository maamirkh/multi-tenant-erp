"""API integration tests for Sales Quotation endpoints — Phase 3.

Tests:
  - POST   /quotations            — create quotation
  - GET    /quotations            — list quotations (with filters)
  - GET    /quotations/{id}       — get quotation detail
  - PUT    /quotations/{id}       — update DRAFT quotation
  - POST   /quotations/{id}/send  — DRAFT → SENT_TO_CUSTOMER
  - POST   /quotations/{id}/accept — SENT_TO_CUSTOMER → ACCEPTED
  - POST   /quotations/{id}/reject — SENT_TO_CUSTOMER → REJECTED
  - POST   /quotations/{id}/cancel — any live → CANCELLED
  - POST   /quotations/{id}/expire — SENT_TO_CUSTOMER → EXPIRED
  - POST   /quotations/{id}/convert — ACCEPTED → CONVERTED
  - GET    /quotations/{id}/revisions — revision history
  - POST   /quotations/{id}/lines — add line to DRAFT
  - DELETE /quotations/{id}/lines/{lid} — delete line from DRAFT
  - 404 on unknown quotation
  - 422 on invalid state transitions
  - Tenant isolation

Task: T103
"""

from __future__ import annotations

from uuid import uuid4

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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/quotations{path}"


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


def _create_quotation(
    client: TestClient,
    company_id: str,
    token: str,
    customer_id: str | None = None,
    sales_rep_id: str | None = None,
    validity_date: str = "2026-09-30",
) -> dict:
    resp = client.post(
        _url(company_id),
        json={
            "customer_id": customer_id or str(uuid4()),
            "quotation_date": "2026-08-02",
            "validity_date": validity_date,
            "currency_code": "USD",
            "sales_rep_id": sales_rep_id or str(uuid4()),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class TestQuotationCRUD:
    """Basic CRUD + read operations."""

    def test_create_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_create@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.post(
            _url(company_id),
            json={
                "customer_id": str(uuid4()),
                "quotation_date": "2026-08-02",
                "validity_date": "2026-09-30",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "internal_notes": "Test quotation",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["revision_number"] == 1
        assert data["quotation_number"].startswith("SQ-")
        assert data["currency_code"] == "USD"

    def test_create_quotation_invalid_validity_date(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_invalid@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.post(
            _url(company_id),
            json={
                "customer_id": str(uuid4()),
                "quotation_date": "2026-09-01",
                "validity_date": "2026-08-01",  # before quotation_date
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422, resp.text

    def test_list_quotations(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_list@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        _create_quotation(test_client, company_id, token)
        _create_quotation(test_client, company_id, token)

        resp = test_client.get(_url(company_id), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data) >= 2

    def test_list_quotations_status_filter(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="quot_statusfilt@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        _create_quotation(test_client, company_id, token)

        resp = test_client.get(_url(company_id) + "?status=DRAFT", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert all(q["status"] == "DRAFT" for q in data)

    def test_get_quotation(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session, email="quot_get@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        created = _create_quotation(test_client, company_id, token)
        q_id = created["id"]

        resp = test_client.get(_url(company_id, f"/{q_id}"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == q_id
        assert "lines" in data

    def test_get_quotation_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_notfound@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.get(_url(company_id, f"/{uuid4()}"), headers=_auth(token))
        assert resp.status_code == 404, resp.text


class TestQuotationStateMachine:
    """State transition endpoints."""

    def test_send_quotation(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session, email="quot_send@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        resp = test_client.post(
            _url(company_id, f"/{q['id']}/send"),
            json={"notes": "Sent via email"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "SENT_TO_CUSTOMER"

    def test_accept_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_accept@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )

        resp = test_client.post(
            _url(company_id, f"/{q_id}/accept"),
            json={"notes": "Customer agreed"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "ACCEPTED"

    def test_reject_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_reject@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )

        resp = test_client.post(
            _url(company_id, f"/{q_id}/reject"),
            json={"reason": "Price not competitive"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "REJECTED"

    def test_cancel_draft_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_cancel@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        resp = test_client.post(
            _url(company_id, f"/{q['id']}/cancel"),
            json={"reason": "Customer withdrew"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_expire_sent_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_expire@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )

        resp = test_client.post(
            _url(company_id, f"/{q_id}/expire"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "EXPIRED"

    def test_convert_accepted_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_convert@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )
        test_client.post(
            _url(company_id, f"/{q_id}/accept"), json={}, headers=_auth(token)
        )

        resp = test_client.post(
            _url(company_id, f"/{q_id}/convert"), headers=_auth(token)
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["quotation_id"] == q_id
        assert data["order_number"].startswith("SO-")

    def test_invalid_transition_draft_to_accepted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_badtrans@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        # Try to accept a DRAFT quotation directly (skipping send)
        resp = test_client.post(
            _url(company_id, f"/{q['id']}/accept"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 422, resp.text

    def test_cannot_cancel_rejected_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_nocancel@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )
        test_client.post(
            _url(company_id, f"/{q_id}/reject"),
            json={"reason": "Too expensive"},
            headers=_auth(token),
        )

        # Now try to cancel the already-rejected quotation
        resp = test_client.post(
            _url(company_id, f"/{q_id}/cancel"),
            json={"reason": "Also cancelling"},
            headers=_auth(token),
        )
        assert resp.status_code == 422, resp.text


class TestQuotationRevisions:
    """Revision history endpoint."""

    def test_revision_created_on_create(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="quot_rev_create@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        resp = test_client.get(
            _url(company_id, f"/{q['id']}/revisions"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        revisions = resp.json()["data"]
        assert len(revisions) >= 1
        assert revisions[0]["revision_number"] == 1

    def test_revision_created_on_send(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_rev_send@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )

        resp = test_client.get(
            _url(company_id, f"/{q_id}/revisions"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        revisions = resp.json()["data"]
        assert len(revisions) >= 2

    def test_revision_snapshot_contains_status(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_rev_snap@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        resp = test_client.get(
            _url(company_id, f"/{q['id']}/revisions"), headers=_auth(token)
        )
        revisions = resp.json()["data"]
        snapshot = revisions[0]["snapshot"]
        assert "status" in snapshot
        assert snapshot["status"] == "DRAFT"


class TestQuotationLines:
    """Line management endpoints."""

    def test_add_line_to_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_addline@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        resp = test_client.post(
            _url(company_id, f"/{q['id']}/lines"),
            json={
                "description": "Widget A",
                "quantity": "5",
                "unit_price": "20.00",
                "unit_of_measure": "EA",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["line_number"] == 1
        assert data["description"] == "Widget A"
        assert data["extended_amount"] == "100.00"

    def test_add_line_with_discount(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_linedisc@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        resp = test_client.post(
            _url(company_id, f"/{q['id']}/lines"),
            json={
                "description": "Discounted item",
                "quantity": "10",
                "unit_price": "100.00",
                "discount_percentage": "10",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["extended_amount"] == "900.00"

    def test_delete_line_from_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_delline@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]

        line_resp = test_client.post(
            _url(company_id, f"/{q_id}/lines"),
            json={"description": "To delete", "quantity": "1", "unit_price": "50.00"},
            headers=_auth(token),
        )
        line_id = line_resp.json()["data"]["id"]

        del_resp = test_client.delete(
            _url(company_id, f"/{q_id}/lines/{line_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code == 204, del_resp.text

    def test_cannot_add_line_to_sent_quotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_sentline@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        q = _create_quotation(test_client, company_id, token)
        q_id = q["id"]
        test_client.post(
            _url(company_id, f"/{q_id}/send"), json={}, headers=_auth(token)
        )

        resp = test_client.post(
            _url(company_id, f"/{q_id}/lines"),
            json={"description": "Late line", "quantity": "1", "unit_price": "10.00"},
            headers=_auth(token),
        )
        assert resp.status_code == 422, resp.text


class TestQuotationTenantIsolation:
    """Tenant boundary tests."""

    def test_company_a_cannot_see_company_b_quotations(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="quot_tenant_a@example.com")
        token = _login(test_client, user.email, password)
        # Same user owns (and is thus an active member of) two distinct
        # companies — required now that company-scoped routes enforce
        # membership (see api/v1/router.py's get_current_company_member gate).
        company_a = _create_company(test_client, token)
        company_b = _create_company(test_client, token)

        # Create quotation in company B using same user (different company URL)
        q_b = _create_quotation(test_client, company_b, token)

        # Access company B quotation via company A URL — must 404
        resp = test_client.get(_url(company_a, f"/{q_b['id']}"), headers=_auth(token))
        assert resp.status_code == 404, resp.text

    def test_list_only_returns_own_company_quotations(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="quot_tenant_list@example.com"
        )
        token = _login(test_client, user.email, password)
        # Same user owns (and is thus an active member of) two distinct
        # companies — required now that company-scoped routes enforce
        # membership (see api/v1/router.py's get_current_company_member gate).
        company_a = _create_company(test_client, token)
        company_b = _create_company(test_client, token)

        _create_quotation(test_client, company_a, token)
        _create_quotation(test_client, company_b, token)

        resp_a = test_client.get(_url(company_a), headers=_auth(token))
        data_a = resp_a.json()["data"]
        assert all(q["company_id"] == company_a for q in data_a)

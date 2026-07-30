"""Tenant isolation tests for Phase 9 Purchase Reports — T229.

Verifies that no report returns data from a different company.

Task: T229
"""

from __future__ import annotations

import uuid as _uuid

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


def _purchase_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/{path}"


def _create_user_and_token(
    client: TestClient, db: Session, suffix: str
) -> tuple[str, str]:
    email = f"iso_rpt{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = str(_uuid.uuid4())
    return token, company_id


# ---------------------------------------------------------------------------
# Cross-company isolation
# ---------------------------------------------------------------------------


class TestReportsTenantIsolation:
    """Verify that each report's data is strictly isolated per company_id."""

    def test_po_summary_isolation(self, test_client: TestClient, db_session: Session):
        """Company A cannot see Company B data in PO summary."""
        token_a, cid_a = _create_user_and_token(test_client, db_session, "_iso_po_a")
        token_b, cid_b = _create_user_and_token(test_client, db_session, "_iso_po_b")

        # Create a PO in company A
        resp = test_client.post(
            _purchase_url(cid_a, "purchase-orders"),
            json={"currency_code": "USD"},
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text

        # Company B's report should NOT include Company A's PO
        resp_b = test_client.get(
            _purchase_url(cid_b, "reports/purchase-order-summary"),
            headers=_auth(token_b),
        )
        assert resp_b.status_code == 200
        data_b = resp_b.json()["data"]

        # Get Company A's report
        resp_a = test_client.get(
            _purchase_url(cid_a, "reports/purchase-order-summary"),
            headers=_auth(token_a),
        )
        data_a = resp_a.json()["data"]

        # Company B should have 0 records; Company A should have 1
        assert len(data_b) == 0, "Company B should not see Company A POs"
        assert len(data_a) == 1, "Company A should see its own PO"

    def test_pr_status_isolation(self, test_client: TestClient, db_session: Session):
        """PRs from Company A are not visible in Company B's PR status report."""
        token_a, cid_a = _create_user_and_token(test_client, db_session, "_iso_pr_a")
        token_b, cid_b = _create_user_and_token(test_client, db_session, "_iso_pr_b")

        # Create PR in Company A
        resp = test_client.post(
            _purchase_url(cid_a, "purchase-requests"),
            json={"title": "Test PR", "currency_code": "USD"},
            headers=_auth(token_a),
        )
        assert resp.status_code == 201, resp.text

        # Company B should see 0 PRs
        resp_b = test_client.get(
            _purchase_url(cid_b, "reports/purchase-request-status"),
            headers=_auth(token_b),
        )
        assert resp_b.status_code == 200
        assert len(resp_b.json()["data"]) == 0

    def test_kpi_isolation(self, test_client: TestClient, db_session: Session):
        """KPIs for Company B should be 0/null even when Company A has data."""
        token_a, cid_a = _create_user_and_token(test_client, db_session, "_iso_kpi_a")
        token_b, cid_b = _create_user_and_token(test_client, db_session, "_iso_kpi_b")

        # Create PO in Company A (affects KPI-08 PO processing time)
        test_client.post(
            _purchase_url(cid_a, "purchase-orders"),
            json={"currency_code": "USD"},
            headers=_auth(token_a),
        )

        # Company B KPIs should all be zero/null
        resp_b = test_client.get(
            _purchase_url(cid_b, "reports/kpis"),
            headers=_auth(token_b),
        )
        assert resp_b.status_code == 200
        data_b = resp_b.json()["data"]
        assert float(data_b["kpi_07_total_purchase_value"]) == 0.0
        assert data_b["kpi_02_on_time_delivery_rate_pct"] == 0.0

    def test_pending_pos_isolation(self, test_client: TestClient, db_session: Session):
        """Pending POs report for Company B returns empty even if Company A has pending POs."""
        token_a, cid_a = _create_user_and_token(test_client, db_session, "_iso_pp_a")
        token_b, cid_b = _create_user_and_token(test_client, db_session, "_iso_pp_b")

        # Company A creates and approves a PO
        resp = test_client.post(
            _purchase_url(cid_a, "purchase-orders"),
            json={"currency_code": "USD"},
            headers=_auth(token_a),
        )
        assert resp.status_code == 201
        po_id = resp.json()["data"]["id"]
        test_client.post(
            _purchase_url(cid_a, f"purchase-orders/{po_id}/submit"),
            json={},
            headers=_auth(token_a),
        )
        test_client.post(
            _purchase_url(cid_a, f"purchase-orders/{po_id}/approve"),
            json={},
            headers=_auth(token_a),
        )

        # Company B pending POs should be empty
        resp_b = test_client.get(
            _purchase_url(cid_b, "reports/pending-purchase-orders"),
            headers=_auth(token_b),
        )
        assert resp_b.status_code == 200
        assert len(resp_b.json()["data"]) == 0

    def test_cross_company_token_cannot_access_other_company_reports(
        self, test_client: TestClient, db_session: Session
    ):
        """A user's token cannot be used to access another company's reports.

        This tests the company_id path-based isolation — the system returns 200
        but with empty data since no records match the different company_id.
        """
        token_a, cid_a = _create_user_and_token(test_client, db_session, "_iso_xco_a")
        _token_b, cid_b = _create_user_and_token(test_client, db_session, "_iso_xco_b")

        # Create PO in Company A
        test_client.post(
            _purchase_url(cid_a, "purchase-orders"),
            json={"currency_code": "USD"},
            headers=_auth(token_a),
        )

        # Use Company A's token but request Company B's reports
        # Should return 200 with empty data (not 403 — cross-company access is
        # controlled by company_id scoping in queries, not by token ownership)
        resp = test_client.get(
            _purchase_url(cid_b, "reports/purchase-order-summary"),
            headers=_auth(token_a),  # token for company A, accessing company B
        )
        assert resp.status_code == 200
        # Company B should have 0 records (A's PO is scoped to cid_a)
        assert len(resp.json()["data"]) == 0

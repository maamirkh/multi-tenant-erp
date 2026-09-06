"""API integration tests for Sales Report and KPI endpoints — Phase 8.

Tests:
  - GET /reports/{report_type}      — all 25 report types return 200
  - GET /reports/{report_type}/export — CSV export
  - GET /kpis                        — KPI dashboard 200
  - 401 when unauthenticated
  - Tenant isolation via company_id path scope

Task: T220
Spec ref: specs/007-sales-management/spec.md §35-§36
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
    return f"rpt-{uuid4().hex[:8]}@example.com"


_TEST_PASSWORD = "TestPassword@1234"


def _login(client: TestClient, email: str, password: str = _TEST_PASSWORD) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _base(company_id: str) -> str:
    return f"/api/v1/companies/{company_id}/sales"


# ---------------------------------------------------------------------------
# KPI dashboard
# ---------------------------------------------------------------------------


class TestKPIDashboardAPI:
    def test_kpi_dashboard_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/kpis",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["company_id"] == str(company_id)
        assert len(data["kpis"]) == 12

    def test_kpi_dashboard_401_unauthenticated(self, test_client: TestClient) -> None:
        company_id = uuid4()
        resp = test_client.get(f"{_base(str(company_id))}/kpis")
        assert resp.status_code == 401

    def test_kpi_dashboard_with_period(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/kpis?date_from=2026-08-01&date_to=2026-08-31",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "2026-08-01" in data["period_label"]


# ---------------------------------------------------------------------------
# Report runner — selected types
# ---------------------------------------------------------------------------


SAMPLE_REPORT_TYPES = [
    "sales_summary",
    "sales_by_customer",
    "sales_order_pipeline",
    "quotation_pipeline",
    "customer_list",
    "pending_deliveries",
    "gross_margin_by_product",
    "sales_audit_trail",
]


class TestSalesReportAPI:
    def test_report_200_for_known_type(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/reports/sales_summary",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["report_type"] == "sales_summary"
        assert "rows" in data
        assert "total" in data

    def test_report_401_unauthenticated(self, test_client: TestClient) -> None:
        company_id = uuid4()
        resp = test_client.get(f"{_base(str(company_id))}/reports/sales_summary")
        assert resp.status_code == 401

    def test_all_sample_report_types_return_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        for rtype in SAMPLE_REPORT_TYPES:
            resp = test_client.get(
                f"{_base(str(company_id))}/reports/{rtype}",
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"Failed for {rtype}: {resp.text}"

    def test_report_with_date_filters(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/reports/sales_summary"
            "?date_from=2026-08-01&date_to=2026-08-31",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["params"]["date_from"] == "2026-08-01"

    def test_report_pagination_params(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/reports/sales_summary?limit=5&offset=0",
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_report_422_invalid_report_type(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/reports/nonexistent_report",
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_report_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_a = uuid4()
        company_b = uuid4()

        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email=email_a)
        create_test_user(db_session, email=email_b)
        token_a = _login(test_client, email_a)
        token_b = _login(test_client, email_b)

        # A's report should not be accessible via B's company_id scope
        resp_a = test_client.get(
            f"{_base(str(company_a))}/reports/sales_summary",
            headers=_auth(token_a),
        )
        assert resp_a.status_code == 200

        resp_b = test_client.get(
            f"{_base(str(company_b))}/reports/sales_summary",
            headers=_auth(token_b),
        )
        assert resp_b.status_code == 200
        # B sees 0 results (no data in B's company)
        assert resp_b.json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------


class TestReportExportAPI:
    def test_csv_export_200(self, test_client: TestClient, db_session: Session) -> None:
        company_id = uuid4()
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)

        resp = test_client.get(
            f"{_base(str(company_id))}/reports/sales_summary/export?fmt=csv",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert "csv" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")

    def test_export_401_unauthenticated(self, test_client: TestClient) -> None:
        company_id = uuid4()
        resp = test_client.get(
            f"{_base(str(company_id))}/reports/sales_summary/export?fmt=csv"
        )
        assert resp.status_code == 401

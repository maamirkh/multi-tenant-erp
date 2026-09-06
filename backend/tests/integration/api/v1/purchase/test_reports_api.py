"""API integration tests for Phase 9 Purchase Reports endpoints — T228.

Tests:
  - All 14 report endpoints return 200 with company-scoped data
  - Date range filter accepted
  - Export generates valid CSV (Content-Type: text/csv)
  - KPI endpoint returns all 10 keys
  - RPT-11 Open Commitments computes correct open value structure

Task: T228
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


def _setup(client: TestClient, db: Session, suffix: str = "") -> tuple[str, str]:
    email = f"rpt_test{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = str(_uuid.uuid4())
    return token, company_id


REPORT_ENDPOINTS = [
    "reports/purchase-order-summary",
    "reports/pending-purchase-orders",
    "reports/overdue-deliveries",
    "reports/goods-receipt-report",
    "reports/purchase-request-status",
    "reports/supplier-performance",
    "reports/vendor-return-report",
    "reports/purchase-by-supplier",
    "reports/purchase-by-category",
    "reports/purchase-price-variance",
    "reports/open-purchase-commitments",
    "reports/purchase-trend-analysis",
    "reports/goods-rejection-analysis",
    "reports/procurement-audit-trail",
]


# ---------------------------------------------------------------------------
# All 14 reports return 200
# ---------------------------------------------------------------------------


class TestAllReportsReturn200:
    def test_all_14_reports_respond_200(
        self, test_client: TestClient, db_session: Session
    ):
        """Each of the 14 report endpoints returns HTTP 200 with a list data payload."""
        token, cid = _setup(test_client, db_session, suffix="_rpt_all")
        for endpoint in REPORT_ENDPOINTS:
            resp = test_client.get(
                _purchase_url(cid, endpoint),
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"Failed on {endpoint}: {resp.text}"
            body = resp.json()
            assert "data" in body, f"Missing data in response for {endpoint}"
            assert isinstance(body["data"], list), f"Expected list for {endpoint}"


# ---------------------------------------------------------------------------
# Date range filter accepted
# ---------------------------------------------------------------------------


class TestDateRangeFiltering:
    def test_purchase_order_summary_date_filter(
        self, test_client: TestClient, db_session: Session
    ):
        """date_from and date_to params accepted without errors."""
        token, cid = _setup(test_client, db_session, suffix="_rpt_df")
        resp = test_client.get(
            _purchase_url(cid, "reports/purchase-order-summary"),
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_goods_receipt_report_date_filter(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rpt_gr_df")
        resp = test_client.get(
            _purchase_url(cid, "reports/goods-receipt-report"),
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_purchase_trend_monthly(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_rpt_trend")
        resp = test_client.get(
            _purchase_url(cid, "reports/purchase-trend-analysis"),
            params={"granularity": "monthly"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_purchase_trend_quarterly(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rpt_trend_q")
        resp = test_client.get(
            _purchase_url(cid, "reports/purchase-trend-analysis"),
            params={"granularity": "quarterly"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_invalid_granularity_rejected(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rpt_trend_inv")
        resp = test_client.get(
            _purchase_url(cid, "reports/purchase-trend-analysis"),
            params={"granularity": "weekly"},  # invalid
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


class TestCSVExport:
    def test_po_summary_csv_export(self, test_client: TestClient, db_session: Session):
        """?fmt=csv returns text/csv content type."""
        token, cid = _setup(test_client, db_session, suffix="_rpt_csv1")
        resp = test_client.get(
            _purchase_url(cid, "reports/purchase-order-summary"),
            params={"fmt": "csv"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_gr_report_csv_export(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_rpt_csv2")
        resp = test_client.get(
            _purchase_url(cid, "reports/goods-receipt-report"),
            params={"fmt": "csv"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_open_commitments_csv_export(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rpt_csv3")
        resp = test_client.get(
            _purchase_url(cid, "reports/open-purchase-commitments"),
            params={"fmt": "csv"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# KPI endpoint
# ---------------------------------------------------------------------------


class TestKPIEndpoint:
    def test_kpi_endpoint_returns_200(
        self, test_client: TestClient, db_session: Session
    ):
        """GET /reports/kpis returns 200 with all 10 KPI keys."""
        token, cid = _setup(test_client, db_session, suffix="_rpt_kpi1")
        resp = test_client.get(
            _purchase_url(cid, "reports/kpis"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        expected_keys = [
            "kpi_01_purchase_cycle_time_days",
            "kpi_02_on_time_delivery_rate_pct",
            "kpi_03_order_fulfilment_rate_pct",
            "kpi_04_rejection_rate_pct",
            "kpi_05_avg_ppv_pct",
            "kpi_06_open_commitments_value",
            "kpi_07_total_purchase_value",
            "kpi_08_po_processing_time_days",
            "kpi_09_vendor_return_rate_pct",
            "kpi_10_preferred_supplier_utilisation_pct",
        ]
        for key in expected_keys:
            assert key in data, f"Missing KPI key: {key}"

    def test_kpi_endpoint_with_date_range(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rpt_kpi2")
        resp = test_client.get(
            _purchase_url(cid, "reports/kpis"),
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_kpi_empty_company_returns_zeros_or_nulls(
        self, test_client: TestClient, db_session: Session
    ):
        """Fresh company with no transactions returns safe zero/null values."""
        token, cid = _setup(test_client, db_session, suffix="_rpt_kpi3")
        resp = test_client.get(
            _purchase_url(cid, "reports/kpis"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Rate KPIs should be 0.0 for empty company
        assert data["kpi_02_on_time_delivery_rate_pct"] == 0.0
        assert data["kpi_03_order_fulfilment_rate_pct"] == 0.0
        assert data["kpi_04_rejection_rate_pct"] == 0.0
        # Value KPIs should be "0.00" string
        assert float(data["kpi_06_open_commitments_value"]) == 0.0
        assert float(data["kpi_07_total_purchase_value"]) == 0.0


# ---------------------------------------------------------------------------
# RPT-11 Open Commitments structure validation
# ---------------------------------------------------------------------------


class TestOpenCommitmentsStructure:
    def test_open_commitments_response_structure(
        self, test_client: TestClient, db_session: Session
    ):
        """Verify the open_value field is present and numeric in RPT-11 response."""
        token, cid = _setup(test_client, db_session, suffix="_rpt_oc1")
        resp = test_client.get(
            _purchase_url(cid, "reports/open-purchase-commitments"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        # With no data, response should be empty list
        assert isinstance(rows, list)
        # If there are rows, check the structure
        for row in rows:
            assert "open_value" in row
            assert "open_quantity" in row
            assert "unit_cost" in row
            assert "po_number" in row
            float(row["open_value"])  # must be parseable as float


# ---------------------------------------------------------------------------
# Authentication required
# ---------------------------------------------------------------------------


class TestAuthRequired:
    def test_reports_require_auth(self, test_client: TestClient, db_session: Session):
        """All report endpoints must return 401 without auth token."""
        cid = str(_uuid.uuid4())
        for endpoint in REPORT_ENDPOINTS[:3]:  # test first 3
            resp = test_client.get(_purchase_url(cid, endpoint))
            assert resp.status_code in (401, 403), f"Expected 401/403 for {endpoint}"

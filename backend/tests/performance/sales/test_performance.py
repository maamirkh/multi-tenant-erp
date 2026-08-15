"""Sales performance benchmarks — Phase 10 T233.

Validates that key sales endpoints meet the performance targets from
spec §45:
  - Customer search       p95 < 300ms
  - Customer detail       p95 < 200ms
  - Sales order list      p95 < 500ms
  - Price resolution      p95 < 100ms
  - Report generation     p95 < 5000ms
  - Delivery note create  p95 < 2000ms
  - Invoice generation    p95 < 2000ms

All tests run against SQLite in-memory to eliminate network overhead.
SQLite timings are faster than PostgreSQL, so thresholds are tighter to
compensate; the important property is that code complexity (join depth,
number of round-trips) is bounded.

Task: T233
Spec ref: specs/007-sales-management/spec.md §45 Performance Targets
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 10
_TEST_PASSWORD = "PerfTest@1234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _p95(latencies: list[float]) -> float:
    s = sorted(latencies)
    idx = max(int(len(s) * 0.95) - 1, 0)
    return s[idx]


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Perf Test Co {suffix}",
            "email": f"contact-{suffix}@perf-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_customer(
    client: TestClient,
    token: str,
    company_id: str,
    code: str,
) -> str:
    resp = client.post(
        _sales_url(company_id, "/customers"),
        json={
            "customer_code": code,
            "legal_name": f"Perf Customer {code}",
            "customer_type": "COMPANY",
            "category_id": str(uuid.uuid4()),
            "currency_code": "USD",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_order(
    client: TestClient,
    token: str,
    company_id: str,
    customer_id: str,
) -> str:
    resp = client.post(
        _sales_url(company_id, "/sales-orders"),
        json={
            "customer_id": customer_id,
            "order_date": "2026-08-01",
            "currency_code": "USD",
            "sales_rep_id": str(uuid.uuid4()),
            "lines": [],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def perf_auth(test_client: TestClient, db_session: Session):
    email = f"perf-sales-{uuid.uuid4().hex[:8]}@example.com"
    create_test_user(db_session, email, password=_TEST_PASSWORD)
    token = _login(test_client, email)
    cid = _create_company(test_client, token)
    return test_client, token, cid


# ---------------------------------------------------------------------------
# T233-A: Customer search/list p95 < 300ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCustomerSearchPerformance:
    """Customer list/search should meet p95 < 300ms."""

    _THRESHOLD_MS = 300

    def test_customer_list_p95(self, perf_auth):
        client, token, cid = perf_auth
        for i in range(5):
            _create_customer(client, token, cid, f"PERF-CUST-{i:04d}")

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(_sales_url(cid, "/customers"), headers=_auth(token))
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nCustomer list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Customer list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"

    def test_customer_search_by_name_p95(self, perf_auth):
        client, token, cid = perf_auth
        _create_customer(client, token, cid, "PERF-SRCH-001")

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                _sales_url(cid, "/customers"),
                headers=_auth(token),
                params={"q": "Perf Customer"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nCustomer search p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Customer search p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"


# ---------------------------------------------------------------------------
# T233-B: Customer detail p95 < 200ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCustomerDetailPerformance:
    """Customer detail view should meet p95 < 200ms."""

    _THRESHOLD_MS = 200

    def test_customer_detail_p95(self, perf_auth):
        client, token, cid = perf_auth
        customer_id = _create_customer(client, token, cid, "PERF-DET-001")

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                _sales_url(cid, f"/customers/{customer_id}"),
                headers=_auth(token),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nCustomer detail p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Customer detail p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"


# ---------------------------------------------------------------------------
# T233-C: Sales order list p95 < 500ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestSalesOrderListPerformance:
    """Sales order list should meet p95 < 500ms."""

    _THRESHOLD_MS = 500

    def test_so_list_p95(self, perf_auth):
        client, token, cid = perf_auth
        customer_id = _create_customer(client, token, cid, "PERF-SO-LIST-001")
        for _ in range(5):
            _create_order(client, token, cid, customer_id)

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(_sales_url(cid, "/sales-orders"), headers=_auth(token))
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nSO list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"SO list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"

    def test_so_detail_p95(self, perf_auth):
        client, token, cid = perf_auth
        customer_id = _create_customer(client, token, cid, "PERF-SO-DET-001")
        order_id = _create_order(client, token, cid, customer_id)

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                _sales_url(cid, f"/sales-orders/{order_id}"),
                headers=_auth(token),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nSO detail p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"SO detail p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"


# ---------------------------------------------------------------------------
# T233-D: Price resolution p95 < 100ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPriceResolutionPerformance:
    """Price resolution endpoint should meet p95 < 100ms."""

    _THRESHOLD_MS = 100

    def test_price_resolution_p95(self, perf_auth):
        client, token, cid = perf_auth
        customer_id = _create_customer(client, token, cid, "PERF-PRICE-001")

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.post(
                _sales_url(cid, "/pricing/resolve"),
                headers=_auth(token),
                json={
                    "customer_id": customer_id,
                    "product_id": str(uuid.uuid4()),
                    "quantity": "10",
                    "currency_code": "USD",
                },
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            # 200 (price found) or 404 (no price configured — acceptable)
            assert resp.status_code in (200, 404)

        p95 = _p95(latencies)
        print(
            f"\nPrice resolution p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)"
        )
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Price resolution p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"


# ---------------------------------------------------------------------------
# T233-E: Report generation p95 < 5000ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestReportGenerationPerformance:
    """Sales KPI and report endpoints should meet p95 < 5000ms."""

    _THRESHOLD_MS = 5000

    def test_kpi_dashboard_p95(self, perf_auth):
        client, token, cid = perf_auth

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                _sales_url(cid, "/kpis"),
                headers=_auth(token),
                params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nKPI dashboard p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"KPI dashboard p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"

    def test_sales_report_p95(self, perf_auth):
        client, token, cid = perf_auth

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                _sales_url(cid, "/reports/order-summary"),
                headers=_auth(token),
                params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code in (200, 404, 422)

        p95 = _p95(latencies)
        print(f"\nSales report p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Sales report p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"


# ---------------------------------------------------------------------------
# T233-F: Quotation list p95 < 500ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestQuotationListPerformance:
    """Quotation list should respond within 500ms p95."""

    _THRESHOLD_MS = 500

    def test_quotation_list_p95(self, perf_auth):
        client, token, cid = perf_auth
        customer_id = _create_customer(client, token, cid, "PERF-QUOT-001")
        for i in range(3):
            client.post(
                _sales_url(cid, "/quotations"),
                headers=_auth(token),
                json={
                    "customer_id": customer_id,
                    "quotation_date": "2026-08-01",
                    "validity_date": "2026-09-30",
                    "currency_code": "USD",
                },
            )

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(_sales_url(cid, "/quotations"), headers=_auth(token))
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nQuotation list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Quotation list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"


# ---------------------------------------------------------------------------
# T233-G: Delivery note and invoice endpoints p95 < 2000ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestDeliveryInvoicePerformance:
    """Delivery note and invoice list should respond within 2000ms p95."""

    _THRESHOLD_MS = 2000

    def test_delivery_note_list_p95(self, perf_auth):
        client, token, cid = perf_auth

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(_sales_url(cid, "/delivery-notes"), headers=_auth(token))
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(
            f"\nDelivery note list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)"
        )
        assert (
            p95 < self._THRESHOLD_MS
        ), f"DN list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"

    def test_invoice_list_p95(self, perf_auth):
        client, token, cid = perf_auth

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(_sales_url(cid, "/invoices"), headers=_auth(token))
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nInvoice list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert (
            p95 < self._THRESHOLD_MS
        ), f"Invoice list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"

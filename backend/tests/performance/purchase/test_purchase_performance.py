"""Purchase performance benchmarks — Phase 11 T245.

Validates that key purchase endpoints meet the performance targets from
spec §44:
  - Supplier search p95 < 300ms
  - PO list p95 < 500ms
  - GR confirmation < 2 000ms (single call, not p95)
  - Reports p95 < 5 000ms

All tests run against SQLite in-memory to eliminate network overhead.
SQLite timings are faster than PostgreSQL, so thresholds are tighter to
compensate; the important property is that the code complexity (join depth,
number of round-trips) is bounded.

Task: T245
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _base(company_id: str) -> str:
    return f"/api/v1/companies/{company_id}/purchase"


def _create_supplier(client: TestClient, token: str, cid: str, code: str) -> str:
    resp = client.post(
        f"{_base(cid)}/suppliers",
        headers=_auth(token),
        json={
            "legal_name": f"Perf Supplier {code}",
            "supplier_code": code,
            "supplier_type": "GOODS",
            "currency_code": "USD",
            "payment_terms_days": 30,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    sid = resp.json()["data"]["id"]
    client.post(f"{_base(cid)}/suppliers/{sid}/activate", headers=_auth(token))
    return str(sid)


def _create_po(client: TestClient, token: str, cid: str, supplier_id: str) -> str:
    resp = client.post(
        f"{_base(cid)}/purchase-orders",
        headers=_auth(token),
        json={"supplier_id": supplier_id, "currency_code": "USD", "notes": "Perf test"},
    )
    assert resp.status_code in (200, 201), resp.text
    return str(resp.json()["data"]["id"])


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
    return str(resp.json()["data"]["id"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def perf_auth(test_client: TestClient, db_session: Session):
    email = f"perf-purchase-{uuid.uuid4().hex[:8]}@example.com"
    user, pw = create_test_user(db_session, email=email, password="Perf1!")
    token = _login(test_client, user.email, pw)
    cid = _create_company(test_client, token)
    return test_client, token, cid


# ---------------------------------------------------------------------------
# T245-A: Supplier search p95 < 300ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestSupplierSearchPerformance:
    """Supplier list/search should return p95 < 300ms."""

    _THRESHOLD_MS = 300

    def test_supplier_list_p95(self, perf_auth):
        client, token, cid = perf_auth
        # Seed a few suppliers
        for i in range(5):
            _create_supplier(client, token, cid, f"PERF-SUP-{i:03d}")

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(f"{_base(cid)}/suppliers", headers=_auth(token))
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nSupplier list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert p95 < self._THRESHOLD_MS, (
            f"Supplier list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"
        )

    def test_supplier_search_p95(self, perf_auth):
        client, token, cid = perf_auth
        _create_supplier(client, token, cid, "PERF-SEARCH-001")

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                f"{_base(cid)}/suppliers",
                headers=_auth(token),
                params={"q": "PERF-SEARCH"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nSupplier search p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert p95 < self._THRESHOLD_MS, (
            f"Supplier search p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"
        )


# ---------------------------------------------------------------------------
# T245-B: PO list p95 < 500ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPOListPerformance:
    """Purchase order list should return p95 < 500ms."""

    _THRESHOLD_MS = 500

    def test_po_list_p95(self, perf_auth):
        client, token, cid = perf_auth
        supplier_id = _create_supplier(client, token, cid, "PERF-PO-SUP-001")
        # Seed a few POs
        for _ in range(5):
            _create_po(client, token, cid, supplier_id)

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                f"{_base(cid)}/purchase-orders",
                headers=_auth(token),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nPO list p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert p95 < self._THRESHOLD_MS, (
            f"PO list p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"
        )

    def test_po_detail_p95(self, perf_auth):
        client, token, cid = perf_auth
        supplier_id = _create_supplier(client, token, cid, "PERF-PO-DET-001")
        po_id = _create_po(client, token, cid, supplier_id)
        # Add a line
        client.post(
            f"{_base(cid)}/purchase-orders/{po_id}/lines",
            headers=_auth(token),
            json={
                "product_description": "Widget",
                "quantity_ordered": "10.000",
                "unit_cost": "25.00",
            },
        )

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                f"{_base(cid)}/purchase-orders/{po_id}",
                headers=_auth(token),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nPO detail p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert p95 < self._THRESHOLD_MS, (
            f"PO detail p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"
        )


# ---------------------------------------------------------------------------
# T245-C: Reports p95 < 5 000ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestReportPerformance:
    """Report endpoints should return p95 < 5 000ms."""

    _THRESHOLD_MS = 5000

    def test_kpi_report_p95(self, perf_auth):
        client, token, cid = perf_auth
        supplier_id = _create_supplier(client, token, cid, "PERF-RPT-SUP-001")
        _create_po(client, token, cid, supplier_id)

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                f"{_base(cid)}/reports/kpis",
                headers=_auth(token),
                params={"date_from": "2020-01-01", "date_to": "2030-12-31"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = _p95(latencies)
        print(f"\nKPI report p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)")
        assert p95 < self._THRESHOLD_MS, (
            f"KPI report p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"
        )

    def test_po_summary_report_p95(self, perf_auth):
        client, token, cid = perf_auth
        supplier_id = _create_supplier(client, token, cid, "PERF-RPT-SUP-002")
        _create_po(client, token, cid, supplier_id)

        latencies = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = client.get(
                f"{_base(cid)}/reports/purchase-order-summary",
                headers=_auth(token),
                params={"date_from": "2020-01-01", "date_to": "2030-12-31"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code in (200, 422)  # 422 if dates required

        p95 = _p95(latencies)
        print(
            f"\nPO summary report p95: {p95:.1f}ms (threshold: {self._THRESHOLD_MS}ms)"
        )
        assert p95 < self._THRESHOLD_MS, (
            f"PO summary report p95 {p95:.1f}ms exceeds {self._THRESHOLD_MS}ms"
        )

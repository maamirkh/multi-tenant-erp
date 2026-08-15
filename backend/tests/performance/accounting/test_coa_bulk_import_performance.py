"""T067 — Chart of Accounts bulk import performance benchmark.

Verifies that bulk-importing 500 accounts completes in under 30 seconds,
per plan.md Phase 2 acceptance criteria: "Bulk import 500 accounts completes
in < 30 seconds with row-level error reporting."

Unlike Inventory's 10K-row benchmark (extrapolated from a 1K sample), 500
rows is directly testable in the SQLite in-memory test environment within
this session's time budget, so no extrapolation is used here.

Spec ref: specs/008-accounting-finance/tasks.md T067
Plan ref: specs/008-accounting-finance/plan.md Phase 2 Exit Criteria
"""

from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_ROW_COUNT = 500
_TARGET_SECONDS = 30


def _url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/accounting{path}"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


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
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _make_rows(row_count: int) -> list[dict]:
    rows = []
    for i in range(row_count):
        account_type = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"][i % 5]
        rows.append(
            {
                "account_code": f"9{i:05d}",
                "account_name": f"Bulk Test Account {i}",
                "account_type": account_type,
                "is_leaf": True,
            }
        )
    return rows


class TestCOABulkImportPerformance:
    """Bulk import benchmark — 500 accounts in < 30 seconds with row-level reporting."""

    def test_500_accounts_import_under_30_seconds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"coa-bulk-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)
        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)

        rows = _make_rows(_ROW_COUNT)

        start = time.perf_counter()
        resp = test_client.post(
            _url(company_id, "/accounts/bulk-import"), headers=headers, json=rows
        )
        elapsed_seconds = time.perf_counter() - start

        assert resp.status_code == 200, resp.text
        results = resp.json()["data"]
        assert len(results) == _ROW_COUNT

        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        print(
            f"\nCOA bulk import: {_ROW_COUNT} rows in {elapsed_seconds:.2f}s "
            f"({len(successes)} succeeded, {len(failures)} failed)"
        )

        assert len(successes) == _ROW_COUNT, f"Unexpected row failures: {failures[:5]}"
        assert elapsed_seconds < _TARGET_SECONDS, (
            f"Bulk import of {_ROW_COUNT} accounts took {elapsed_seconds:.2f}s, "
            f"exceeding the {_TARGET_SECONDS}s target."
        )

    def test_row_level_error_reporting_does_not_abort_batch(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A duplicate/invalid row must not prevent the remaining rows from importing."""
        email = f"coa-bulk-err-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)
        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)

        rows = _make_rows(50)
        # Introduce 10 duplicate codes among the 50 rows.
        for i in range(10):
            rows[i]["account_code"] = rows[0]["account_code"]

        resp = test_client.post(
            _url(company_id, "/accounts/bulk-import"), headers=headers, json=rows
        )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) == 50
        failures = [r for r in results if not r["success"]]
        successes = [r for r in results if r["success"]]
        # First occurrence of the duplicated code succeeds; the other 9 fail.
        assert len(failures) == 9
        assert len(successes) == 41

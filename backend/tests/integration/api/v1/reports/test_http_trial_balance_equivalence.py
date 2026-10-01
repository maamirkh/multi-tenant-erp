"""T138 (moved from Phase 2, §0.2 item 4) — Scenario A: calling
Accounting's own ``/accounting/reports/trial-balance`` and Epic 11's
``GET /reports/accounting.trial_balance`` with identical parameters
produces byte-identical totals — the one HTTP-level cross-check; Phase
2's T058-T060 already proved adapter-level equivalence for every other
Accounting report."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.accounting.test_reports_api import _setup
from tests.integration.api.v1.reports.conftest import reports_url, setup_company


def test_trial_balance_http_totals_are_byte_identical(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    fixture = _setup(db_session, company_id)
    period_id = fixture["period"].id

    headers = {"Authorization": f"Bearer {token}"}

    accounting_resp = test_client.get(
        f"/api/v1/companies/{company_id}/accounting/reports/trial-balance",
        params={"period_id": str(period_id)},
        headers=headers,
    )
    assert accounting_resp.status_code == 200, accounting_resp.text
    accounting_data = accounting_resp.json()["data"]

    reports_resp = test_client.get(
        reports_url(company_id, "/accounting.trial_balance")
        + f"?filters[period_id]={period_id}",
        headers=headers,
    )
    assert reports_resp.status_code == 200, reports_resp.text
    reports_data = reports_resp.json()["data"]

    assert reports_data["total_debit"] == accounting_data["total_debit"]
    assert reports_data["total_credit"] == accounting_data["total_credit"]
    assert reports_data["is_balanced"] == accounting_data["is_balanced"]
    assert reports_data["is_balanced"] is True

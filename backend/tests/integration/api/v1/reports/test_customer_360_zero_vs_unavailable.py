"""T170 (FR-RPT-114/115) — zero vs. unavailable, never conflated: a
customer with zero Sales transactions gets a real ``PRESENT`` zero (Sales
has no "not configured" concept); Accounting with no Chart of Accounts
configured gets ``UNAVAILABLE(reason="not_configured")`` — the two states
are never conflated into one another.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.reports.conftest import (
    auth_header,
    create_sales_customer,
    reports_url,
    setup_company,
)


def test_zero_sales_present_unconfigured_accounting_unavailable(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    # Accounting deliberately left unconfigured (no AccountingConfiguration
    # row) — Sales carries zero transactions for this brand-new customer.
    customer = create_sales_customer(db_session, company_id)

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["sales"]["state"] == "present"
    assert data["sales"]["total_revenue"] in ("0", "0.00", 0)
    assert data["sales"]["invoice_count"] == 0

    assert data["accounting_ar"]["state"] == "unavailable"
    assert data["accounting_ar"]["reason"] == "not_configured"

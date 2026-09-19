"""T171 — Installments section Case B half (real Postgres — mirrors
``test_dashboard_installments_case_b.py``'s own requirement for
``build_active_contract_with_schedule``):

Case B (Installments disabled, but an existing obligation for this exact
customer) -> section ``PRESENT``, ``read_only_servicing_continuity=True``,
data sourced only from allow-listed ``installments.register``/
``installments.aging``-shaped data (never ``installments.dashboard``).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    create_sales_customer,
    reports_url,
    setup_company,
)


def test_case_b_disabled_with_existing_contract_section_present(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    customer = create_sales_customer(db_session, company_id)
    # Installments left disabled; the fixture itself sets up its own
    # AccountingConfiguration/fiscal year, so accounting_ar's own gate is
    # not this test's concern.
    build_active_contract_with_schedule(
        db_session, company_id=company_id, customer_id=customer.id
    )

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    section = resp.json()["data"]["installments"]
    assert section["state"] == "present"
    assert section["read_only_servicing_continuity"] is True
    assert section["contract_count"] == 1

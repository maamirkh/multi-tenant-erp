"""T171 — Installments section Case A half: disabled with no existing
obligations -> ``OMITTED(reason="not_entitled")``.

**Case B lives in ``postgres/test_customer_360_installments_case_b.py``**
— ``build_active_contract_with_schedule`` relies on Postgres-only
``server_default=text("now()")``/``gen_random_uuid()`` columns, the same
real-Postgres requirement already established for this identical fixture
in Phase 4's ``postgres/test_dashboard_installments_case_b.py`` (T153) and
Phase 2/3's ``postgres/test_installments_case_a_b_execution.py`` (T142).
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


def test_case_a_disabled_no_contracts_section_omitted(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    customer = create_sales_customer(db_session, company_id)
    # Installments left at its default-disabled state; no contract exists.

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    section = resp.json()["data"]["installments"]
    assert section["state"] == "omitted"
    assert section["reason"] == "not_entitled"

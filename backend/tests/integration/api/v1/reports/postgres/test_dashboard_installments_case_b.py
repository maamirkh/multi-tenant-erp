"""T153 — Installment Exposure widget's FR-RPT-041 exception, Case B half
(real Postgres — mirrors ``test_installments_case_a_b_execution.py``'s own
requirement for ``build_active_contract_with_schedule``):

Case B (Installments disabled, but an existing obligation) -> widget
present, ``read_only_servicing_continuity=True``, values matching
``installments.aging``/``installments.due_overdue`` exactly (sourced only
from the allow-listed report keys, never ``installments.dashboard``).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    reports_url,
    setup_company,
)


def test_case_b_disabled_with_existing_contract_widget_present(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    build_active_contract_with_schedule(db_session, company_id=company_id)

    dashboard_resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert dashboard_resp.status_code == 200, dashboard_resp.text
    widget = dashboard_resp.json()["data"]["installment_exposure"]
    assert widget["state"] == "present"
    assert widget["read_only_servicing_continuity"] is True

    aging_resp = test_client.get(
        reports_url(company_id, "/installments.aging"), headers=auth_header(token)
    )
    assert aging_resp.status_code == 200, aging_resp.text
    expected_principal = sum(
        (
            Decimal(str(row["outstanding_amount"]))
            for row in aging_resp.json()["data"]["items"]
        ),
        Decimal("0"),
    )
    assert Decimal(str(widget["outstanding_principal"])) == expected_principal

    due_overdue_resp = test_client.get(
        reports_url(company_id, "/installments.due_overdue"), headers=auth_header(token)
    )
    assert due_overdue_resp.status_code == 200, due_overdue_resp.text
    expected_overdue = sum(
        (
            Decimal(str(row["outstanding_amount"]))
            for row in due_overdue_resp.json()["data"]["items"]
            if row.get("report_type") == "overdue"
        ),
        Decimal("0"),
    )
    assert Decimal(str(widget["overdue"])) == expected_overdue

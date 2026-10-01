"""T153 — Installment Exposure widget's FR-RPT-041 exception (the only
widget with a three-way branch, T149), Case A half:

- Case A (Installments disabled, no existing contracts) -> widget omitted.

**Case B lives in ``postgres/test_dashboard_installments_case_b.py``**:
``build_active_contract_with_schedule`` relies on Postgres-only
``server_default=text("now()")``/``gen_random_uuid()`` columns
(``modules/installments/models/schedule.py``) that raise
``sqlite3.OperationalError: unknown function: now()`` against this
directory's SQLite fixtures — the exact same real-Postgres requirement
``postgres/test_installments_case_a_b_execution.py`` (T142) already
established for this identical fixture.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.reports.conftest import (
    auth_header,
    reports_url,
    setup_company,
)


def test_case_a_disabled_no_contracts_widget_omitted(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    # Installments left at its default-disabled state; no contract exists.

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    widget = resp.json()["data"]["installment_exposure"]
    assert widget["state"] == "omitted"

"""T209 — XLSX's row limit is independent of (and lower than) CSV's: a row
count between the two succeeds as CSV and is rejected as XLSX."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports import constants
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    seed_sales_invoice,
    setup_company,
)


def test_between_limits_csv_ok_xlsx_rejected(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert constants.EXPORT_ROW_LIMIT_XLSX < constants.EXPORT_ROW_LIMIT_CSV
    token, company_id = setup_company(db_session, test_client)
    for amount in ("1.00", "2.00", "3.00"):
        seed_sales_invoice(db_session, company_id, amount=amount)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", 5)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_XLSX", 2)
    headers = auth_header(token)

    csv_resp = test_client.get(
        export_url(company_id, "sales.by_customer", "csv"), headers=headers
    )
    xlsx_resp = test_client.get(
        export_url(company_id, "sales.by_customer", "xlsx"), headers=headers
    )

    assert csv_resp.status_code == 200, csv_resp.text
    assert xlsx_resp.status_code == 422, xlsx_resp.text
    assert xlsx_resp.json()["error"]["code"] == "EXPORT_TOO_LARGE"

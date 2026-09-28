"""T201 (FR-RPT-218) — the export's column set is exactly the online
report's field set: the same adapter row schema feeds both paths."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    parse_csv,
    reports_url,
    seed_sales_invoice,
    setup_company,
)


def test_export_header_equals_online_item_fields(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    seed_sales_invoice(db_session, company_id, amount="42.00", customer_id=uuid.uuid4())
    headers = auth_header(token)

    for report_key in ("sales.by_customer", "sales.summary", "sales.by_product"):
        online = test_client.get(
            reports_url(company_id, f"/{report_key}"), headers=headers
        )
        assert online.status_code == 200, online.text
        items = online.json()["data"]["items"]

        exported = test_client.get(
            export_url(company_id, report_key, "csv"), headers=headers
        )
        assert exported.status_code == 200, exported.text
        header = parse_csv(exported.content)[0]

        if items:
            assert header == list(items[0].keys()), report_key

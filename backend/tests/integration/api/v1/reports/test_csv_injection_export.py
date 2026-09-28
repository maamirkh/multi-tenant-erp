"""T203 (Scenario L, FR-RPT-216) — a formula-shaped value in exported
report data is neutralized in both CSV and XLSX; typed negative numbers
are not mangled."""

from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from tests.integration.api.v1.reports.conftest import (
    auth_header,
    create_sales_customer,
    export_url,
    parse_csv,
    seed_sales_invoice,
    setup_company,
)

_PAYLOAD = "=SUM(A1:A9)"


def _seed_malicious_customer(db_session: Session, company_id: uuid.UUID) -> None:
    customer = create_sales_customer(db_session, company_id)
    customer.legal_name = _PAYLOAD
    db_session.commit()
    seed_sales_invoice(db_session, company_id, amount="10.00", customer_id=customer.id)


def test_csv_formula_neutralized(test_client: TestClient, db_session: Session) -> None:
    token, company_id = setup_company(db_session, test_client)
    _seed_malicious_customer(db_session, company_id)

    resp = test_client.get(
        export_url(company_id, "sales.by_customer", "csv"), headers=auth_header(token)
    )

    assert resp.status_code == 200, resp.text
    rows = parse_csv(resp.content)
    name_index = rows[0].index("customer_name")
    assert rows[1][name_index] == f"'{_PAYLOAD}"
    assert not any(cell.startswith("=") for row in rows for cell in row)


def test_xlsx_formula_neutralized(test_client: TestClient, db_session: Session) -> None:
    token, company_id = setup_company(db_session, test_client)
    _seed_malicious_customer(db_session, company_id)

    resp = test_client.get(
        export_url(company_id, "sales.by_customer", "xlsx"), headers=auth_header(token)
    )

    assert resp.status_code == 200, resp.text
    sheet = load_workbook(io.BytesIO(resp.content)).active
    assert sheet is not None
    header = [c.value for c in sheet[1]]
    cell = sheet.cell(row=2, column=header.index("customer_name") + 1)
    assert cell.value == f"'{_PAYLOAD}"
    assert cell.data_type == "s"  # a literal string, never a formula ("f")

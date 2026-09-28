"""T202 (Scenario D) — the union of three online pages equals the export's
row set, value-for-value (every cell compared as its serialized text)."""

from __future__ import annotations

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

_PAGE_SIZE = 2


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def test_three_page_online_union_equals_export(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    for amount in ("11.10", "22.20", "33.30", "44.40", "55.50", "66.60"):
        seed_sales_invoice(db_session, company_id, amount=amount)
    headers = auth_header(token)
    scope = "&filters[date_from]=2026-01-01&filters[date_to]=2026-01-31"

    online_rows: list[list[str]] = []
    field_order: list[str] | None = None
    for page in (1, 2, 3):
        resp = test_client.get(
            reports_url(company_id, "/sales.by_customer")
            + f"?page={page}&page_size={_PAGE_SIZE}{scope}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        for item in resp.json()["data"]["items"]:
            field_order = field_order or list(item.keys())
            online_rows.append([_cell(item[f]) for f in field_order])
    assert len(online_rows) == 6

    exported = test_client.get(
        export_url(company_id, "sales.by_customer", "csv") + scope, headers=headers
    )
    assert exported.status_code == 200, exported.text
    rows = parse_csv(exported.content)
    assert rows[0] == field_order
    assert sorted(rows[1:]) == sorted(online_rows)
    assert "2026-01-01_2026-01-31" in exported.headers["content-disposition"]

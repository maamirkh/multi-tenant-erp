"""T199 (Scenario J) — a Category A export whose bounded count exceeds the
configured synchronous export limit is rejected with ``EXPORT_TOO_LARGE``
**before** any ``iter_export_rows()`` call (spy-verified). The limit is
lowered via ``constants`` so the test never depends on a hardcoded
production number."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.reports import constants
from modules.reports.services.adapters.sales_adapter import SalesAdapter
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    parse_csv,
    seed_sales_invoice,
    setup_company,
)


@pytest.fixture
def iter_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    original = SalesAdapter.iter_export_rows

    def spy(
        self: SalesAdapter,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        calls.append("iter")
        return original(self, db, company_id, report_key, filters, sort, batch_size)

    monkeypatch.setattr(SalesAdapter, "iter_export_rows", spy)
    return calls


def test_over_limit_category_a_rejected_before_any_row_retrieval(
    test_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    iter_spy: list[str],
) -> None:
    token, company_id = setup_company(db_session, test_client)
    for amount in ("10.00", "20.00", "30.00"):
        seed_sales_invoice(db_session, company_id, amount=amount)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", 2)

    resp = test_client.get(
        export_url(company_id, "sales.by_customer", "csv"), headers=auth_header(token)
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "EXPORT_TOO_LARGE"
    assert "content-disposition" not in resp.headers
    assert iter_spy == []


def test_at_limit_category_a_export_succeeds(
    test_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    iter_spy: list[str],
) -> None:
    token, company_id = setup_company(db_session, test_client)
    for amount in ("10.00", "20.00", "30.00"):
        seed_sales_invoice(db_session, company_id, amount=amount)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", 3)

    resp = test_client.get(
        export_url(company_id, "sales.by_customer", "csv"), headers=auth_header(token)
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-disposition"].startswith("attachment;")
    assert len(parse_csv(resp.content)) == 1 + 3
    assert iter_spy == ["iter"]

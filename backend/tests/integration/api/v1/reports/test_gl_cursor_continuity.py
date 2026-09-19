"""T139 (moved from Phase 2, §0.2 item 4) — GL online cursor-continuity
test: iterating ``GET /reports/accounting.gl`` page-by-page via
``next_cursor`` until ``has_more=False`` yields every posted journal line
exactly once across ≥3 pages."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.accounting.test_reports_api import _setup
from tests.integration.api.v1.reports.conftest import reports_url, setup_company

_PAGE_SIZE = 1


def test_gl_cursor_pagination_yields_every_line_exactly_once_across_3plus_pages(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    _setup(db_session, company_id)
    headers = {"Authorization": f"Bearer {token}"}

    seen_line_keys: list[tuple[str, str, int]] = []
    cursor: str | None = None
    pages = 0
    while True:
        url = reports_url(company_id, "/accounting.gl") + f"?page_size={_PAGE_SIZE}"
        if cursor is not None:
            url += f"&filters[cursor]={cursor}"
        resp = test_client.get(url, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        pages += 1

        for row in body["items"]:
            key = (row["posting_date"], row["journal_entry_id"], row["line_number"])
            assert key not in seen_line_keys, f"duplicate GL line across pages: {key}"
            seen_line_keys.append(key)

        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        cursor = body["next_cursor"]
        assert cursor is not None
        assert pages < 50  # safety valve against an infinite-loop regression

    assert pages >= 3
    assert len(seen_line_keys) >= 3

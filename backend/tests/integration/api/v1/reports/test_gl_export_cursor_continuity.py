"""T207 — a >100-row GL export consumes multiple native cursor pages; its
row count matches the online cursor-paginated total exactly, with no
skipped or duplicated journal line."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports import constants
from tests.integration.api.v1.accounting.test_reports_api import _setup
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    parse_csv,
    reports_url,
    setup_company,
)
from tests.integration.api.v1.reports.gl_export_support import (
    post_extra_entries,
    spy_gl_page_fetches,
)

_BATCH_SIZE = 25


def _online_gl_keys(
    test_client: TestClient, company_id: object, headers: dict[str, str]
) -> list[tuple[str, str, str]]:
    keys: list[tuple[str, str, str]] = []
    cursor: str | None = None
    for _ in range(50):
        url = reports_url(str(company_id), "/accounting.gl") + "?page_size=100"
        if cursor is not None:
            url += f"&filters[cursor]={cursor}"
        resp = test_client.get(url, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        keys.extend(
            (r["posting_date"], r["journal_entry_id"], str(r["line_number"]))
            for r in body["items"]
        )
        if not body["has_more"]:
            return keys
        cursor = body["next_cursor"]
    raise AssertionError("online GL pagination never terminated")


def test_gl_export_spans_cursor_pages_without_skip_or_duplicate(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)
    fixture = _setup(db_session, company_id)
    post_extra_entries(db_session, company_id, fixture, count=50)  # +100 lines
    headers = auth_header(token)

    online_keys = _online_gl_keys(test_client, company_id, headers)
    assert len(online_keys) > 100
    assert len(set(online_keys)) == len(online_keys)

    monkeypatch.setattr(constants, "EXPORT_BATCH_SIZE", _BATCH_SIZE)
    page_fetches = spy_gl_page_fetches(monkeypatch)
    resp = test_client.get(
        export_url(company_id, "accounting.gl", "csv"), headers=headers
    )
    assert resp.status_code == 200, resp.text

    rows = parse_csv(resp.content)
    header, data = rows[0], rows[1:]
    idx = [header.index(f) for f in ("posting_date", "journal_entry_id", "line_number")]
    export_keys = [(r[idx[0]], r[idx[1]], r[idx[2]]) for r in data]

    assert len(export_keys) == len(online_keys)
    assert len(set(export_keys)) == len(export_keys)
    assert set(export_keys) == set(online_keys)
    assert len(page_fetches) > 1
    assert all(limit == _BATCH_SIZE for limit in page_fetches)

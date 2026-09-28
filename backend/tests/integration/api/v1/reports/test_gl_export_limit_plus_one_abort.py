"""T208 (§0.2 item 16) — GL export's limit+1 strategy: a scope with exactly
``limit`` rows succeeds; ``limit+1`` rows is rejected with
``EXPORT_TOO_LARGE``; no cursor page beyond the one containing the
``limit+1``th row is ever requested; no file and no audit row on rejection.

``_setup`` posts 3 journal entries = 6 GL lines; batch size 2 → 3 pages."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports import constants
from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from tests.integration.api.v1.accounting.test_reports_api import _setup
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    parse_csv,
    setup_company,
)
from tests.integration.api.v1.reports.gl_export_support import spy_gl_page_fetches

_GL_LINES = 6
_BATCH_SIZE = 2


def test_gl_export_exactly_at_limit_succeeds(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)
    _setup(db_session, company_id)
    monkeypatch.setattr(constants, "EXPORT_BATCH_SIZE", _BATCH_SIZE)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", _GL_LINES)

    resp = test_client.get(
        export_url(company_id, "accounting.gl", "csv"), headers=auth_header(token)
    )

    assert resp.status_code == 200, resp.text
    assert len(parse_csv(resp.content)) == 1 + _GL_LINES


def test_gl_export_limit_plus_one_aborts_without_fetching_further_pages(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)
    _setup(db_session, company_id)
    limit = 3  # the 4th (limit+1th) row lives on cursor page 2 of 3
    monkeypatch.setattr(constants, "EXPORT_BATCH_SIZE", _BATCH_SIZE)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", limit)
    page_fetches = spy_gl_page_fetches(monkeypatch)

    resp = test_client.get(
        export_url(company_id, "accounting.gl", "csv"), headers=auth_header(token)
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "EXPORT_TOO_LARGE"
    assert "content-disposition" not in resp.headers
    pages_containing_limit_plus_one = -(-(limit + 1) // _BATCH_SIZE)
    assert len(page_fetches) == pages_containing_limit_plus_one == 2
    assert ReportsAuditRepository(db_session).list_for_company(company_id) == []

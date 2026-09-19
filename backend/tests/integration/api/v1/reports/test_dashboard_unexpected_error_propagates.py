"""T156 — the non-contradictory counterpart of T155: an adapter mock
raising a genuinely unexpected exception (not ``UnavailablePrerequisiteError``)
causes the *whole* request to fail with a 5xx — proving the dashboard
composition never silently swallows a real defect into any widget state.
``ExecutiveDashboardService.get()`` never uses a bare ``except Exception``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import modules.reports.services.dashboard_service as dashboard_service_module
from modules.reports.schemas.dashboard import OperationalInventoryValueWidget
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    reports_url,
    setup_company,
)


def test_unexpected_exception_fails_whole_request(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)

    def _raise_unexpected(
        *_args: object, **_kwargs: object
    ) -> OperationalInventoryValueWidget:
        raise ConnectionError("mocked genuinely unexpected failure")

    monkeypatch.setattr(
        dashboard_service_module, "_inventory_widget", _raise_unexpected
    )

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code >= 500, resp.text

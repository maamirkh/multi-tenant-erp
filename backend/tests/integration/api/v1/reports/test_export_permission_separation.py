"""T204 (FR-RPT-212) — ``.view`` and ``.export`` are separate codes: a user
holding only ``reports.sales.view`` can run the report online but is
denied its export, and no audit row is written for the denial."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    grant_reports_permissions,
    reports_url,
    seed_sales_invoice,
    setup_company_with_user,
)


def test_view_only_user_denied_export(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id, user_id = setup_company_with_user(db_session, test_client)
    grant_reports_permissions(db_session, company_id, user_id, {"reports.sales.view"})
    seed_sales_invoice(db_session, company_id, amount="10.00")
    headers = auth_header(token)

    online = test_client.get(
        reports_url(company_id, "/sales.by_customer"), headers=headers
    )
    assert online.status_code == 200, online.text

    exported = test_client.get(
        export_url(company_id, "sales.by_customer", "csv"), headers=headers
    )
    assert exported.status_code == 403, exported.text
    error = exported.json()["error"]
    assert error["code"] == "REPORT_PERMISSION_DENIED"
    assert error["details"]["permission_code"] == "reports.sales.export"
    assert ReportsAuditRepository(db_session).list_for_company(company_id) == []


def test_export_only_user_denied_view_but_allowed_export(
    test_client: TestClient, db_session: Session
) -> None:
    """The reverse direction — no implicit grant either way."""
    token, company_id, user_id = setup_company_with_user(db_session, test_client)
    grant_reports_permissions(db_session, company_id, user_id, {"reports.sales.export"})
    headers = auth_header(token)

    online = test_client.get(
        reports_url(company_id, "/sales.by_customer"), headers=headers
    )
    assert online.status_code == 403, online.text

    exported = test_client.get(
        export_url(company_id, "sales.by_customer", "csv"), headers=headers
    )
    assert exported.status_code == 200, exported.text

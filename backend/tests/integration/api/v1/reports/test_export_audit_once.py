"""T205 (SC-005) — exactly one correctly-attributed audit row per
successful export; none for a rejected one."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports import constants
from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    seed_sales_invoice,
    setup_company_with_user,
)


def test_one_audit_row_per_successful_export(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id, user_id = setup_company_with_user(db_session, test_client)
    seed_sales_invoice(db_session, company_id, amount="10.00")
    seed_sales_invoice(db_session, company_id, amount="20.00")
    headers = auth_header(token)
    scope = "&filters[date_from]=2026-01-01"

    ok = test_client.get(
        export_url(company_id, "sales.by_customer", "xlsx") + scope, headers=headers
    )
    assert ok.status_code == 200, ok.text

    rows = ReportsAuditRepository(db_session).list_for_company(
        company_id, "ReportExport"
    )
    assert len(rows) == 1
    audit = rows[0]
    assert audit.action == "EXPORTED"
    assert audit.actor_id == user_id
    assert audit.company_id == company_id
    assert audit.report_key == "sales.by_customer"
    assert audit.format == "XLSX"
    assert audit.row_count == 2
    assert isinstance(audit.filter_scope, dict)
    assert audit.filter_scope["date_from"] == "2026-01-01"

    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_XLSX", 1)
    rejected = test_client.get(
        export_url(company_id, "sales.by_customer", "xlsx") + scope, headers=headers
    )
    assert rejected.status_code == 422, rejected.text
    assert (
        len(
            ReportsAuditRepository(db_session).list_for_company(
                company_id, "ReportExport"
            )
        )
        == 1
    )

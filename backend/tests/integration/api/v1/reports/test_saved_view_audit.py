"""T185 — saved-view create/update/delete each produce exactly one
correctly-attributed ``ReportsAuditLog`` row, committed in the same
transaction as the persistence write (T184)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    reports_url,
    setup_company_with_user,
)


def test_create_update_delete_each_audited_once(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id, user_id = setup_company_with_user(db_session, test_client)
    headers = auth_header(token)

    created = test_client.post(
        reports_url(company_id, "/saved-views"),
        json={
            "report_key": "sales.summary",
            "name": "January",
            "filter_config": {"date_from": "2026-01-01"},
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    view_id = uuid.UUID(created.json()["data"]["id"])

    updated = test_client.patch(
        reports_url(company_id, f"/saved-views/{view_id}"),
        json={"name": "January (renamed)"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text

    deleted = test_client.delete(
        reports_url(company_id, f"/saved-views/{view_id}"), headers=headers
    )
    assert deleted.status_code == 200, deleted.text

    rows = ReportsAuditRepository(db_session).list_for_company(
        company_id, "SavedReportView"
    )
    assert [r.action for r in rows] == ["CREATED", "UPDATED", "DELETED"]
    for row in rows:
        assert row.entity_id == view_id
        assert row.actor_id == user_id
        assert row.company_id == company_id
        assert row.report_key == "sales.summary"
        assert row.format is None
        assert row.row_count is None

    create_row, update_row, delete_row = rows
    assert create_row.before is None
    assert isinstance(create_row.after, dict)
    assert create_row.after["name"] == "January"
    assert isinstance(update_row.before, dict) and isinstance(update_row.after, dict)
    assert update_row.before["name"] == "January"
    assert update_row.after["name"] == "January (renamed)"
    assert isinstance(delete_row.before, dict)
    assert delete_row.before["name"] == "January (renamed)"
    assert delete_row.after is None


def test_rejected_mutation_writes_no_audit_row(
    test_client: TestClient, db_session: Session
) -> None:
    """A failed validation / not-found never leaves an orphan audit row."""
    token, company_id, _user_id = setup_company_with_user(db_session, test_client)
    headers = auth_header(token)

    invalid = test_client.post(
        reports_url(company_id, "/saved-views"),
        json={
            "report_key": "sales.summary",
            "name": "Bad",
            "filter_config": {"not_a_field": 1},
        },
        headers=headers,
    )
    assert invalid.status_code == 422, invalid.text
    missing = test_client.delete(
        reports_url(company_id, f"/saved-views/{uuid.uuid4()}"), headers=headers
    )
    assert missing.status_code == 404, missing.text

    assert ReportsAuditRepository(db_session).list_for_company(company_id) == []

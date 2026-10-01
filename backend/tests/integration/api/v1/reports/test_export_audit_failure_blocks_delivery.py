"""T206 — the single most important Phase 6 test (§21.8): if the export's
audit record cannot be durably committed, the export is **not** delivered
— ``500 EXPORT_AUDIT_FAILED``, no file bytes, no attachment header, and
zero ``ReportsAuditLog`` rows afterward."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    seed_sales_invoice,
    setup_company,
)


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_audit_commit_failure_blocks_file_delivery(
    test_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
) -> None:
    token, company_id = setup_company(db_session, test_client)
    seed_sales_invoice(db_session, company_id, amount="99.00")
    commit_attempts: list[str] = []

    def failing_commit() -> None:
        commit_attempts.append("commit")
        raise OperationalError("COMMIT", {}, Exception("simulated outage"))

    # Setup is complete — from here on, the export's audit commit is the
    # only commit the request performs.
    monkeypatch.setattr(db_session, "commit", failing_commit)
    resp = test_client.get(
        export_url(company_id, "sales.by_customer", fmt), headers=auth_header(token)
    )
    monkeypatch.undo()

    assert commit_attempts == ["commit"]
    assert resp.status_code == 500, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    assert "content-disposition" not in resp.headers
    assert resp.json()["error"]["code"] == "EXPORT_AUDIT_FAILED"
    assert "99.00" not in resp.text
    assert ReportsAuditRepository(db_session).list_for_company(company_id) == []

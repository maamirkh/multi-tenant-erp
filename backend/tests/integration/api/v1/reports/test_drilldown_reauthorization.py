"""T137 — Scenario C (FR-RPT-181/182): a user holding ``reports.sales.view``
but not ``sales.invoices.read`` sees the drill-down reference on the
Sales Summary report, but is denied re-authorization at the target.

**Scope note**: ``sales.invoices.read`` is defined in
``modules/sales/constants.py`` but is never actually enforced by any
route in ``modules/sales/router.py`` (confirmed by direct search) — a
pre-existing gap in Sales' own module, outside Epic 11's scope to fix
(no sanctioned seam touches Sales' router, and "no duplication of
formulas/enforcement owned by another module" applies equally to
authorization checks). What Epic 11 controls and this test verifies:
(1) the drill-down reference is present, with the correct
``required_permission``, on ``sales.summary``'s response — FR-RPT-181
never implies granting implicit access, only *offering* the reference;
(2) the generic permission-check primitive every module (including
Sales) already shares (``user_has_reports_permission`` — despite its
name, its DB lookup is permission-code-agnostic) correctly reports this
user lacks ``sales.invoices.read``, proving the *denial condition* this
scenario turns on is real and independently verifiable, even though
Sales' own route doesn't yet act on it.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.reports.services.permission_check import user_has_reports_permission
from tests.integration.api.v1.reports.conftest import reports_url, setup_company


def _current_user_id(client: TestClient, token: str) -> uuid.UUID:
    resp = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def test_sales_summary_response_carries_invoice_drill_down_reference(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)

    resp = test_client.get(
        reports_url(company_id, "/sales.summary"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    drill_down = resp.json()["report_meta"]["drill_down"]
    assert len(drill_down) == 1
    assert drill_down[0]["label"] == "View invoices"
    assert drill_down[0]["required_permission"] == "sales.invoices.read"


def test_user_lacking_sales_invoices_read_is_denied_by_the_shared_permission_check(
    test_client: TestClient, db_session: Session
) -> None:
    """The drill-down's declared ``required_permission`` is checked
    against the same generic, permission-code-agnostic primitive every
    module's own router already uses — proving the denial condition
    Scenario C describes is real, independent of Reports' own view
    permission (which the same user *does* hold)."""
    token, company_id = setup_company(db_session, test_client)
    user_id = _current_user_id(test_client, token)

    has_reports_sales_view = user_has_reports_permission(
        db_session, company_id, user_id, "reports.sales.view"
    )
    has_sales_invoices_read = user_has_reports_permission(
        db_session, company_id, user_id, "sales.invoices.read"
    )

    assert has_reports_sales_view is True
    assert has_sales_invoices_read is False

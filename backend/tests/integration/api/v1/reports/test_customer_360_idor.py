"""T167 — Scenario F: Tenant B's user requesting Tenant A's ``customer_id``
gets the identical not-found a nonexistent ID would (IDOR-safe, FR-RPT-271)
— Sales' own ``CustomerService.get_by_id()`` already tenant-scopes the
lookup, so the platform's standard ``NotFoundException`` (404, code
``NOT_FOUND``) propagates uncaught, with zero Reports-owned translation."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.reports.conftest import (
    auth_header,
    create_sales_customer,
    reports_url,
    setup_company,
)


def test_cross_tenant_and_nonexistent_customer_id_are_indistinguishable(
    test_client: TestClient, db_session: Session
) -> None:
    _token_a, company_a = setup_company(db_session, test_client)
    customer_a = create_sales_customer(db_session, company_a)

    token_b, company_b = setup_company(db_session, test_client)

    cross_tenant_resp = test_client.get(
        reports_url(company_b, f"/customer-360/{customer_a.id}"),
        headers=auth_header(token_b),
    )
    nonexistent_resp = test_client.get(
        reports_url(company_b, f"/customer-360/{uuid.uuid4()}"),
        headers=auth_header(token_b),
    )

    assert cross_tenant_resp.status_code == 404, cross_tenant_resp.text
    assert nonexistent_resp.status_code == 404, nonexistent_resp.text
    assert (
        cross_tenant_resp.json()["error"]["code"]
        == nonexistent_resp.json()["error"]["code"]
        == "NOT_FOUND"
    )

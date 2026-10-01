"""T172 (FR-RPT-262) — Customer 360 checks tenant scope independently per
section (each domain call is itself tenant-scoped) rather than relying on
the customer-lookup step alone. This test mocks one section's underlying
call to simulate a tenant-check failure (returning a fabricated value that
does not belong to this company) and proves the other three sections are
computed completely independently — the mocked corruption never leaks
into, or otherwise affects, any other section's result.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.services.aging_calculator import AgingRow
from modules.accounting.services.ar_service import AccountsReceivableService
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    configure_accounting_minimal,
    create_sales_customer,
    reports_url,
    setup_company,
)


def test_mocked_accounting_tenant_failure_does_not_affect_other_sections(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)
    customer = create_sales_customer(db_session, company_id)

    fabricated_row = AgingRow(
        customer_ledger_id=None,
        customer_id=None,
        current=Decimal("999999"),
    )

    def _mocked_get_customer_aging(
        self: AccountsReceivableService,
        company_id: object,
        customer_id: object,
        as_of_date: object,
    ) -> AgingRow:
        # Simulates a broken tenant scope: returns a fixed row regardless
        # of which company/customer was actually requested.
        return fabricated_row

    monkeypatch.setattr(
        AccountsReceivableService, "get_customer_aging", _mocked_get_customer_aging
    )

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # The mock took effect for Accounting...
    assert data["accounting_ar"]["state"] == "present"
    assert Decimal(str(data["accounting_ar"]["balance"])) == Decimal("999999")

    # ...but every other, independently-evaluated section is completely
    # unaffected — still the real, correctly company-scoped zero state for
    # a brand-new customer.
    assert data["sales"]["state"] == "present"
    assert data["sales"]["invoice_count"] == 0
    assert data["crm"]["state"] == "omitted"
    assert data["crm"]["reason"] == "not_entitled"
    assert data["installments"]["state"] == "omitted"
    assert data["installments"]["reason"] == "not_entitled"

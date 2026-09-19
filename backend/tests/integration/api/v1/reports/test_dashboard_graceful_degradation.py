"""T152 — Scenario B: Executive dashboard graceful degradation.

Given a tenant with CRM disabled, when an authorized user loads the
Executive Dashboard, every widget except the CRM Pipeline widget renders
correctly, and the CRM widget is simply omitted from the response
(FR-RPT-041, FR-RPT-044) — no error state, no reason field.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    configure_accounting_minimal,
    reports_url,
    setup_company,
)


def test_crm_disabled_dashboard_omits_only_crm_widget(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db_session)
    ).enable(company_id)
    db_session.commit()

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["crm_pipeline"]["state"] == "omitted"
    assert "reason" not in data["crm_pipeline"]

    for widget_key in (
        "net_sales",
        "gross_sales",
        "purchase_spend",
        "ar",
        "ap",
        "cash_position",
        "operational_inventory_value",
        "installment_exposure",
        "gross_profit_margin",
    ):
        assert data[widget_key]["state"] == "present", (
            f"{widget_key} expected present, got {data[widget_key]['state']}"
        )

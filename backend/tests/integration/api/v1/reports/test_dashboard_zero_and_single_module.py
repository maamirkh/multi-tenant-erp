"""T154 (FR-RPT-044) — the Executive Dashboard MUST behave correctly for a
company with zero data in every module (every entitled widget renders a
defined state, never an error) and for a company with only one optional
module enabled (only that module's widget renders; the other optional
module stays omitted).

Sales/Purchase/Inventory/Accounting are the platform's "core, always-on"
domains (conftest.py's own documented convention) — only CRM/Installments
are independently toggle-gated, so "single module enabled" is exercised
across that pair.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    reports_url,
    setup_company,
)

_ALL_WIDGET_KEYS = (
    "net_sales",
    "gross_sales",
    "purchase_spend",
    "ar",
    "ap",
    "cash_position",
    "operational_inventory_value",
    "crm_pipeline",
    "installment_exposure",
    "gross_profit_margin",
)


def test_zero_data_company_every_widget_has_a_defined_state(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    for widget_key in _ALL_WIDGET_KEYS:
        assert data[widget_key]["state"] in ("present", "omitted", "unavailable")
    # Sales/Purchase are always-entitled core domains with zero transactions
    # — a defined zero, never an error.
    assert data["net_sales"]["state"] == "present"
    assert data["net_sales"]["value"] in ("0", "0.000000", 0)
    assert data["gross_sales"]["state"] == "present"
    assert data["purchase_spend"]["state"] == "present"


def test_only_crm_enabled_crm_present_installments_omitted(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    CrmFeatureFlagService(
        db=db_session,
        flag_repo=CrmFeatureFlagRepository(db_session),
        provisioning_service=None,
    ).enable(company_id)
    db_session.commit()

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["crm_pipeline"]["state"] == "present"
    assert data["installment_exposure"]["state"] == "omitted"

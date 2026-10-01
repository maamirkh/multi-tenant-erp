"""T158 — ``?period=this_month&compare=previous_period`` populates each
comparison-capable widget's ``comparison`` field via
``comparison_service.compute_comparison`` (T024), calling the same
adapter method twice (current + comparison period).

Three widgets are a documented, structural exception (dashboard_service.py
module docstring): CRM Pipeline (``crm.dashboard`` has no period
parameter — always "current calendar month"), Operational Inventory Value
(``inventory.valuation`` has no as-of parameter — always "right now"), and
Installment Exposure (``installments.due_overdue`` has no as-of parameter
— always "as of today"). Their ``comparison`` stays ``None`` even when
``compare`` is requested and the widget itself is ``present``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    configure_accounting_minimal,
    reports_url,
    setup_company,
)

_COMPARABLE_WIDGETS = (
    "net_sales",
    "gross_sales",
    "purchase_spend",
    "ar",
    "ap",
    "cash_position",
    "gross_profit_margin",
)
_STRUCTURALLY_NON_COMPARABLE_WIDGETS = (
    "crm_pipeline",
    "operational_inventory_value",
    "installment_exposure",
)


def test_comparison_populates_every_comparable_widget(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)
    CrmFeatureFlagService(
        db=db_session,
        flag_repo=CrmFeatureFlagRepository(db_session),
        provisioning_service=None,
    ).enable(company_id)
    db_session.commit()

    resp = test_client.get(
        reports_url(company_id, "/dashboard"),
        params={"period": "this_month", "compare": "previous_period"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    for widget_key in _COMPARABLE_WIDGETS:
        widget = data[widget_key]
        assert widget["state"] == "present", widget_key
        assert widget["comparison"] is not None, widget_key
        assert widget["comparison"]["comparability"] in (
            "full",
            "not_comparable",
            "partial_current_period",
        )

    for widget_key in _STRUCTURALLY_NON_COMPARABLE_WIDGETS:
        assert data[widget_key]["comparison"] is None, widget_key


def test_no_compare_param_every_comparison_is_null(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    for widget_key in _COMPARABLE_WIDGETS + _STRUCTURALLY_NON_COMPARABLE_WIDGETS:
        assert data[widget_key]["comparison"] is None, widget_key

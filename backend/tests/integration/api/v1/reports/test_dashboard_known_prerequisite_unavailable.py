"""T155 — an adapter mock raising ``UnavailablePrerequisiteError`` for
exactly one widget results in that widget ``UNAVAILABLE``, response still
``200``, the other 9 widgets render normally (§0.2 item 8's corrected,
non-contradictory partial-failure rule)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import modules.reports.services.dashboard_service as dashboard_service_module
from modules.reports.exceptions import UnavailablePrerequisiteError
from modules.reports.schemas.dashboard import (
    OperationalInventoryValueWidget,
    WidgetState,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    configure_accounting_minimal,
    reports_url,
    setup_company,
)


def test_one_widget_unavailable_others_render_normally(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)

    def _raise_unavailable(
        *_args: object, **_kwargs: object
    ) -> OperationalInventoryValueWidget:
        raise UnavailablePrerequisiteError(
            "inventory.valuation", "mocked prerequisite gap"
        )

    monkeypatch.setattr(
        dashboard_service_module, "_inventory_widget", _raise_unavailable
    )

    resp = test_client.get(
        reports_url(company_id, "/dashboard"), headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["operational_inventory_value"]["state"] == WidgetState.UNAVAILABLE.value

    for widget_key in (
        "net_sales",
        "gross_sales",
        "purchase_spend",
        "ar",
        "ap",
        "cash_position",
        "gross_profit_margin",
    ):
        assert data[widget_key]["state"] == "present", widget_key

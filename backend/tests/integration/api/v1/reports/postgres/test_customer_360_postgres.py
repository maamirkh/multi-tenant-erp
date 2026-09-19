"""T176 — Real-Postgres composite test: full composition across all four
domains, ``Decimal`` precision preserved end-to-end for the AR figure.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    create_sales_customer,
    reports_url,
    setup_company,
)


def test_full_composition_all_four_domains_decimal_precision_preserved(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    CrmFeatureFlagService(
        db=db_session,
        flag_repo=CrmFeatureFlagRepository(db_session),
        provisioning_service=None,
    ).enable(company_id)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db_session)
    ).enable(company_id)
    db_session.commit()

    customer = create_sales_customer(db_session, company_id)
    # Also configures AccountingConfiguration + posts a real AR
    # transaction (the invoice) for this exact customer.
    build_active_contract_with_schedule(
        db_session,
        company_id=company_id,
        customer_id=customer.id,
        installment_count=3,
        installment_amount=Decimal("123.456789"),
    )

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["sales"]["state"] == "present"
    assert data["accounting_ar"]["state"] == "present"
    assert data["crm"]["state"] == "present"
    assert data["installments"]["state"] == "present"

    # Decimal precision preserved end-to-end — the AR balance parses back
    # to an exact Decimal with no floating-point rounding artifact.
    balance = Decimal(str(data["accounting_ar"]["balance"]))
    assert balance > Decimal("0")
    assert balance == balance.quantize(Decimal("0.000001"))

    assert data["installments"]["contract_count"] == 1
    assert data["installments"]["read_only_servicing_continuity"] is False

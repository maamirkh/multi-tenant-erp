"""Phase 9 correction (found by T259's real-browser check) — discovery
applies the same Installments servicing-continuity rule as execution:

- fully entitled → all 7 Installments keys discoverable;
- Case A (disabled, no contracts) → none;
- Case B (disabled, existing contract) → exactly the 5 allow-listed keys,
  and that set is identical to what ``GET /reports/{key}`` actually serves
  (T142) — ``plan_performance``/``dashboard`` stay hidden.

Real Postgres: ``build_active_contract_with_schedule`` needs Postgres-only
server defaults (same requirement as T142/T153).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.reports.conftest import reports_url, setup_company

_ALL_7 = {
    "installments.register",
    "installments.collections",
    "installments.due_overdue",
    "installments.aging",
    "installments.settlement_writeoff",
    "installments.plan_performance",
    "installments.dashboard",
}
_ALLOWLISTED_5 = _ALL_7 - {"installments.plan_performance", "installments.dashboard"}


def _discovered_installments(
    client: TestClient, company_id: uuid.UUID, headers: dict[str, str]
) -> set[str]:
    resp = client.get(reports_url(company_id, "/discovery"), headers=headers)
    assert resp.status_code == 200, resp.text
    return {
        r["key"]
        for r in resp.json()["data"]["reports"]
        if r["domain"] == "installments"
    }


def test_fully_entitled_discovers_all_7(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db_session)
    ).enable(company_id)
    db_session.commit()
    headers = {"Authorization": f"Bearer {token}"}

    assert _discovered_installments(test_client, company_id, headers) == _ALL_7


def test_case_a_discovers_none(test_client: TestClient, db_session: Session) -> None:
    token, company_id = setup_company(db_session, test_client)
    headers = {"Authorization": f"Bearer {token}"}

    assert _discovered_installments(test_client, company_id, headers) == set()


def test_case_b_discovers_exactly_the_servable_allowlist(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    build_active_contract_with_schedule(db_session, company_id=company_id)
    headers = {"Authorization": f"Bearer {token}"}

    discovered = _discovered_installments(test_client, company_id, headers)
    assert discovered == _ALLOWLISTED_5

    # Discovery and execution agree key-for-key (T142's contract).
    servable = {
        key
        for key in _ALL_7
        if test_client.get(
            reports_url(company_id, f"/{key}"), headers=headers
        ).status_code
        == 200
    }
    assert discovered == servable

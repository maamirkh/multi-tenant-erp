"""T142 (moved from Phase 2, §0.2 item 3) — Real-Postgres Installments
Case A/B integration test (Scenarios H/M):

- Fully entitled -> all 7 keys 200.
- Case A (disabled, no existing contracts) -> all 7 keys
  ``REPORT_NOT_ENTITLED``.
- Case B (disabled, existing contract) -> exactly the 5 allow-listed keys
  200 with ``read_only_servicing_continuity: true`` in ``report_meta``,
  while ``plan_performance``/``dashboard`` return the identical
  ``REPORT_NOT_ENTITLED`` Case A would.
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
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.reports.conftest import reports_url, setup_company

_ALL_7_KEYS = (
    "installments.register",
    "installments.collections",
    "installments.due_overdue",
    "installments.aging",
    "installments.settlement_writeoff",
    "installments.plan_performance",
    "installments.dashboard",
)
_ALLOWLISTED_5 = frozenset(
    {
        "installments.register",
        "installments.collections",
        "installments.due_overdue",
        "installments.aging",
        "installments.settlement_writeoff",
    }
)


def test_fully_entitled_all_7_keys_return_200(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db_session)
    ).enable(company_id)
    db_session.commit()
    build_active_contract_with_schedule(db_session, company_id=company_id)

    headers = {"Authorization": f"Bearer {token}"}
    for key in _ALL_7_KEYS:
        resp = test_client.get(reports_url(company_id, f"/{key}"), headers=headers)
        assert resp.status_code == 200, f"{key}: {resp.text}"
        assert resp.json()["report_meta"]["read_only_servicing_continuity"] is False


def test_case_a_disabled_no_contracts_all_7_keys_denied(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    # Installments left at its default-disabled state; no contract exists.

    headers = {"Authorization": f"Bearer {token}"}
    for key in _ALL_7_KEYS:
        resp = test_client.get(reports_url(company_id, f"/{key}"), headers=headers)
        assert resp.status_code == 403, f"{key}: {resp.text}"
        assert resp.json()["error"]["code"] == "REPORT_NOT_ENTITLED"


def test_case_b_disabled_with_existing_contract_allowlist_only(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    # Installments left disabled, but a real contract already exists.
    build_active_contract_with_schedule(db_session, company_id=company_id)

    headers = {"Authorization": f"Bearer {token}"}
    for key in _ALL_7_KEYS:
        resp = test_client.get(reports_url(company_id, f"/{key}"), headers=headers)
        if key in _ALLOWLISTED_5:
            assert resp.status_code == 200, f"{key}: {resp.text}"
            assert (
                resp.json()["report_meta"]["read_only_servicing_continuity"] is True
            ), key
        else:
            assert resp.status_code == 403, f"{key}: {resp.text}"
            assert resp.json()["error"]["code"] == "REPORT_NOT_ENTITLED"

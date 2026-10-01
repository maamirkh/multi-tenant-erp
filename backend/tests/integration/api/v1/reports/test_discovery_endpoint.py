"""T131 — Integration test for ``GET /reports/discovery``: a user missing
``reports.crm.view`` (or with CRM disabled) never sees ``crm.*``; the
visible set is exactly the entitled/permitted subset of the real 43
``NOW`` keys, never any ``DEFERRED`` key.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.registry.definitions import REPORT_REGISTRY, ReportStatus
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.integration.api.v1.reports.conftest import reports_url, setup_company

_DEFERRED_KEYS = {
    d.key for d in REPORT_REGISTRY.values() if d.status is ReportStatus.DEFERRED
}
_ALL_NOW_KEYS = {
    d.key for d in REPORT_REGISTRY.values() if d.status is ReportStatus.NOW
}


def test_owner_discovers_every_now_key_never_a_deferred_one(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)

    resp = test_client.get(
        reports_url(company_id, "/discovery"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    keys = {item["key"] for item in resp.json()["data"]["reports"]}

    assert keys.issubset(_ALL_NOW_KEYS)
    assert not (keys & _DEFERRED_KEYS)
    # Every core domain (sales/purchase/inventory/accounting) defaults
    # entitled with no subscription, and setup_company() explicitly
    # granted every reports.* permission code — so every non-CRM/
    # Installments NOW key should be visible (CRM/Installments both
    # default their OWN module toggle to disabled).
    non_gated_keys = {
        d.key
        for d in REPORT_REGISTRY.values()
        if d.status is ReportStatus.NOW
        and d.domain_capability_key not in ("crm", "installments")
    }
    assert non_gated_keys.issubset(keys)


def test_missing_crm_permission_hides_all_crm_keys(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)

    user_id = _current_user_id(test_client, token)
    member = CompanyMemberRepository(db_session).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    role_permission_repo = RolePermissionRepository(db_session)
    current = role_permission_repo.get_permission_codes_for_role(member.role_id)
    role_permission_repo.bulk_set_permissions_for_role(
        member.role_id, current - {"reports.crm.view"}
    )
    db_session.commit()

    resp = test_client.get(
        reports_url(company_id, "/discovery"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    keys = {item["key"] for item in resp.json()["data"]["reports"]}

    crm_keys = {
        d.key for d in REPORT_REGISTRY.values() if d.domain_capability_key == "crm"
    }
    assert not (keys & crm_keys)


def _current_user_id(client: TestClient, token: str) -> uuid.UUID:
    resp = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])

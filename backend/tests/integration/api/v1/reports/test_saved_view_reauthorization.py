"""T141 — Scenario E (FR-RPT-203): a saved view referencing
``reports.accounting.view``, after the role change removing it, fails to
load with ``REPORT_PERMISSION_DENIED``."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.integration.api.v1.reports.conftest import reports_url, setup_company


def _current_user_id(client: TestClient, token: str) -> uuid.UUID:
    resp = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def test_saved_view_load_denied_after_permission_removed(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = test_client.post(
        reports_url(company_id, "/saved-views"),
        json={
            "report_key": "accounting.gl",
            "name": "My GL View",
            "filter_config": {},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    view_id = create_resp.json()["data"]["id"]

    # Loads fine right after saving — permission still held.
    load_resp = test_client.get(
        reports_url(company_id, f"/saved-views/{view_id}"), headers=headers
    )
    assert load_resp.status_code == 200, load_resp.text

    # Role change: remove reports.accounting.view.
    user_id = _current_user_id(test_client, token)
    member = CompanyMemberRepository(db_session).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    role_permission_repo = RolePermissionRepository(db_session)
    current = role_permission_repo.get_permission_codes_for_role(member.role_id)
    role_permission_repo.bulk_set_permissions_for_role(
        member.role_id, current - {"reports.accounting.view"}
    )
    db_session.commit()

    denied_resp = test_client.get(
        reports_url(company_id, f"/saved-views/{view_id}"), headers=headers
    )
    assert denied_resp.status_code == 403, denied_resp.text
    assert denied_resp.json()["error"]["code"] == "REPORT_PERMISSION_DENIED"

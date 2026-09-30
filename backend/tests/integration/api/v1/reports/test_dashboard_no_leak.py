"""T157 — a user missing ``reports.crm.view`` vs. CRM disabled entirely
both produce an absent CRM widget with zero distinguishing signal
(FR-RPT-041's leak-prevention philosophy, mirrored from the discovery
endpoint's own precedent, T131)."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    reports_url,
    setup_company,
)


def _revoke_permission(
    db: Session, company_id: UUID, user_id: UUID, permission_code: str
) -> None:
    member = CompanyMemberRepository(db).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    repo = RolePermissionRepository(db)
    current = repo.get_permission_codes_for_role(member.role_id)
    repo.bulk_set_permissions_for_role(member.role_id, current - {permission_code})
    db.commit()


def test_missing_permission_and_disabled_module_produce_identical_crm_widget(
    test_client: TestClient, db_session: Session
) -> None:
    # Case 1: CRM enabled, but the user lacks reports.crm.view.
    token_a, company_a = setup_company(db_session, test_client)
    CrmFeatureFlagService(
        db=db_session,
        flag_repo=CrmFeatureFlagRepository(db_session),
        provisioning_service=None,
    ).enable(company_a)
    db_session.commit()

    members_a, _total_a = CompanyMemberRepository(db_session).list_by_company(company_a)
    owner_a = members_a[0]
    _revoke_permission(db_session, company_a, owner_a.user_id, "reports.crm.view")

    resp_a = test_client.get(
        reports_url(company_a, "/dashboard"), headers=auth_header(token_a)
    )
    assert resp_a.status_code == 200, resp_a.text
    widget_a = resp_a.json()["data"]["crm_pipeline"]

    # Case 2: CRM disabled entirely, user retains every reports.* permission.
    token_b, company_b = setup_company(db_session, test_client)

    resp_b = test_client.get(
        reports_url(company_b, "/dashboard"), headers=auth_header(token_b)
    )
    assert resp_b.status_code == 200, resp_b.text
    widget_b = resp_b.json()["data"]["crm_pipeline"]

    assert (
        widget_a
        == widget_b
        == {
            "state": "omitted",
            "pipeline_value": None,
            "pipeline_value_by_currency": [],
            "win_rate": None,
            "comparison": None,
            "drill_down": None,
        }
    )

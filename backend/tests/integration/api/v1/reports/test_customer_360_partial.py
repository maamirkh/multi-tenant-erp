"""T168 — Scenario N: partial composition. CRM disabled + Installments
entitled, user missing ``reports.crm.view`` — Sales/Accounting/
Installments present, CRM ``OMITTED(reason="not_entitled")`` (entitlement
failure takes priority over the missing permission — FR-RPT-041's
ordering). A second sub-case additionally removes
``reports.accounting.view`` (Accounting stays entitled — a core, always-on
domain) and asserts ``OMITTED(reason="not_permitted")`` for Accounting,
distinct from CRM's ``not_entitled`` reason.
"""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    configure_accounting_minimal,
    create_sales_customer,
    reports_url,
    setup_company,
)


def _revoke_permissions(
    db: Session, company_id: UUID, user_id: UUID, permission_codes: set[str]
) -> None:
    member = CompanyMemberRepository(db).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    repo = RolePermissionRepository(db)
    current = repo.get_permission_codes_for_role(member.role_id)
    repo.bulk_set_permissions_for_role(member.role_id, current - permission_codes)
    db.commit()


def _owner_user_id(db: Session, company_id: UUID) -> UUID:
    members, _total = CompanyMemberRepository(db).list_by_company(company_id)
    return members[0].user_id


def test_crm_disabled_and_missing_permission_reports_not_entitled(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db_session)
    ).enable(company_id)
    customer = create_sales_customer(db_session, company_id)
    # CRM left at its default-disabled state; also strip the permission.
    _revoke_permissions(
        db_session,
        company_id,
        _owner_user_id(db_session, company_id),
        {"reports.crm.view"},
    )

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["sales"]["state"] == "present"
    assert data["accounting_ar"]["state"] == "present"
    assert data["installments"]["state"] == "present"
    assert data["crm"]["state"] == "omitted"
    assert data["crm"]["reason"] == "not_entitled"


def test_accounting_permission_missing_reports_not_permitted_distinct_from_crm(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    configure_accounting_minimal(db_session, company_id)
    customer = create_sales_customer(db_session, company_id)
    _revoke_permissions(
        db_session,
        company_id,
        _owner_user_id(db_session, company_id),
        {"reports.crm.view", "reports.accounting.view"},
    )

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["crm"]["state"] == "omitted"
    assert data["crm"]["reason"] == "not_entitled"
    assert data["accounting_ar"]["state"] == "omitted"
    assert data["accounting_ar"]["reason"] == "not_permitted"
    assert data["crm"]["reason"] != data["accounting_ar"]["reason"]

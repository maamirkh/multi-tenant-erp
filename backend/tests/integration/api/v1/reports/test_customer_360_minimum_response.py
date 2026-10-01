"""T169 — Scenario O: minimum-useful-response rule (FR-RPT-116, T164). A
user authorized only for the base gate (``reports.customer_360.view`` +
the tenant-scoped customer lookup) but missing every one of the four
domain permissions gets an identity-only response — all four sections
explicitly ``OMITTED``, never a 403/404 — distinct from T167's
fully-denied (customer not found/cross-tenant) branch, which never
resolves an identity at all.
"""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    create_sales_customer,
    reports_url,
    setup_company,
)


def _owner_user_id(db: Session, company_id: UUID) -> UUID:
    members, _total = CompanyMemberRepository(db).list_by_company(company_id)
    return members[0].user_id


def test_only_base_gate_authorized_returns_identity_only_all_omitted(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    customer = create_sales_customer(db_session, company_id)

    member = CompanyMemberRepository(db_session).get_by_user_id(
        user_id=_owner_user_id(db_session, company_id), company_id=company_id
    )
    assert member is not None
    repo = RolePermissionRepository(db_session)
    current = repo.get_permission_codes_for_role(member.role_id)
    stripped = current - {
        "reports.sales.view",
        "reports.accounting.view",
        "reports.crm.view",
        "reports.installments.view",
    }
    assert "reports.customer_360.view" in stripped
    repo.bulk_set_permissions_for_role(member.role_id, stripped)
    db_session.commit()

    resp = test_client.get(
        reports_url(company_id, f"/customer-360/{customer.id}"),
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["customer_id"] == str(customer.id)
    assert data["customer_name"] == customer.legal_name
    # Sales/Accounting are core, always-entitled domains — stripping only
    # the permission reports "not_permitted". CRM/Installments are left at
    # their default-disabled state in this test (never enabled), so their
    # entitlement check fails first and reports "not_entitled" regardless
    # of the also-stripped permission (FR-RPT-041's priority, T168).
    expected_reasons = {
        "sales": "not_permitted",
        "accounting_ar": "not_permitted",
        "crm": "not_entitled",
        "installments": "not_entitled",
    }
    for section_key, expected_reason in expected_reasons.items():
        assert data[section_key]["state"] == "omitted", section_key
        assert data[section_key]["reason"] == expected_reason, section_key

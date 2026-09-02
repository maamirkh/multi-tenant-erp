"""[Epic 10, Phase 13] Real, live-ASGI-request evidence for the
``GET /my-permissions`` endpoint added in this phase to unblock
``frontend/src/hooks/installments/useInstallmentsPermissions.ts`` (T216).

Mirrors ``test_http_security_closure.py``'s fixtures/patterns exactly —
real ``main.create_app()`` instance, real login, real Role/RolePermission/
CompanyMember rows, only ``get_db`` overridden.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.installments.constants import ALL_INSTALLMENTS_PERMISSION_CODES
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from tests.fixtures.auth_fixtures import create_test_user

_INSTALLMENTS_PREFIX = "/api/v1/companies/{company_id}/installments"


def _make_company(db: Session) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(email=f"myperm-owner-{suffix}@example.test", display_name="Owner")
    db.add(owner)
    db.flush()
    company = Company(
        id=uuid.uuid4(),
        legal_name=f"MyPerm Co {suffix}",
        slug=f"myperm-co-{suffix}",
        owner_id=owner.id,
        email=f"myperm-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _login(test_client: TestClient, db: Session, *, email: str, password: str) -> str:
    create_test_user(db, email=email, password=password)
    db.commit()
    response = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def _ensure_permission(db: Session, code: str) -> None:
    if db.get(Permission, code) is not None:
        return
    db.add(
        Permission(
            id=code, code=code, label=code, module="installments", action="manage"
        )
    )
    db.flush()


def _grant_membership_with_permissions(
    db: Session,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    codes: set[str],
) -> None:
    for code in codes:
        _ensure_permission(db, code)
    role = Role(
        company_id=company_id,
        name=f"MyPerm Role {uuid.uuid4().hex[:8]}",
        slug=f"myperm-role-{uuid.uuid4().hex[:10]}",
        rank=50,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    db.flush()
    for code in codes:
        db.add(RolePermission(role_id=role.id, permission_id=code))
    db.flush()
    db.add(
        CompanyMember(
            company_id=company_id,
            user_id=user_id,
            role_id=role.id,
            status=MembershipStatus.active.value,
        )
    )
    db.commit()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestMyPermissionsHttp:
    def test_unauthenticated_request_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)
        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/my-permissions"
        )
        assert response.status_code == 401, response.text

    def test_returns_exactly_granted_codes_no_more_no_less(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)
        email = f"myperm-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client, pg_db_session, email=email, password="MyPerm@1234"
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        granted = {"installments.contract.view", "installments.collection.create"}
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes=granted,
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/my-permissions",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        returned = set(response.json()["data"]["permissions"])
        assert returned == granted

    def test_no_membership_is_rejected_before_reaching_handler(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """The router-mount-level ``get_current_company_member`` dependency
        (api/v1/router.py) rejects non-members before any installments
        handler runs — same behavior as every other installments endpoint,
        and the same mount pattern CRM's own ``/my-permissions`` sits
        behind. The handler's own ``member is None`` branch is defense in
        depth mirroring ``get_my_crm_permissions`` exactly, not reachable
        through this mount."""
        company = _make_company(pg_db_session)
        email = f"myperm-nomember-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client, pg_db_session, email=email, password="MyPerm@1234"
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/my-permissions",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text

    def test_cross_tenant_membership_not_leaked(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """Company A membership/permissions must not surface when querying
        Company B's /my-permissions (tenant isolation) — rejected at the
        router-mount ``get_current_company_member`` dependency since the
        user has no membership row for Company B."""
        company_a = _make_company(pg_db_session)
        company_b = _make_company(pg_db_session)
        email = f"myperm-crosstenant-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client, pg_db_session, email=email, password="MyPerm@1234"
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company_a.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_b.id) + "/my-permissions",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text


class TestAllInstallmentsPermissionCodesConstant:
    def test_exactly_sixteen_codes(self) -> None:
        assert len(ALL_INSTALLMENTS_PERMISSION_CODES) == 16

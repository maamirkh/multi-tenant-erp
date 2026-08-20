"""[T098] [Gate C] Multi-tenant user — suspending Company A must not
affect Company B (plan.md §9-§10, ADR-6's tenant-isolation guarantee —
the reason blanket session revocation by user_id was rejected).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    seed_system_roles,
)


def _make_platform_token_with_permissions(db: Session, codes: set[str]) -> str:
    from modules.auth.models.user import User

    user = User(
        email=f"cross-tenant-platform-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Cross Tenant Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()

    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"cross-tenant-test-role-{uuid.uuid4().hex[:10]}",
        name="Cross Tenant Test Role",
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()

    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()
    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


def _make_company(db: Session, *, owner_id, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"Cross Tenant Co {label} {suffix}",
        slug=f"cross-tenant-co-{label.lower()}-{suffix}",
        owner_id=owner_id,
        email=f"cross-tenant-co-{label.lower()}-{suffix}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    seed_system_roles(db, company.id)
    create_member_with_role(
        db, company_id=company.id, user_id=owner_id, role_slug="owner"
    )
    return company


def _suspend(test_client: TestClient, platform_token: str, company_id) -> object:
    return test_client.post(
        f"/api/v1/platform/tenants/{company_id}/suspend",
        json={"reason": "T098 cross-tenant isolation test"},
        headers={"Authorization": f"Bearer {platform_token}"},
    )


def _probe(test_client: TestClient, token: str, company_id) -> object:
    return test_client.get(
        f"/api/v1/companies/{company_id}/inventory/health",
        headers={"Authorization": f"Bearer {token}"},
    )


class TestSuspendingOneTenantDoesNotAffectAnother:
    def test_user_x_member_of_a_and_b_suspending_a_only_denies_a(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t098-x-{uuid.uuid4().hex[:12]}@example.com"
        password = "T098TestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)

        company_a = _make_company(db_session, owner_id=user.id, label="A")
        company_b = _make_company(db_session, owner_id=user.id, label="B")
        db_session.commit()

        platform_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend"}
        )

        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200
        access_token = login.json()["data"]["access_token"]

        # Pre-suspension: X reaches both A and B on the same token.
        assert _probe(test_client, access_token, company_a.id).status_code == 200
        assert _probe(test_client, access_token, company_b.id).status_code == 200

        suspend_response = _suspend(test_client, platform_token, company_a.id)
        assert suspend_response.status_code == 200

        # A is denied immediately, without waiting for token expiry...
        assert _probe(test_client, access_token, company_a.id).status_code == 403
        # ...but the SAME still-unexpired token keeps working for B. This
        # is the cross-tenant-isolation proof: suspending A must not cost
        # X access to B (no blanket session revocation by user_id).
        assert _probe(test_client, access_token, company_b.id).status_code == 200

        # Confirm enforcement is not module-specific by also checking a
        # second business module for A.
        sales_response = test_client.get(
            f"/api/v1/companies/{company_a.id}/sales/health",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert sales_response.status_code == 403

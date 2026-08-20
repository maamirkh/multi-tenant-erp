"""[T043, BR-9A-001] A tenant `owner`/`admin` role grants NO Platform
authority. [T059, BR-9A-011] A deactivated Platform Administrator cannot
access Platform APIs, immediately.

Creating a ``CompanyMember`` never creates a ``PlatformAdministrator``; no
tenant role value maps to a platform principal. API-level proof follows
in T055 (Phase 4). T059 is the API-level proof of T054's session-revoking
deactivation: a still-unexpired access token stops working on the very
next request, and the session rows are already revoked in the database.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_session_repository import (
    PlatformSessionRepository,
)
from modules.platform_admin.services.platform_administrator_service import (
    PlatformAdministratorService,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.role import Role
from tests.fixtures.auth_fixtures import create_test_user


class TestTenantRoleGrantsNoPlatformAuthority:
    def test_owner_role_company_member_creates_no_platform_administrator(
        self, db_session: Session
    ) -> None:
        suffix = uuid.uuid4().hex[:12]
        user = User(
            email=f"tenant-owner-{suffix}@example.test", display_name="Tenant Owner"
        )
        db_session.add(user)
        db_session.flush()

        company = Company(
            legal_name="Boundary Test Co",
            slug=f"boundary-test-co-{suffix}",
            owner_id=user.id,
            email=f"boundary-co-{suffix}@example.test",
        )
        db_session.add(company)
        db_session.flush()

        owner_role = Role(company_id=company.id, name="Owner", slug="owner", rank=100)
        db_session.add(owner_role)
        db_session.flush()

        member = CompanyMember(
            company_id=company.id,
            user_id=user.id,
            role_id=owner_role.id,
            status="active",
        )
        db_session.add(member)
        db_session.flush()

        # No PlatformAdministrator row exists for THIS user — creating the
        # highest-privilege tenant role (owner, rank 100) had zero effect
        # on Platform identity. Scoped to this user's id rather than a
        # table-wide count, since the shared test database may carry rows
        # from other tests in the same session.
        repo = PlatformAdministratorRepository(db_session)
        assert repo.get_by_user_id(user.id) is None

    def test_admin_role_company_member_creates_no_platform_administrator(
        self, db_session: Session
    ) -> None:
        suffix = uuid.uuid4().hex[:12]
        user = User(
            email=f"tenant-admin-{suffix}@example.test", display_name="Tenant Admin"
        )
        db_session.add(user)
        db_session.flush()

        owner_user = User(
            email=f"owner-for-admin-{suffix}@example.test", display_name="Owner"
        )
        db_session.add(owner_user)
        db_session.flush()

        company = Company(
            legal_name="Boundary Admin Co",
            slug=f"boundary-admin-co-{suffix}",
            owner_id=owner_user.id,
            email=f"boundary-admin-co-{suffix}@example.test",
        )
        db_session.add(company)
        db_session.flush()

        admin_role = Role(company_id=company.id, name="Admin", slug="admin", rank=90)
        db_session.add(admin_role)
        db_session.flush()

        member = CompanyMember(
            company_id=company.id,
            user_id=user.id,
            role_id=admin_role.id,
            status="active",
        )
        db_session.add(member)
        db_session.flush()

        repo = PlatformAdministratorRepository(db_session)
        assert repo.get_by_user_id(user.id) is None
        # No tenant role value — "owner", "admin", or any other slug/rank —
        # is ever consulted by PlatformAdministratorRepository at all; this
        # is a structural guarantee (the repository has no CompanyMember
        # join in its implementation), not a runtime coincidence.


class TestDeactivatedAdministratorCannotAccessPlatformApis:
    """T059 [BR-9A-011] — the API-level proof of T054. A PlatformSession
    created by a real login is genuinely revoked, in the database, the
    moment the owning administrator is deactivated — not merely rejected
    by some separate in-memory check."""

    def test_deactivation_revokes_the_in_flight_access_token_immediately(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # .com, not .test: Pydantic's EmailStr validator rejects .test as a
        # reserved special-use TLD (RFC 2606) — this email goes through
        # real HTTP request validation via the login endpoint.
        email = f"deactivate-boundary-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword@1234"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.commit()

        login_response = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["data"]["access_token"]

        # Sanity check: the token genuinely works before deactivation.
        pre_deactivation = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert pre_deactivation.status_code == 204

        # Log back in for a second, independent session — the one we'll
        # actually deactivate against, so this test doesn't depend on the
        # logout call above having revoked anything.
        login_response_2 = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response_2.status_code == 200
        second_access_token = login_response_2.json()["data"]["access_token"]

        # Deactivate via the real service, with a REAL PlatformSessionRepository
        # injected as the SessionRevoker (T054's completed wiring).
        db_session.refresh(administrator)
        admin_repo = PlatformAdministratorRepository(db_session)
        audit_repo = PlatformAuditRepository(db_session)
        audit_service = PlatformAuditService(db_session, audit_repo)
        session_repo = PlatformSessionRepository(db_session)
        service = PlatformAdministratorService(
            db_session, admin_repo, audit_service, session_revoker=session_repo
        )
        service.deactivate(
            administrator, actor_platform_administrator_id=None, reason="T059 test"
        )

        # The session rows are already revoked in the database.
        active_sessions = session_repo.get_active_by_administrator(administrator.id)
        assert active_sessions == []
        all_sessions = (
            db_session.query(PlatformSession)
            .filter(PlatformSession.platform_administrator_id == administrator.id)
            .all()
        )
        assert all(s.is_revoked for s in all_sessions)

        # The same, still-unexpired access token is rejected on the very
        # next request.
        post_deactivation = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {second_access_token}"},
        )
        assert post_deactivation.status_code == 401

    def test_forced_audit_failure_rolls_back_session_revocation_too(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """T054's 3-way atomicity: unlike Phase 3's T044 (no session to
        revoke), this administrator has a real, active PlatformSession —
        proving the state change, the audit row, AND the session
        revocation all fail to commit together, not just the first two."""
        from unittest.mock import patch

        email = f"deactivate-atomic-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword@1234"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.commit()

        login_response = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["data"]["access_token"]

        db_session.refresh(administrator)
        admin_repo = PlatformAdministratorRepository(db_session)
        audit_repo = PlatformAuditRepository(db_session)
        audit_service = PlatformAuditService(db_session, audit_repo)
        session_repo = PlatformSessionRepository(db_session)
        service = PlatformAdministratorService(
            db_session, admin_repo, audit_service, session_revoker=session_repo
        )

        with patch.object(
            PlatformAuditService,
            "record",
            side_effect=RuntimeError("simulated audit-write failure"),
        ):
            try:
                service.deactivate(
                    administrator,
                    actor_platform_administrator_id=None,
                    reason="forced failure atomicity test",
                )
            except RuntimeError:
                pass

        db_session.rollback()

        reloaded = admin_repo.get_by_id(administrator.id)
        assert reloaded.is_active is True

        active_sessions = session_repo.get_active_by_administrator(administrator.id)
        assert len(active_sessions) == 1, (
            "the session must remain active — its revocation must not "
            "survive a failed audit write, same as the state change"
        )

        # The still-valid, never-revoked access token still works, proving
        # the rollback was genuine, not merely a database-level assertion.
        still_works = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert still_works.status_code == 204

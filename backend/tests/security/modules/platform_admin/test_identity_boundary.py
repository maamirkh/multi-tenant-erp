"""[T043, BR-9A-001] A tenant `owner`/`admin` role grants NO Platform
authority.

Creating a ``CompanyMember`` never creates a ``PlatformAdministrator``; no
tenant role value maps to a platform principal. API-level proof follows
in T055 (Phase 4).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.role import Role


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

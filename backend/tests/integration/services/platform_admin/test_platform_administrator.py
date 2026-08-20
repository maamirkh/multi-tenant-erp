"""[T042] A Platform Administrator with zero company memberships is a
valid, complete principal (BR-9A-010).

Creates an account with no ``CompanyMember`` row anywhere and asserts no
membership check blocks its creation. API-level proof follows in T059
(Phase 4).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.services.platform_administrator_service import (
    PlatformAdministratorService,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService


def _make_service(db: Session) -> PlatformAdministratorService:
    admin_repo = PlatformAdministratorRepository(db)
    audit_repo = PlatformAuditRepository(db)
    audit_service = PlatformAuditService(db, audit_repo)
    return PlatformAdministratorService(db, admin_repo, audit_service)


class TestPlatformAdministratorZeroMemberships:
    def test_account_valid_with_no_company_member_row(
        self, db_session: Session
    ) -> None:
        user = User(
            email=f"platform-owner-{uuid.uuid4().hex[:12]}@example.test",
            display_name="Platform Owner",
        )
        db_session.add(user)
        db_session.flush()

        service = _make_service(db_session)

        administrator = service.create(
            user_id=user.id, actor_platform_administrator_id=None
        )

        assert administrator.id is not None
        assert administrator.user_id == user.id
        assert administrator.is_active is True

        # Confirm zero CompanyMember rows exist for THIS user — creation
        # succeeded despite this, proving no membership check gated it
        # (BR-9A-010). Scoped to this user's id rather than a table-wide
        # count, since the shared test database may carry rows from other
        # tests in the same session.
        from modules.users_roles.models.company_member import CompanyMember

        member_count = (
            db_session.query(CompanyMember)
            .filter(CompanyMember.user_id == user.id)
            .count()
        )
        assert member_count == 0

    def test_zero_memberships_does_not_block_role_assignment_seam(
        self, db_session: Session
    ) -> None:
        """Role assignment itself is Phase 5 scope; here we assert the
        repository/service layer exposes the administrator by id with no
        membership-derived gate anywhere in the lookup path."""
        user = User(
            email=f"no-membership-{uuid.uuid4().hex[:12]}@example.test",
            display_name="No Membership",
        )
        db_session.add(user)
        db_session.flush()

        service = _make_service(db_session)
        administrator = service.create(
            user_id=user.id, actor_platform_administrator_id=None
        )

        repo = PlatformAdministratorRepository(db_session)
        fetched = repo.get_by_id(administrator.id)
        assert fetched is not None
        assert fetched.is_active is True

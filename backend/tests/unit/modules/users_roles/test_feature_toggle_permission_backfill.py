"""[T141] Backfill: existing companies' owner/admin roles genuinely gain
the three new feature-toggle-management permission codes, not only
companies created after this deploy (Epic 9A Phase 10, plan.md §14 risk
mitigation).
"""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from modules.users_roles.repositories.permission_repository import PermissionRepository
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository
from modules.users_roles.services.role_seed_service import RoleSeedService

_NEW_CODES = {
    "inventory.settings.manage",
    "sales.settings.manage",
    "purchase.settings.manage",
}


def _make_company(db: Session, *, owner_id: UUID) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T141 Backfill Co {suffix}",
        slug=f"t141-backfill-co-{suffix}",
        owner_id=owner_id,
        email=f"t141-backfill-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    return company


def _seed_service(db: Session) -> RoleSeedService:
    return RoleSeedService(
        db=db,
        role_repo=RoleRepository(db),
        permission_repo=PermissionRepository(db),
        role_permission_repo=RolePermissionRepository(db),
    )


class TestBackfillGrantsNewPermissionsToPreExistingCompanies:
    def test_backfill_restores_missing_codes_on_owner_and_admin(
        self, db_session: Session
    ) -> None:
        from modules.auth.models.user import User

        user = User(
            email=f"t141-owner-{uuid.uuid4().hex[:10]}@example.com",
            display_name="T141 Owner",
        )
        db_session.add(user)
        db_session.flush()

        company = _make_company(db_session, owner_id=user.id)
        seed_service = _seed_service(db_session)
        # Simulates the company's original seeding, which ran BEFORE
        # this deploy added the new codes to DEFAULT_ROLE_PERMISSIONS
        # (in reality that seeding happened with the old constants; here
        # we seed with the now-current constants, then strip the 3 new
        # rows to reproduce the identical pre-deploy end state).
        seed_service.seed_all(company.id)

        owner_role = db_session.execute(
            select(Role).where(Role.company_id == company.id, Role.slug == "owner")
        ).scalar_one()
        admin_role = db_session.execute(
            select(Role).where(Role.company_id == company.id, Role.slug == "admin")
        ).scalar_one()

        db_session.query(RolePermission).filter(
            RolePermission.role_id.in_([owner_role.id, admin_role.id]),
            RolePermission.permission_id.in_(_NEW_CODES),
        ).delete(synchronize_session=False)
        db_session.commit()

        role_permission_repo = RolePermissionRepository(db_session)
        before_owner = role_permission_repo.get_permission_codes_for_role(owner_role.id)
        before_admin = role_permission_repo.get_permission_codes_for_role(admin_role.id)
        assert not (before_owner & _NEW_CODES)
        assert not (before_admin & _NEW_CODES)

        processed = (
            seed_service.backfill_default_role_permissions_for_existing_companies(
                [company.id]
            )
        )
        assert processed == 1

        after_owner = role_permission_repo.get_permission_codes_for_role(owner_role.id)
        after_admin = role_permission_repo.get_permission_codes_for_role(admin_role.id)
        assert _NEW_CODES <= after_owner
        assert _NEW_CODES <= after_admin

    def test_backfill_is_idempotent_and_does_not_duplicate(
        self, db_session: Session
    ) -> None:
        from modules.auth.models.user import User

        user = User(
            email=f"t141-owner2-{uuid.uuid4().hex[:10]}@example.com",
            display_name="T141 Owner 2",
        )
        db_session.add(user)
        db_session.flush()

        company = _make_company(db_session, owner_id=user.id)
        seed_service = _seed_service(db_session)
        seed_service.seed_all(company.id)

        # Company already has the new codes (created after this deploy) —
        # re-running the backfill must be a genuine no-op, not an error
        # or a duplicate row (RolePermission has a unique constraint).
        processed = (
            seed_service.backfill_default_role_permissions_for_existing_companies(
                [company.id]
            )
        )
        assert processed == 1

        owner_role = db_session.execute(
            select(Role).where(Role.company_id == company.id, Role.slug == "owner")
        ).scalar_one()
        codes = RolePermissionRepository(db_session).get_permission_codes_for_role(
            owner_role.id
        )
        assert _NEW_CODES <= codes

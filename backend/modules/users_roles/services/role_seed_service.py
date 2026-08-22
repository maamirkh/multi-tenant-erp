"""RoleSeedService — idempotent seeding of system roles and permissions.

Seeds the 8 system roles (from constants.py) and 14 initial permissions
for a company.  Safe to call multiple times — uses database unique
constraints to skip duplicates.

Called during company creation to bootstrap the role hierarchy.

Spec reference: FR-040, tasks T026.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from modules.users_roles.constants import (
    DEFAULT_ROLE_PERMISSIONS,
    INITIAL_PERMISSIONS,
    SYSTEM_ROLES,
)
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from modules.users_roles.repositories.permission_repository import (
    PermissionRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository

logger = logging.getLogger(__name__)


class RoleSeedService:
    """Seeds system roles and permissions for a company.

    Args:
        db: SQLAlchemy ``Session`` shared by all repositories.
        role_repo: Injected ``RoleRepository``.
        permission_repo: Injected ``PermissionRepository``.
        role_permission_repo: Injected ``RolePermissionRepository``.
    """

    def __init__(
        self,
        db: Session,
        role_repo: RoleRepository,
        permission_repo: PermissionRepository,
        role_permission_repo: RolePermissionRepository,
    ) -> None:
        self._db = db
        self._role_repo = role_repo
        self._permission_repo = permission_repo
        self._role_permission_repo = role_permission_repo

    def seed_permissions(self) -> list[Permission]:
        """Seed global permissions (idempotent).

        Returns:
            List of all permission records (existing or newly created).
        """
        result: list[Permission] = []
        for perm_def in INITIAL_PERMISSIONS:
            existing = self._permission_repo.get_by_code(perm_def.code)
            if existing is not None:
                result.append(existing)
                continue
            permission = Permission(
                id=perm_def.code,
                code=perm_def.code,
                label=perm_def.label,
                module=perm_def.module,
                action=perm_def.action,
                description=perm_def.description,
            )
            self._db.add(permission)
            result.append(permission)

        self._db.flush()
        logger.info("Permissions seeded", extra={"count": len(result)})
        return result

    def seed_roles_for_company(
        self,
        company_id: UUID,
        created_by: UUID | None = None,
    ) -> list[Role]:
        """Seed the 8 system roles for a company (idempotent).

        Args:
            company_id: Target company UUID.
            created_by: User who triggered the seeding (company creator).

        Returns:
            List of all system role records for the company.
        """
        result: list[Role] = []
        for role_def in SYSTEM_ROLES:
            existing = self._role_repo.get_by_slug(company_id, role_def.slug)
            if existing is not None:
                result.append(existing)
                continue
            role = Role(
                company_id=company_id,
                name=role_def.name,
                slug=role_def.slug,
                rank=role_def.rank,
                description=role_def.description,
                is_system=True,
                is_active=True,
                created_by=created_by,
            )
            self._db.add(role)
            self._db.flush()
            result.append(role)

        logger.info(
            "System roles seeded",
            extra={"company_id": str(company_id), "count": len(result)},
        )
        return result

    def seed_role_permissions(
        self,
        company_id: UUID,
    ) -> None:
        """Seed the default role-permission mappings for a company (idempotent).

        Maps system roles to their default permissions using the matrix
        defined in ``constants.DEFAULT_ROLE_PERMISSIONS``.
        """
        system_roles = self._role_repo.get_system_roles(company_id)
        role_by_slug = {r.slug: r for r in system_roles}

        for slug, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
            role = role_by_slug.get(slug)
            if role is None:
                logger.warning(
                    "System role not found for permission mapping",
                    extra={"slug": slug, "company_id": str(company_id)},
                )
                continue

            existing_codes = self._role_permission_repo.get_permission_codes_for_role(
                role.id
            )
            new_codes = permission_codes - existing_codes
            for code in sorted(new_codes):
                rp = RolePermission(role_id=role.id, permission_id=code)
                self._db.add(rp)

        self._db.flush()
        logger.info(
            "Role-permission mappings seeded",
            extra={"company_id": str(company_id)},
        )

    def backfill_default_role_permissions_for_existing_companies(
        self, company_ids: list[UUID]
    ) -> int:
        """One-time backfill (Epic 9A Phase 10, T141, plan.md §14 risk
        mitigation): re-run ``seed_role_permissions`` for every already-
        existing company, so a newly-added ``DEFAULT_ROLE_PERMISSIONS``
        code (e.g. the three feature-toggle-management codes) reaches
        pre-existing owner/admin roles too — not only companies created
        after this deploy. Uses the existing, already-idempotent
        ``seed_role_permissions`` mechanism unchanged (additive-only:
        ``new_codes = permission_codes - existing_codes``); safe to
        re-run. Not a migration (ADR-8's decoupling principle) — a
        one-time operator step, mirroring ``rollout_service.py``'s own
        convention for the identical problem shape in Epic 9A.

        Returns the number of companies processed.
        """
        for company_id in company_ids:
            self.seed_role_permissions(company_id)
        self._db.commit()
        return len(company_ids)

    def seed_all(
        self,
        company_id: UUID,
        created_by: UUID | None = None,
    ) -> list[Role]:
        """Run the complete seed sequence: permissions → roles → mappings.

        Args:
            company_id: Target company UUID.
            created_by: User who triggered the seeding.

        Returns:
            List of system roles for the company.
        """
        self.seed_permissions()
        roles = self.seed_roles_for_company(company_id, created_by)
        self.seed_role_permissions(company_id)
        self._db.commit()
        logger.info(
            "Complete seed finished",
            extra={"company_id": str(company_id)},
        )
        return roles

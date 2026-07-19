"""RoleService — orchestrates custom role CRUD operations.

Implements custom role creation (US3): validates name uniqueness,
rank range, system role rank conflicts, custom role limits, and
permission assignment. Enforces system role immutability.

Each method is a complete unit of work: validate → state change →
audit log → domain event → commit.

Spec reference: FR-041 through FR-048, FR-074, BR-031, tasks T048, T085.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.config.settings import Settings
from core.events.outbox import EventOutboxRepository
from core.utils.datetime import utcnow
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.users_roles.constants import SYSTEM_ROLES
from modules.users_roles.events import (
    RoleCreatedEvent,
    RoleDeletedEvent,
    RoleUpdatedEvent,
)
from modules.users_roles.exceptions import (
    CustomRoleLimitExceededError,
    InvalidRoleRankError,
    RoleHasActiveAssignmentsError,
    RoleNameConflictError,
    RoleNotFoundError,
    SystemRoleImmutableError,
)
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.permission_repository import (
    PermissionRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository

logger = logging.getLogger(__name__)

# System role ranks that custom roles cannot use
SYSTEM_ROLE_RANKS: frozenset[int] = frozenset(r.rank for r in SYSTEM_ROLES)


def _slugify(name: str) -> str:
    """Convert a role name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _new_correlation_id() -> str:
    return str(uuid.uuid4())


class RoleService:
    """Orchestrates custom role operations.

    Args:
        db: SQLAlchemy ``Session`` shared by all repositories.
        role_repo: Injected ``RoleRepository``.
        permission_repo: Injected ``PermissionRepository``.
        role_permission_repo: Injected ``RolePermissionRepository``.
        member_repo: Injected ``CompanyMemberRepository``.
        audit_service: Injected ``CompanyAuditService``.
        outbox_repo: Injected ``EventOutboxRepository``.
        settings: Application settings.
    """

    def __init__(
        self,
        db: Session,
        role_repo: RoleRepository,
        permission_repo: PermissionRepository,
        role_permission_repo: RolePermissionRepository,
        member_repo: CompanyMemberRepository,
        audit_service: CompanyAuditService,
        outbox_repo: EventOutboxRepository,
        settings: Settings,
    ) -> None:
        self._db = db
        self._role_repo = role_repo
        self._permission_repo = permission_repo
        self._role_permission_repo = role_permission_repo
        self._member_repo = member_repo
        self._audit_service = audit_service
        self._outbox_repo = outbox_repo
        self._settings = settings

    def create_custom_role(
        self,
        *,
        company_id: UUID,
        name: str,
        rank: int,
        actor_user_id: UUID,
        description: str | None = None,
        permission_codes: list[str] | None = None,
        request_context: dict[str, Any] | None = None,
    ) -> Role:
        """Create a new custom role in a company.

        Steps:
        1. Validate rank range 1-99 (FR-042)
        2. Validate rank != system role ranks (FR-042)
        3. Validate name uniqueness (BR-031, case-insensitive)
        4. Validate custom role count < limit (FR-048)
        5. Validate permission codes exist
        6. Create Role record
        7. Assign permissions
        8. Write audit log
        9. Publish RoleCreatedEvent

        Raises:
            InvalidRoleRankError: Rank outside 1-99 or conflicts with system.
            RoleNameConflictError: Name already exists in company.
            CustomRoleLimitExceededError: Company at custom role limit.
        """
        ctx = request_context or {}

        # 1. Validate rank range
        if rank < 1 or rank > 99:
            raise InvalidRoleRankError(details={"rank": rank, "valid_range": "1-99"})

        # 2. Validate rank doesn't conflict with system role ranks
        if rank in SYSTEM_ROLE_RANKS:
            raise InvalidRoleRankError(
                message="Custom role rank conflicts with a system role rank.",
                details={
                    "rank": rank,
                    "system_ranks": sorted(SYSTEM_ROLE_RANKS),
                },
            )

        # 3. Validate name uniqueness (case-insensitive)
        existing = self._role_repo.get_by_name(company_id, name)
        if existing is not None:
            raise RoleNameConflictError(
                details={"name": name, "company_id": str(company_id)}
            )

        # 4. Validate custom role count
        current_count = self._role_repo.count_custom_roles(company_id)
        if current_count >= self._settings.MAX_CUSTOM_ROLES_PER_COMPANY:
            raise CustomRoleLimitExceededError(
                details={
                    "current_count": current_count,
                    "max_custom_roles": self._settings.MAX_CUSTOM_ROLES_PER_COMPANY,
                }
            )

        # 5. Validate permission codes
        codes = set(permission_codes or [])
        if codes:
            found = self._permission_repo.get_by_codes(codes)
            found_codes = {p.code for p in found}
            invalid = codes - found_codes
            if invalid:
                raise InvalidRoleRankError(
                    message="One or more permission codes are invalid.",
                    details={"invalid_codes": sorted(invalid)},
                )

        # 6. Create Role record
        slug = _slugify(name)
        # Ensure slug uniqueness by appending short uuid if conflict
        if self._role_repo.get_by_slug(company_id, slug) is not None:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        role = Role(
            company_id=company_id,
            name=name,
            slug=slug,
            description=description,
            rank=rank,
            is_system=False,
            is_active=True,
            created_by=actor_user_id,
        )
        self._db.add(role)
        self._db.flush()

        # 7. Assign permissions
        if codes:
            self._role_permission_repo.bulk_set_permissions_for_role(role.id, codes)

        # 8. Write audit log
        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ROLE_CREATED",
            after_state={
                "role_id": str(role.id),
                "name": name,
                "slug": slug,
                "rank": rank,
                "permission_codes": sorted(codes),
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # 9. Publish domain event
        now = utcnow()
        event = RoleCreatedEvent(
            company_id=company_id,
            role_id=role.id,
            role_name=name,
            created_at=now,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(role)

        logger.info(
            "Custom role created",
            extra={
                "company_id": str(company_id),
                "role_id": str(role.id),
                "role_name": name,
            },
        )
        return role

    def update_custom_role(
        self,
        *,
        company_id: UUID,
        role_id: UUID,
        actor_user_id: UUID,
        name: str | None = None,
        description: str | None = ...,  # type: ignore[assignment]
        rank: int | None = None,
        permission_codes: list[str] | None = None,
        request_context: dict[str, Any] | None = None,
    ) -> Role:
        """Update a custom role.

        Raises:
            RoleNotFoundError: Role does not exist.
            SystemRoleImmutableError: Cannot modify a system role (FR-041).
            InvalidRoleRankError: Invalid rank value.
            RoleNameConflictError: Name conflict.
        """
        ctx = request_context or {}

        # Resolve role
        role = self._role_repo.get_by_id_or_none(id=role_id, company_id=company_id)
        if role is None:
            raise RoleNotFoundError(details={"role_id": str(role_id)})

        # Enforce system role immutability (FR-041)
        if role.is_system:
            raise SystemRoleImmutableError()

        before_state: dict[str, Any] = {
            "role_id": str(role_id),
            "name": role.name,
            "rank": role.rank,
        }

        # Update name
        if name is not None and name != role.name:
            existing = self._role_repo.get_by_name(company_id, name)
            if existing is not None and existing.id != role_id:
                raise RoleNameConflictError(
                    details={"name": name, "company_id": str(company_id)}
                )
            role.name = name
            role.slug = _slugify(name)
            # Ensure slug uniqueness
            if self._role_repo.get_by_slug(company_id, role.slug) is not None:
                existing_slug = self._role_repo.get_by_slug(company_id, role.slug)
                if existing_slug and existing_slug.id != role_id:
                    role.slug = f"{role.slug}-{uuid.uuid4().hex[:6]}"

        # Update rank
        if rank is not None and rank != role.rank:
            if rank < 1 or rank > 99:
                raise InvalidRoleRankError(
                    details={"rank": rank, "valid_range": "1-99"}
                )
            if rank in SYSTEM_ROLE_RANKS:
                raise InvalidRoleRankError(
                    message="Custom role rank conflicts with a system role rank.",
                    details={"rank": rank, "system_ranks": sorted(SYSTEM_ROLE_RANKS)},
                )
            role.rank = rank

        # Update description
        if description is not ...:
            role.description = description

        self._db.flush()

        # Update permissions
        if permission_codes is not None:
            codes = set(permission_codes)
            if codes:
                found = self._permission_repo.get_by_codes(codes)
                found_codes = {p.code for p in found}
                invalid = codes - found_codes
                if invalid:
                    raise InvalidRoleRankError(
                        message="One or more permission codes are invalid.",
                        details={"invalid_codes": sorted(invalid)},
                    )
            self._role_permission_repo.bulk_set_permissions_for_role(role_id, codes)

        # Audit log
        after_state: dict[str, Any] = {
            "role_id": str(role_id),
            "name": role.name,
            "rank": role.rank,
        }
        if permission_codes is not None:
            after_state["permission_codes"] = sorted(set(permission_codes))

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ROLE_UPDATED",
            before_state=before_state,
            after_state=after_state,
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # Domain event
        event = RoleUpdatedEvent(
            company_id=company_id,
            role_id=role_id,
            updated_at=utcnow(),
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(role)

        logger.info(
            "Custom role updated",
            extra={"company_id": str(company_id), "role_id": str(role_id)},
        )
        return role

    def deactivate_role(
        self,
        *,
        company_id: UUID,
        role_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> Role:
        """Deactivate a custom role (FR-047).

        Sets ``is_active=False``, preventing new assignments while
        preserving existing ones.

        Raises:
            RoleNotFoundError: Role does not exist.
            SystemRoleImmutableError: Cannot deactivate a system role.
        """
        ctx = request_context or {}

        role = self._role_repo.get_by_id_or_none(id=role_id, company_id=company_id)
        if role is None:
            raise RoleNotFoundError(details={"role_id": str(role_id)})

        if role.is_system:
            raise SystemRoleImmutableError()

        role.is_active = False
        self._db.flush()

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ROLE_DEACTIVATED",
            after_state={"role_id": str(role_id), "name": role.name},
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        self._db.commit()
        self._db.refresh(role)

        logger.info(
            "Custom role deactivated",
            extra={"company_id": str(company_id), "role_id": str(role_id)},
        )
        return role

    def delete_role(
        self,
        *,
        company_id: UUID,
        role_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> None:
        """Delete a custom role (FR-046).

        Only allowed if zero active members are assigned.

        Raises:
            RoleNotFoundError: Role does not exist.
            SystemRoleImmutableError: Cannot delete a system role.
            RoleHasActiveAssignmentsError: Active members assigned.
        """
        ctx = request_context or {}

        role = self._role_repo.get_by_id_or_none(id=role_id, company_id=company_id)
        if role is None:
            raise RoleNotFoundError(details={"role_id": str(role_id)})

        if role.is_system:
            raise SystemRoleImmutableError()

        # Check for active assignments
        active_count = self._member_repo.count_by_role(company_id, role_id)
        if active_count > 0:
            raise RoleHasActiveAssignmentsError(
                details={
                    "role_id": str(role_id),
                    "active_assignments": active_count,
                }
            )

        # Soft delete
        role.is_deleted = True
        role.deleted_at = utcnow()
        self._db.flush()

        # Remove permission mappings
        self._role_permission_repo.delete_by_role_id(role_id)

        # Audit log
        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ROLE_DELETED",
            after_state={"role_id": str(role_id), "name": role.name},
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # Domain event
        event = RoleDeletedEvent(
            company_id=company_id,
            role_id=role_id,
            deleted_at=utcnow(),
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()

        logger.info(
            "Custom role deleted",
            extra={"company_id": str(company_id), "role_id": str(role_id)},
        )

    def get_role(self, role_id: UUID, company_id: UUID) -> Role:
        """Return a role by ID, scoped to company.

        Raises:
            RoleNotFoundError: If the role does not exist.
        """
        role = self._role_repo.get_by_id_or_none(id=role_id, company_id=company_id)
        if role is None:
            raise RoleNotFoundError(details={"role_id": str(role_id)})
        return role

    def list_roles(
        self,
        company_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """List roles for a company with member counts.

        Returns:
            Tuple of (role dicts with member_count, total count).
        """
        roles, total = self._role_repo.list_by_company(
            company_id, skip=skip, limit=limit, include_inactive=include_inactive
        )

        result = []
        for role in roles:
            member_count = self._member_repo.count_by_role(company_id, role.id)
            result.append(
                {
                    "role": role,
                    "member_count": member_count,
                }
            )

        return result, total

    def get_permission_codes_for_role(self, role_id: UUID) -> list[str]:
        """Return sorted permission codes for a role."""
        codes = self._role_permission_repo.get_permission_codes_for_role(role_id)
        return sorted(codes)

    def get_role_with_permissions(
        self, role_id: UUID, company_id: UUID
    ) -> tuple[Role, list[Permission], int]:
        """Load a role with its full Permission objects and assigned member count.

        Used by the GET /roles/{role_id} endpoint (T084) to return
        ``RoleDetailResponse`` per contracts/roles-api.yaml.

        Args:
            role_id:    ID of the role to retrieve.
            company_id: Tenant scope for validation.

        Returns:
            Tuple of ``(role, permissions, member_count)`` where
            ``permissions`` is sorted by module then code, and
            ``member_count`` is the count of active non-archived members.

        Raises:
            RoleNotFoundError: If the role does not exist in this company.
        """
        role = self.get_role(role_id, company_id)
        codes = self._role_permission_repo.get_permission_codes_for_role(role_id)
        permissions: list[Permission] = (
            sorted(
                self._permission_repo.get_by_codes(codes),
                key=lambda p: (p.module, p.code),
            )
            if codes
            else []
        )
        member_count = self._member_repo.count_by_role(company_id, role_id)
        return role, permissions, member_count

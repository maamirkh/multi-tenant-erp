"""FastAPI dependency injection functions for the users & roles module.

All DI factories in this module are synchronous — matching the sync
``Session`` / ``get_db`` pattern used throughout the backend.

Spec reference: Epic 4 — Users & Roles, tasks T033, T045.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.events.outbox import EventOutboxRepository
from modules.auth.repositories.session_repository import SessionRepository
from modules.auth.repositories.user_repository import UserRepository
from modules.companies.repositories.company_repository import CompanyRepository
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.platform_admin.services.company_access_service import (
    assert_company_access_allowed,
)
from modules.users_roles.models.company_member import CompanyMember
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
from modules.users_roles.repositories.user_preference_repository import (
    UserPreferenceRepository,
)
from modules.users_roles.services.invitation_service import InvitationService
from modules.users_roles.services.member_service import MemberService
from modules.users_roles.services.ownership_service import OwnershipService
from modules.users_roles.services.permission_service import PermissionService
from modules.users_roles.services.preference_service import PreferenceService
from modules.users_roles.services.profile_service import ProfileService
from modules.users_roles.services.role_seed_service import RoleSeedService
from modules.users_roles.services.role_service import RoleService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Null storage stub (used when S3 is not configured)
# ---------------------------------------------------------------------------


class _NullStorageClient:
    """No-op storage backend used when S3 is not configured.

    ``upload()`` raises ``NotImplementedError`` so accidental calls in
    non-storage environments are caught at call time, not silently swallowed.
    """

    def upload(self, file: object, key: str) -> str:
        raise NotImplementedError(
            "Storage backend not configured. "
            "Override get_profile_service() with a real S3StorageClient."
        )

    def get_url(self, key: str) -> str:
        return ""


# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_member_repo(db: Session = Depends(get_db)) -> CompanyMemberRepository:
    """Return a ``CompanyMemberRepository`` bound to the current session."""
    return CompanyMemberRepository(db)


def get_role_repo(db: Session = Depends(get_db)) -> RoleRepository:
    """Return a ``RoleRepository`` bound to the current session."""
    return RoleRepository(db)


def get_permission_repo(db: Session = Depends(get_db)) -> PermissionRepository:
    """Return a ``PermissionRepository`` bound to the current session."""
    return PermissionRepository(db)


def get_role_permission_repo(
    db: Session = Depends(get_db),
) -> RolePermissionRepository:
    """Return a ``RolePermissionRepository`` bound to the current session."""
    return RolePermissionRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_member_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MemberService:
    """Wire and return a ``MemberService`` for the current request."""
    return MemberService(
        db=db,
        member_repo=CompanyMemberRepository(db),
        role_repo=RoleRepository(db),
        audit_service=CompanyAuditService(db),
        outbox_repo=EventOutboxRepository(db),
        settings=settings,
        session_repo=SessionRepository(db),
    )


def get_invitation_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InvitationService:
    """Wire and return an ``InvitationService`` for the current request."""
    return InvitationService(
        db=db,
        member_repo=CompanyMemberRepository(db),
        audit_service=CompanyAuditService(db),
        outbox_repo=EventOutboxRepository(db),
        settings=settings,
    )


def get_role_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RoleService:
    """Wire and return a ``RoleService`` for the current request."""
    return RoleService(
        db=db,
        role_repo=RoleRepository(db),
        permission_repo=PermissionRepository(db),
        role_permission_repo=RolePermissionRepository(db),
        member_repo=CompanyMemberRepository(db),
        audit_service=CompanyAuditService(db),
        outbox_repo=EventOutboxRepository(db),
        settings=settings,
    )


def get_permission_service(
    db: Session = Depends(get_db),
) -> PermissionService:
    """Wire and return a ``PermissionService`` for the current request."""
    return PermissionService(
        permission_repo=PermissionRepository(db),
    )


def get_role_seed_service(
    db: Session = Depends(get_db),
) -> RoleSeedService:
    """Wire and return a ``RoleSeedService`` for the current request."""
    return RoleSeedService(
        db=db,
        role_repo=RoleRepository(db),
        permission_repo=PermissionRepository(db),
        role_permission_repo=RolePermissionRepository(db),
    )


def get_ownership_service(
    db: Session = Depends(get_db),
) -> OwnershipService:
    """Wire and return an ``OwnershipService`` for the current request."""
    return OwnershipService(
        db=db,
        member_repo=CompanyMemberRepository(db),
        role_repo=RoleRepository(db),
        company_repo=CompanyRepository(db),
        audit_service=CompanyAuditService(db),
        outbox_repo=EventOutboxRepository(db),
    )


# ---------------------------------------------------------------------------
# Authorization dependencies
# ---------------------------------------------------------------------------


def get_current_company_member(
    company_id: UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> CompanyMember:
    """Resolve the current user's active membership in the target company.

    Validates that the user has an active (non-archived, non-deleted)
    membership in the specified company.

    Raises:
        HTTPException 403: If the user is not an active member of the company.

    Also enforces company-scoped access invalidation (Epic 9A, T083):
    denies (403/404) when the company is suspended/deleted, or when this
    request's Session predates the company's ``access_invalidated_at``
    watermark (ADR-6) — closing the gap where every company-scoped route
    in the five business modules previously never consulted
    ``Company.status`` at all. ``get_current_user()`` itself is
    unmodified — this check happens only here, one layer up.
    """
    assert_company_access_allowed(db, company_id, current_user.session_id)

    member_repo = CompanyMemberRepository(db)
    member = member_repo.get_by_user_id(
        user_id=current_user.user_id,
        company_id=company_id,  # type: ignore[arg-type]
    )

    if member is None or member.status not in ("active", "pending_invitation"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this company.",
        )

    return member


def get_actor_role_rank(
    current_member: CompanyMember = Depends(get_current_company_member),
    db: Session = Depends(get_db),
) -> int:
    """Return the rank of the current member's role.

    Used for rank-based authorization checks.
    """
    role_repo = RoleRepository(db)
    role = role_repo.get_by_id_or_none(
        id=current_member.role_id, company_id=current_member.company_id
    )
    if role is None:
        return 0
    return role.rank


def require_rank(minimum_rank: int):
    """Return a FastAPI dependency that enforces a minimum role rank.

    Usage::

        @router.patch("/{member_id}", dependencies=[Depends(require_rank(ADMIN_RANK))])

    Raises:
        HTTPException 403: If the actor's rank is below the minimum.
    """

    def _check(actor_rank: int = Depends(get_actor_role_rank)) -> int:
        if actor_rank < minimum_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have sufficient rank to perform this action.",
            )
        return actor_rank

    return _check


# ---------------------------------------------------------------------------
# Profile / Preference service factories
# ---------------------------------------------------------------------------


def get_profile_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProfileService:
    """Wire and return a ``ProfileService`` for the current request.

    Uses a null storage stub; override in production to inject
    a real ``S3StorageClient``.
    """
    return ProfileService(
        db=db,
        user_repo=UserRepository(db),
        storage=_NullStorageClient(),
        settings=settings,
    )


def get_preference_service(
    db: Session = Depends(get_db),
) -> PreferenceService:
    """Wire and return a ``PreferenceService`` for the current request."""
    return PreferenceService(
        db=db,
        pref_repo=UserPreferenceRepository(db),
    )

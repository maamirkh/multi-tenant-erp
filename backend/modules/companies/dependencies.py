"""FastAPI dependency injection functions for the companies module.

All DI factories in this module are synchronous — matching the sync
``Session`` / ``get_db`` pattern used throughout the backend.

Phase 1 RBAC simplification
─────────────────────────────
Until Epic 4 introduces the ``company_members`` table, membership is
determined by a single rule:

    A user is a member of a company if and only if
    ``company.owner_id == current_user.user_id``.

SuperAdmin status is represented by ``"super_admin"`` appearing in
``current_user.roles``.

# TODO Epic-4: replace with company_members table lookup for membership
# TODO Epic-4: replace roles list check with RBAC table for super_admin

Spec reference: Phase 8, §7 Authorization.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.events.outbox import EventOutboxRepository
from modules.companies.exceptions import CompanyNotFoundError
from modules.companies.models.company import Company
from modules.companies.repositories.company_address_repository import (
    CompanyAddressRepository,
)
from modules.companies.repositories.company_audit_log_repository import (
    CompanyAuditLogRepository,
)
from modules.companies.repositories.company_repository import CompanyRepository
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.companies.services.company_logo_service import CompanyLogoService
from modules.companies.services.company_service import CompanyService
from modules.companies.services.company_settings_service import CompanySettingsService
from modules.platform_admin.services.company_access_service import (
    assert_company_access_allowed,
)

logger = logging.getLogger(__name__)

# Role identifiers — kept as constants so future Epic 4 can centralise them.
_ROLE_SUPER_ADMIN = "super_admin"
_ROLE_ADMIN = "admin"
_ROLE_OWNER = "owner"
_ROLES_ADMIN_AND_ABOVE = frozenset({_ROLE_OWNER, _ROLE_ADMIN, _ROLE_SUPER_ADMIN})

# ---------------------------------------------------------------------------
# Service factory dependencies
# ---------------------------------------------------------------------------


def get_company_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CompanyService:
    """Wire and return a ``CompanyService`` for the current request.

    All repositories share the same ``db`` session so that their writes
    are batched within the same connection.
    """
    company_repo = CompanyRepository(db)
    address_repo = CompanyAddressRepository(db)
    audit_log_repo = CompanyAuditLogRepository(db)
    outbox_repo = EventOutboxRepository(db)
    audit_service = CompanyAuditService(db)
    settings_service = CompanySettingsService()
    return CompanyService(
        db=db,
        company_repo=company_repo,
        address_repo=address_repo,
        audit_log_repo=audit_log_repo,
        outbox_repo=outbox_repo,
        audit_service=audit_service,
        settings_service=settings_service,
    )


def get_company_audit_service(
    db: Session = Depends(get_db),
) -> CompanyAuditService:
    """Return a ``CompanyAuditService`` bound to the current request session."""
    return CompanyAuditService(db)


def get_company_logo_service(
    settings: Settings = Depends(get_settings),
) -> CompanyLogoService:
    """Return a ``CompanyLogoService`` with a stub storage backend.

    In production, override this dependency (or ``get_storage``) to inject
    the real ``S3StorageClient``.  The stub raises ``NotImplementedError``
    on upload so mis-configuration is caught at call time, not at startup.
    """
    return CompanyLogoService(
        storage=_NullStorageClient(),
        max_bytes=settings.COMPANY_LOGO_MAX_BYTES,
    )


# ---------------------------------------------------------------------------
# Company access dependency
# ---------------------------------------------------------------------------


def get_current_company(
    company_id: UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
    db: Session = Depends(get_db),
) -> Company:
    """Resolve and authorise access to a company for the current request.

    Lookup order:
    1. Fetch raw company record (any status) via ``service._company_repo``.
    2. If not found → ``CompanyNotFoundError`` (HTTP 404).
    3. ``assert_company_access_allowed`` (Epic 9A, T084): if suspended →
       ``CompanySuspendedError`` (HTTP 403); if deleted →
       ``CompanyNotFoundError`` (HTTP 404) — byte-identical to the manual
       checks this replaces; additionally denies a request authenticated
       by a pre-suspension ``Session`` even after reactivation (ADR-6).
    4. Membership check (owner only until Epic 4 adds ``company_members``).

    # TODO Epic-4: replace with company_members table lookup
    """
    company = service._company_repo.get_by_id(company_id)

    if company is None:
        raise CompanyNotFoundError()

    assert_company_access_allowed(db, company_id, current_user.session_id)

    # TODO Epic-4: replace with company_members table lookup
    is_owner = company.owner_id == current_user.user_id
    is_super_admin = _ROLE_SUPER_ADMIN in current_user.roles

    if not is_owner and not is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you are not a member of this company.",
        )

    return company


# ---------------------------------------------------------------------------
# Role-guard dependency factories
# ---------------------------------------------------------------------------


def require_role(allowed_roles: list[str]) -> Callable[..., CurrentUser]:
    """Return a dependency that enforces at least one of ``allowed_roles``.

    Raises ``HTTP 403`` if ``current_user.roles`` has no overlap with
    ``allowed_roles``.

    Usage::

        @router.get("/admin-only")
        def admin_endpoint(
            _: CurrentUser = Depends(require_role(["admin", "super_admin"]))
        ):
            ...
    """

    def _guard(
        current_user: CurrentUser = Depends(require_authenticated),
    ) -> CurrentUser:
        if not any(r in current_user.roles for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles is required: {allowed_roles}.",
            )
        return current_user

    return _guard


def require_owner() -> Callable[..., Company]:
    """Return a dependency that allows only the company owner or super_admin.

    Requires ``get_current_company`` to have already resolved the company.

    # TODO Epic-4: replace ownership check with company_members role lookup
    """

    def _guard(
        company: Company = Depends(get_current_company),
        current_user: CurrentUser = Depends(require_authenticated),
    ) -> Company:
        is_owner = company.owner_id == current_user.user_id
        is_super_admin = _ROLE_SUPER_ADMIN in current_user.roles
        if not is_owner and not is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company owner access required.",
            )
        return company

    return _guard


def require_admin_or_above() -> Callable[..., Company]:
    """Return a dependency that allows owner, admin, or super_admin.

    # TODO Epic-4: replace with company_members role lookup
    """

    def _guard(
        company: Company = Depends(get_current_company),
        current_user: CurrentUser = Depends(require_authenticated),
    ) -> Company:
        is_owner = company.owner_id == current_user.user_id
        has_admin_role = any(r in current_user.roles for r in _ROLES_ADMIN_AND_ABOVE)
        if not is_owner and not has_admin_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required.",
            )
        return company

    return _guard


def require_super_admin() -> Callable[..., CurrentUser]:
    """Return a dependency that restricts access to super_admin only.

    # TODO Epic-4: replace with RBAC table super_admin check
    """

    def _guard(
        current_user: CurrentUser = Depends(require_authenticated),
    ) -> CurrentUser:
        if _ROLE_SUPER_ADMIN not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="SuperAdmin access required.",
            )
        return current_user

    return _guard


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _NullStorageClient:
    """No-op storage backend used when S3 is not configured.

    ``upload()`` raises ``NotImplementedError`` so accidental calls in
    non-storage environments are caught at call time, not silently swallowed.
    """

    def upload(self, file: Any, key: str) -> str:  # noqa: ANN401
        raise NotImplementedError(
            "Storage backend not configured. "
            "Override get_company_logo_service() with a real S3StorageClient."
        )

    def delete(self, key: str) -> None:
        pass

    def get_url(self, key: str) -> str:
        return ""

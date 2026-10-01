"""FastAPI dependency injection functions for the Platform Administration
module.

``get_current_platform_admin()`` (T052) is the Platform equivalent of
``core.auth.dependencies.get_current_user()`` — but, unlike the tenant
path, it checks session revocation from day one (plan.md §10.4): tenant
sessions have a known, documented gap where a revoked session's
still-unexpired access token keeps working; Platform sessions do not
inherit that gap.

Makes no change to ``get_current_user()``, ``CurrentUser``, or the tenant
JWT payload — the tenant/Platform boundary is structural (distinct `typ`
claim, and a Platform token's `sub` is a `PlatformAdministrator.id`, which
does not correspond to any `users.id` row, so `get_current_user()` already
rejects a Platform token on its own, unmodified).

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend (plan.md §4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.exceptions.base import UnauthorizedException
from core.logging.setup import REQUEST_ID_CONTEXT
from modules.platform_admin.exceptions import (
    CapabilityNotEntitledError,
    InsufficientPlatformPermissionError,
    PlatformSessionInvalidError,
)
from modules.platform_admin.repositories.override_repository import OverrideRepository
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.repositories.platform_session_repository import (
    PlatformSessionRepository,
)
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    EffectiveEntitlement,
    PlatformEntitlementService,
)
from modules.platform_admin.services.override_service import OverrideService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService

logger = logging.getLogger(__name__)


@dataclass
class PlatformPrincipal:
    """The authenticated Platform Administrator principal for this request."""

    platform_administrator_id: UUID
    session_id: UUID
    user_id: UUID


def get_current_platform_admin(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PlatformPrincipal:
    """Extract and validate a Platform access token from the Authorization
    header.

    Raises:
        UnauthorizedException: Missing/malformed header, or the bearer
            token is empty.
        PlatformSessionInvalidError: `typ` is not `platform_access`, the
            `PlatformSession` is revoked or not found, or the
            `PlatformAdministrator` is not found or inactive.
        TokenExpiredException: Token `exp` claim is in the past.
        AuthenticationException: Signature/claims otherwise invalid.
    """
    authorization: str | None = request.headers.get("Authorization")

    if not authorization:
        raise UnauthorizedException(message="Platform authentication required.")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedException(
            message="Invalid Authorization header format. Expected 'Bearer <token>'."
        )

    raw_token = parts[1].strip()
    if not raw_token:
        raise UnauthorizedException(message="Bearer token is empty.")

    jwt_svc = PlatformJwtService(settings)
    claims = jwt_svc.decode_token(raw_token)

    if claims.get("typ") != "platform_access":
        raise PlatformSessionInvalidError(
            message="Token is not a valid Platform access token."
        )

    platform_administrator_id = jwt_svc.extract_platform_administrator_id(claims)
    session_id = jwt_svc.extract_session_id(claims)

    session_repo = PlatformSessionRepository(db)
    session = session_repo.get_by_id(session_id)
    if session is None or session.is_revoked:
        raise PlatformSessionInvalidError(
            message="Platform session has been revoked or no longer exists."
        )

    admin_repo = PlatformAdministratorRepository(db)
    administrator = admin_repo.get_by_id(platform_administrator_id)
    if administrator is None or not administrator.is_active:
        raise PlatformSessionInvalidError(
            message="Platform Administrator account is not active."
        )

    return PlatformPrincipal(
        platform_administrator_id=administrator.id,
        session_id=session.id,
        user_id=administrator.user_id,
    )


_PERMISSIONS_CACHE_ATTR = "_platform_effective_permissions_cache"
_ENTITLEMENT_CACHE_ATTR = "_platform_entitlement_cache"


def get_effective_permissions_cached(
    request: Request, principal: PlatformPrincipal, db: Session
) -> frozenset[str]:
    """Request-scoped memoisation (T213, plan.md §31) of
    ``PlatformRbacRepository.get_effective_permissions()`` — several
    dependencies/handlers within one request need the same
    administrator's effective permission set (e.g.
    ``require_platform_permission`` itself, and the dashboard route's
    own per-widget gating, ``router.py``'s ``get_dashboard``). Caches on
    ``request.state`` only — a fresh dict every request, never a
    process-level cache, so there is no invalidation/consistency
    concern across requests.
    """
    cache: dict[UUID, frozenset[str]] | None = getattr(
        request.state, _PERMISSIONS_CACHE_ATTR, None
    )
    if cache is None:
        cache = {}
        setattr(request.state, _PERMISSIONS_CACHE_ATTR, cache)

    cached = cache.get(principal.platform_administrator_id)
    if cached is not None:
        return cached

    effective = PlatformRbacRepository(db).get_effective_permissions(
        principal.platform_administrator_id
    )
    cache[principal.platform_administrator_id] = effective
    return effective


def require_platform_permission(code: str) -> Callable[..., PlatformPrincipal]:
    """Dependency factory: the single server-side enforcement primitive
    every sensitive Platform route uses (BR-9A-008). Holding one
    permission never implies another — this checks exactly *code*,
    resolved fresh from the database (T063, FR-9A-221), never from a
    token claim.

    Usage::

        @router.get("/administrators", dependencies=[
            Depends(require_platform_permission("platform.admins.read"))
        ])
    """

    def _dependency(
        request: Request,
        principal: PlatformPrincipal = Depends(get_current_platform_admin),
        db: Session = Depends(get_db),
    ) -> PlatformPrincipal:
        effective = get_effective_permissions_cached(request, principal, db)
        if code not in effective:
            logger.warning(
                "Platform permission denied",
                extra={
                    "request_id": REQUEST_ID_CONTEXT.get("-"),
                    "platform_administrator_id": str(
                        principal.platform_administrator_id
                    ),
                    "required_permission": code,
                },
            )
            raise InsufficientPlatformPermissionError(
                message=f"Missing required Platform permission: {code}."
            )
        return principal

    # Exposed for the contract-conformance test (T177) — lets it verify
    # each route's *wired* permission matches the contract's declared
    # `x-permission` without duplicating a second permission map by hand.
    _dependency.permission_code = code  # type: ignore[attr-defined]

    return _dependency


def require_capability_entitled(capability_key: str) -> Callable[..., None]:
    """Dependency factory: the **point-of-use** Plan Entitlement ceiling
    (T122, ADR-3, plan.md §13.1 Correction 1). Mounted alongside
    ``get_current_company_member`` on every entitled module's router
    include — the same single place the repository already centralises
    per-module request gating (§3.10), so every endpoint in that module
    is covered automatically, with no per-endpoint annotation to forget.

    Resolves fresh per request via the single authoritative
    ``PlatformEntitlementService`` (never cached, FR-9A-170) and raises
    ``CapabilityNotEntitledError`` (403) when the effective result is
    Unavailable. This is the *primary* runtime enforcement point — a
    module's own existing tenant-toggle gate (e.g. CRM's
    ``require_crm_enabled``) is a secondary guard that continues to
    honour the tenant's own choice *within* what this ceiling allows.

    Usage::

        router.include_router(
            crm_router,
            dependencies=[
                Depends(get_current_company_member),
                Depends(require_capability_entitled("crm")),
                Depends(require_crm_enabled),
            ],
        )
    """

    def _dependency(
        request: Request,
        company_id: UUID,
        db: Session = Depends(get_db),
    ) -> None:
        # Request-scoped memoisation (T213, plan.md §31) — never a
        # cross-request cache (FR-9A-170's "resolved fresh" still holds:
        # fresh per *request*, not re-resolved per *dependency call*
        # within the same request).
        cache: dict[tuple[UUID, str], EffectiveEntitlement] | None = getattr(
            request.state, _ENTITLEMENT_CACHE_ATTR, None
        )
        if cache is None:
            cache = {}
            setattr(request.state, _ENTITLEMENT_CACHE_ATTR, cache)

        cache_key = (company_id, capability_key)
        result = cache.get(cache_key)
        if result is None:
            override_service = OverrideService(
                db=db,
                repo=OverrideRepository(db),
                audit=PlatformAuditService(db, PlatformAuditRepository(db)),
            )
            service = PlatformEntitlementService(
                db=db,
                plan_repo=PlanRepository(db),
                subscription_repo=SubscriptionRepository(db),
                override_checker=override_service,
            )
            result = service.resolve_effective_entitlement(
                company_id=company_id, capability_key=capability_key
            )
            cache[cache_key] = result

        if not result.available:
            logger.warning(
                "Platform entitlement denied",
                extra={
                    "request_id": REQUEST_ID_CONTEXT.get("-"),
                    "company_id": str(company_id),
                    "capability_key": capability_key,
                    "reason": result.reason,
                },
            )
            raise CapabilityNotEntitledError(
                message=(
                    f"The '{capability_key}' capability is not entitled under "
                    "the current plan."
                ),
                details={"capability_key": capability_key, "reason": result.reason},
            )

    return _dependency

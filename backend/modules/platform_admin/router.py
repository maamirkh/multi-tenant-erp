"""Platform Administration module API router.

Endpoints (Phase 4):
    POST /platform/auth/login    — public, per contracts/platform-admin-v1.yaml
    POST /platform/auth/refresh  — public
    POST /platform/auth/logout   — requires a valid Platform session

Endpoints (Phase 5, T068/T069):
    GET   /platform/administrators               — platform.admins.read
    POST  /platform/administrators                — platform.admins.manage
    PATCH /platform/administrators/{adminId}       — platform.admins.manage
    GET   /platform/roles                          — platform.rbac.read
    POST  /platform/roles                          — platform.rbac.manage
    POST  /platform/administrators/{adminId}/roles — platform.rbac.manage

Endpoints (Phase 7, T090):
    POST /platform/tenants/{companyId}/suspend    — platform.tenants.suspend
    POST /platform/tenants/{companyId}/reactivate — platform.tenants.reactivate

Endpoints (Phase 8, T114):
    GET   /platform/plans                          — platform.plans.read
    POST  /platform/plans                           — platform.plans.manage
    PATCH /platform/plans/{planId}                  — platform.plans.manage
    GET   /platform/tenants/{companyId}/subscription  — platform.subscriptions.read
    POST  /platform/tenants/{companyId}/subscription  — platform.subscriptions.manage

Mounted at ``/api/v1/platform`` by ``api/v1/router.py`` (T053) — without
``get_current_company_member``, since Platform is never company-scoped.

Router discipline: delegates to the service layer — no business logic in
the router (plan.md §10 API Contract Lock). Contract traceability:
operations 1-3 (public `/auth/*`, no `x-permission`), operations 20-25
(Administrator/RBAC management), the `/tenants/{companyId}/suspend` and
`/reactivate` operations, and the `/plans*`/`/tenants/{companyId}/
subscription` operations of ``platform-admin-v1.yaml``.
"""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.events.outbox import EventOutboxRepository
from core.exceptions.base import NotFoundException
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.pagination import PaginatedData, PaginatedResponse
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.dependencies import (
    PlatformPrincipal,
    get_current_platform_admin,
    require_platform_permission,
)
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
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.schemas.plan import (
    CreatePlanRequest,
    PlanResponse,
    UpdatePlanRequest,
)
from modules.platform_admin.schemas.platform_administrator import (
    CreatePlatformAdministratorRequest,
    PlatformAdministratorResponse,
    UpdatePlatformAdministratorRequest,
)
from modules.platform_admin.schemas.platform_auth import (
    PlatformLoginRequest,
    PlatformLoginResponse,
    PlatformRefreshTokenRequest,
    PlatformRefreshTokenResponse,
)
from modules.platform_admin.schemas.platform_rbac import (
    AssignRoleRequest,
    CreateOrUpdateRoleRequest,
    RoleAssignmentResponse,
    RoleResponse,
)
from modules.platform_admin.schemas.subscription import (
    AssignSubscriptionRequest,
    SubscriptionHistoryResponse,
    SubscriptionResponse,
)
from modules.platform_admin.schemas.tenant_lifecycle import (
    TenantLifecycleActionRequest,
    TenantLifecycleResponse,
)
from modules.platform_admin.services.plan_service import PlanService
from modules.platform_admin.services.platform_administrator_service import (
    PlatformAdministratorService,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_auth_service import PlatformAuthService
from modules.platform_admin.services.platform_rbac_service import PlatformRbacService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService
from modules.platform_admin.services.tenant_lifecycle_service import (
    TenantLifecycleService,
)

router = APIRouter(prefix="/auth", tags=["Platform Authentication"])
admin_router = APIRouter(tags=["Platform Administrators"])
rbac_router = APIRouter(tags=["Platform RBAC"])
tenant_router = APIRouter(tags=["Platform Tenants"])
plan_router = APIRouter(tags=["Platform Plans"])


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


def _platform_auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PlatformAuthService:
    return PlatformAuthService(db=db, settings=settings)


@router.post(
    "/login",
    response_model=StandardResponse[PlatformLoginResponse],
    status_code=status.HTTP_200_OK,
    summary="Platform Administrator login",
    description=(
        "Authenticate with email and password against the same User "
        "credentials, then require an active PlatformAdministrator. "
        "Returns a Platform-typed access/refresh token pair."
    ),
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials or no active PlatformAdministrator"},
        422: {"description": "Validation error"},
    },
)
async def login(
    request: Request,
    payload: PlatformLoginRequest,
    svc: PlatformAuthService = Depends(_platform_auth_service),
) -> StandardResponse[PlatformLoginResponse]:
    """Authenticate a Platform Administrator and issue Platform tokens."""
    result = svc.login(
        email=str(payload.email), password=payload.password, request=request
    )
    return StandardResponse(
        data=PlatformLoginResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        ),
        message="Login successful.",
        meta=_meta(request),
    )


@router.post(
    "/refresh",
    response_model=StandardResponse[PlatformRefreshTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Rotate Platform refresh token",
    description="Exchange a valid Platform refresh token for a new access/refresh pair.",
    responses={
        200: {"description": "Token refreshed"},
        401: {"description": "Invalid, expired, or revoked refresh token/session"},
    },
)
async def refresh_token(
    request: Request,
    payload: PlatformRefreshTokenRequest,
    svc: PlatformAuthService = Depends(_platform_auth_service),
) -> StandardResponse[PlatformRefreshTokenResponse]:
    """Rotate a Platform refresh token and issue a new access token."""
    result = svc.refresh(raw_refresh_token=payload.refresh_token, request=request)
    return StandardResponse(
        data=PlatformRefreshTokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_in=result.expires_in,
        ),
        message="Token refreshed.",
        meta=_meta(request),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Platform Administrator logout",
    description="Revoke the current Platform session and all its refresh tokens.",
    responses={
        204: {"description": "No Content"},
        401: {"description": "Not authenticated"},
    },
)
async def logout(
    request: Request,
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlatformAuthService = Depends(_platform_auth_service),
) -> None:
    """Revoke the current Platform session and all its refresh tokens.

    Per contracts/platform-admin-v1.yaml, this operation returns
    204 No Content — unlike the tenant /auth/logout (200 + body), which
    the Platform contract deliberately does not mirror here.
    """
    svc.logout(session_id=current.session_id, request=request)


# ---------------------------------------------------------------------------
# Platform Administrator management (T068) — operations 20-22
# ---------------------------------------------------------------------------


def _administrator_service(
    db: Session = Depends(get_db),
) -> PlatformAdministratorService:
    audit = PlatformAuditService(db, PlatformAuditRepository(db))
    return PlatformAdministratorService(
        db=db,
        repo=PlatformAdministratorRepository(db),
        audit=audit,
        # T054's completed session-revoking deactivation: PlatformSessionRepository
        # already implements the SessionRevoker protocol structurally
        # (revoke_all_for_administrator(platform_administrator_id)).
        session_revoker=PlatformSessionRepository(db),
    )


@admin_router.get(
    "/administrators",
    response_model=PaginatedResponse[PlatformAdministratorResponse],
    summary="List Platform Administrator accounts",
    dependencies=[Depends(require_platform_permission("platform.admins.read"))],
)
async def list_administrators(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PlatformAdministratorResponse]:
    repo = PlatformAdministratorRepository(db)
    items, total = repo.list_paginated(offset=(page - 1) * page_size, limit=page_size)
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[PlatformAdministratorResponse.model_validate(a) for a in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} Platform Administrator(s) found.",
        meta=_meta(request),
    )


@admin_router.post(
    "/administrators",
    response_model=StandardResponse[PlatformAdministratorResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a Platform Administrator account",
    dependencies=[Depends(require_platform_permission("platform.admins.manage"))],
    responses={
        404: {"description": "User not found"},
        409: {"description": "A Platform Administrator already exists for this user"},
    },
)
async def create_administrator(
    request: Request,
    payload: CreatePlatformAdministratorRequest,
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlatformAdministratorService = Depends(_administrator_service),
) -> StandardResponse[PlatformAdministratorResponse]:
    administrator = svc.create(
        user_id=payload.user_id,
        actor_platform_administrator_id=current.platform_administrator_id,
    )
    return StandardResponse(
        data=PlatformAdministratorResponse.model_validate(administrator),
        message="Platform Administrator created.",
        meta=_meta(request),
    )


@admin_router.patch(
    "/administrators/{adminId}",
    response_model=StandardResponse[PlatformAdministratorResponse],
    summary="Activate/deactivate a Platform Administrator",
    description="Deactivation immediately revokes all active Platform sessions.",
    dependencies=[Depends(require_platform_permission("platform.admins.manage"))],
    responses={
        409: {"description": "Cannot deactivate the last active Platform Owner"}
    },
)
async def update_administrator(
    request: Request,
    payload: UpdatePlatformAdministratorRequest,
    adminId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlatformAdministratorService = Depends(_administrator_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PlatformAdministratorResponse]:
    repo = PlatformAdministratorRepository(db)
    administrator = repo.get_by_id(adminId)
    if administrator is None:
        raise NotFoundException(message="Platform Administrator not found.")

    if payload.is_active:
        administrator = svc.activate(
            administrator,
            actor_platform_administrator_id=current.platform_administrator_id,
            reason=payload.reason,
        )
        message = "Platform Administrator activated."
    else:
        rbac_service = PlatformRbacService(
            db=db,
            repo=PlatformRbacRepository(db),
            admin_repo=repo,
            audit=PlatformAuditService(db, PlatformAuditRepository(db)),
        )
        rbac_service.assert_not_last_owner_removal(
            administrator.id,
            actor_platform_administrator_id=current.platform_administrator_id,
            reason=payload.reason,
        )
        administrator = svc.deactivate(
            administrator,
            actor_platform_administrator_id=current.platform_administrator_id,
            reason=payload.reason,
        )
        message = "Platform Administrator deactivated; active sessions revoked."

    return StandardResponse(
        data=PlatformAdministratorResponse.model_validate(administrator),
        message=message,
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Platform RBAC management (T069) — operations 23-25
# ---------------------------------------------------------------------------


def _rbac_service(db: Session = Depends(get_db)) -> PlatformRbacService:
    audit = PlatformAuditService(db, PlatformAuditRepository(db))
    return PlatformRbacService(
        db=db,
        repo=PlatformRbacRepository(db),
        admin_repo=PlatformAdministratorRepository(db),
        audit=audit,
    )


def _role_response(role, repo: PlatformRbacRepository) -> RoleResponse:
    codes = sorted(repo.get_role_permission_codes(role.id))
    return RoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        permission_codes=codes,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@rbac_router.get(
    "/roles",
    response_model=PaginatedResponse[RoleResponse],
    summary="List Platform Roles and their permission bundles",
    dependencies=[Depends(require_platform_permission("platform.rbac.read"))],
)
async def list_roles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RoleResponse]:
    repo = PlatformRbacRepository(db)
    roles, total = repo.list_roles(offset=(page - 1) * page_size, limit=page_size)
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[_role_response(r, repo) for r in roles],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} Platform Role(s) found.",
        meta=_meta(request),
    )


@rbac_router.post(
    "/roles",
    response_model=StandardResponse[RoleResponse],
    summary="Create/update a Platform Role's permission bundle",
    dependencies=[Depends(require_platform_permission("platform.rbac.manage"))],
    responses={422: {"description": "One or more permission codes are not recognised"}},
)
async def create_or_update_role(
    request: Request,
    payload: CreateOrUpdateRoleRequest,
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlatformRbacService = Depends(_rbac_service),
    db: Session = Depends(get_db),
) -> StandardResponse[RoleResponse]:
    role = svc.create_or_update_role(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        permission_codes=set(payload.permission_codes),
        actor_platform_administrator_id=current.platform_administrator_id,
        reason=payload.reason,
    )
    return StandardResponse(
        data=_role_response(role, PlatformRbacRepository(db)),
        message="Platform Role saved.",
        meta=_meta(request),
    )


@rbac_router.post(
    "/administrators/{adminId}/roles",
    response_model=StandardResponse[RoleAssignmentResponse],
    summary="Assign a Platform Role to an administrator",
    dependencies=[Depends(require_platform_permission("platform.rbac.manage"))],
    responses={
        403: {"description": "Self-escalation rejected"},
        404: {"description": "Administrator or Role not found"},
        409: {"description": "Last-Platform-Owner-removal rejected"},
    },
)
async def assign_role(
    request: Request,
    payload: AssignRoleRequest,
    adminId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlatformRbacService = Depends(_rbac_service),
    db: Session = Depends(get_db),
) -> StandardResponse[RoleAssignmentResponse]:
    if PlatformAdministratorRepository(db).get_by_id(adminId) is None:
        raise NotFoundException(message="Platform Administrator not found.")
    if PlatformRbacRepository(db).get_role_by_id(payload.role_id) is None:
        raise NotFoundException(message="Platform Role not found.")

    assignment = svc.assign_role(
        platform_administrator_id=adminId,
        role_id=payload.role_id,
        actor_platform_administrator_id=current.platform_administrator_id,
        reason=payload.reason,
    )
    return StandardResponse(
        data=RoleAssignmentResponse.model_validate(assignment),
        message="Platform Role assigned.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Tenant lifecycle (T090)
# ---------------------------------------------------------------------------


def _tenant_lifecycle_service(db: Session = Depends(get_db)) -> TenantLifecycleService:
    return TenantLifecycleService(
        db=db,
        company_repo=CompanyRepository(db),
        outbox_repo=EventOutboxRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


@tenant_router.post(
    "/tenants/{companyId}/suspend",
    response_model=StandardResponse[TenantLifecycleResponse],
    summary="Suspend a tenant (active/inactive -> suspended)",
    dependencies=[Depends(require_platform_permission("platform.tenants.suspend"))],
    responses={
        404: {"description": "Company not found"},
        409: {"description": "Tenant already suspended (Edge Case #1)"},
    },
)
async def suspend_tenant(
    request: Request,
    payload: TenantLifecycleActionRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: TenantLifecycleService = Depends(_tenant_lifecycle_service),
) -> StandardResponse[TenantLifecycleResponse]:
    company = svc.suspend(
        company_id=companyId,
        actor_platform_administrator_id=current.platform_administrator_id,
        reason=payload.reason,
    )
    return StandardResponse(
        data=TenantLifecycleResponse.model_validate(company),
        message="Tenant suspended.",
        meta=_meta(request),
    )


@tenant_router.post(
    "/tenants/{companyId}/reactivate",
    response_model=StandardResponse[TenantLifecycleResponse],
    summary="Reactivate a tenant (suspended -> its recorded pre-suspension status)",
    dependencies=[Depends(require_platform_permission("platform.tenants.reactivate"))],
    responses={
        404: {"description": "Company not found"},
        409: {"description": "Tenant not currently suspended (Edge Case #2)"},
    },
)
async def reactivate_tenant(
    request: Request,
    payload: TenantLifecycleActionRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: TenantLifecycleService = Depends(_tenant_lifecycle_service),
) -> StandardResponse[TenantLifecycleResponse]:
    company = svc.reactivate(
        company_id=companyId,
        actor_platform_administrator_id=current.platform_administrator_id,
        reason=payload.reason,
    )
    return StandardResponse(
        data=TenantLifecycleResponse.model_validate(company),
        message="Tenant reactivated.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Plans & Subscriptions (T114)
# ---------------------------------------------------------------------------


def _plan_service(db: Session = Depends(get_db)) -> PlanService:
    return PlanService(
        db=db,
        repo=PlanRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _subscription_service(db: Session = Depends(get_db)) -> SubscriptionService:
    return SubscriptionService(
        db=db,
        repo=SubscriptionRepository(db),
        company_repo=CompanyRepository(db),
        quota_service=QuotaService(QuotaRepository(db)),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _plan_response(plan, repo: PlanRepository) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        status=plan.status,
        description=plan.description,
        is_commercially_available=plan.is_commercially_available,
        billing_cycle_metadata=plan.billing_cycle_metadata,
        pricing_metadata=plan.pricing_metadata,
        capability_map=repo.get_capability_map(plan.id),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@plan_router.get(
    "/plans",
    response_model=PaginatedResponse[PlanResponse],
    summary="List plans",
    dependencies=[Depends(require_platform_permission("platform.plans.read"))],
)
async def list_plans(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PlanResponse]:
    repo = PlanRepository(db)
    items, total = repo.list_paginated(
        status=status_filter, offset=(page - 1) * page_size, limit=page_size
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[_plan_response(p, repo) for p in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} Plan(s) found.",
        meta=_meta(request),
    )


@plan_router.post(
    "/plans",
    response_model=StandardResponse[PlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a plan (draft)",
    dependencies=[Depends(require_platform_permission("platform.plans.manage"))],
)
async def create_plan(
    request: Request,
    payload: CreatePlanRequest,
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlanService = Depends(_plan_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PlanResponse]:
    plan = svc.create(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        billing_cycle_metadata=payload.billing_cycle_metadata,
        pricing_metadata=payload.pricing_metadata,
        capability_map=payload.capability_map,
        actor_platform_administrator_id=current.platform_administrator_id,
        reason=payload.reason,
    )
    return StandardResponse(
        data=_plan_response(plan, PlanRepository(db)),
        message="Plan created.",
        meta=_meta(request),
    )


@plan_router.patch(
    "/plans/{planId}",
    response_model=StandardResponse[PlanResponse],
    summary="Update/publish/retire a plan",
    dependencies=[Depends(require_platform_permission("platform.plans.manage"))],
    responses={
        404: {"description": "Plan not found"},
        409: {"description": "Requested status transition is not permitted"},
    },
)
async def update_plan(
    request: Request,
    payload: UpdatePlanRequest,
    planId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: PlanService = Depends(_plan_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PlanResponse]:
    repo = PlanRepository(db)
    plan = repo.get_by_id(planId)
    if plan is None:
        raise NotFoundException(message="Plan not found.")

    if payload.action == "publish":
        plan = svc.publish(
            plan,
            actor_platform_administrator_id=current.platform_administrator_id,
            reason=payload.reason,
        )
        message = "Plan published."
    elif payload.action == "retire":
        plan = svc.retire(
            plan,
            actor_platform_administrator_id=current.platform_administrator_id,
            reason=payload.reason,
        )
        message = "Plan retired."
    else:
        plan = svc.update(
            plan,
            name=payload.name,
            description=payload.description,
            is_commercially_available=payload.is_commercially_available,
            billing_cycle_metadata=payload.billing_cycle_metadata,
            pricing_metadata=payload.pricing_metadata,
            capability_map=payload.capability_map,
            actor_platform_administrator_id=current.platform_administrator_id,
            reason=payload.reason,
        )
        message = "Plan updated."

    return StandardResponse(
        data=_plan_response(plan, repo),
        message=message,
        meta=_meta(request),
    )


@tenant_router.get(
    "/tenants/{companyId}/subscription",
    response_model=StandardResponse[SubscriptionHistoryResponse],
    summary="View a tenant's current subscription and history",
    dependencies=[Depends(require_platform_permission("platform.subscriptions.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_subscription(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    db: Session = Depends(get_db),
) -> StandardResponse[SubscriptionHistoryResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    repo = SubscriptionRepository(db)
    history = repo.list_for_company(companyId)
    current_subscription = next((s for s in history if s.status == "active"), None)
    return StandardResponse(
        data=SubscriptionHistoryResponse(
            current=(
                SubscriptionResponse.model_validate(current_subscription)
                if current_subscription
                else None
            ),
            history=[SubscriptionResponse.model_validate(s) for s in history],
        ),
        message=(
            f"{len(history)} Subscription record(s) found."
            if history
            else "No Subscription history for this tenant."
        ),
        meta=_meta(request),
    )


@tenant_router.post(
    "/tenants/{companyId}/subscription",
    response_model=StandardResponse[SubscriptionResponse],
    summary="Assign/change a tenant's plan (surfaces usage-conflict per FR-9A-165)",
    dependencies=[
        Depends(require_platform_permission("platform.subscriptions.manage"))
    ],
    responses={
        404: {"description": "Company or Plan not found"},
        409: {"description": "Usage-conflict requiring explicit acknowledgment"},
    },
)
async def assign_subscription(
    request: Request,
    payload: AssignSubscriptionRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: SubscriptionService = Depends(_subscription_service),
    db: Session = Depends(get_db),
) -> StandardResponse[SubscriptionResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")
    if PlanRepository(db).get_by_id(payload.plan_id) is None:
        raise NotFoundException(message="Plan not found.")

    subscription = svc.assign_or_change(
        company_id=companyId,
        plan_id=payload.plan_id,
        effective_date=payload.effective_date,
        end_date=payload.end_date,
        actor_platform_administrator_id=current.platform_administrator_id,
        reason=payload.reason,
        acknowledged=payload.acknowledged,
    )
    return StandardResponse(
        data=SubscriptionResponse.model_validate(subscription),
        message="Subscription assigned.",
        meta=_meta(request),
    )

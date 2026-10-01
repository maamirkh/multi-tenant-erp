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
from datetime import datetime
from typing import Literal
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
    get_effective_permissions_cached,
    require_platform_permission,
)
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_rbac import PlatformRole
from modules.platform_admin.repositories.ai_credit_repository import AiCreditRepository
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
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
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.repositories.support_access_repository import (
    SupportAccessRepository,
)
from modules.platform_admin.repositories.usage_repository import UsageRepository
from modules.platform_admin.schemas.ai_credit import (
    AdjustAiCreditsRequest,
    AiCreditLedgerEntryResponse,
    TenantAiCreditsResponse,
)
from modules.platform_admin.schemas.dashboard import (
    DashboardResponse,
    DashboardWidgetResponse,
)
from modules.platform_admin.schemas.entitlement import (
    CapabilityEntitlementResponse,
    TenantEntitlementsResponse,
)
from modules.platform_admin.schemas.health import PlatformHealthResponse
from modules.platform_admin.schemas.override import (
    EntitlementOverrideResponse,
    GrantEntitlementOverrideRequest,
    GrantQuotaOverrideRequest,
    QuotaOverrideResponse,
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
from modules.platform_admin.schemas.quota import (
    QuotaStatusResponse,
    TenantQuotasResponse,
)
from modules.platform_admin.schemas.subscription import (
    AssignSubscriptionRequest,
    SubscriptionHistoryResponse,
    SubscriptionResponse,
)
from modules.platform_admin.schemas.support_access import (
    InitiateSupportAccessRequest,
    SupportAccessGrantResponse,
)
from modules.platform_admin.schemas.tenant_directory import (
    AuditEventSummaryResponse,
    LifecycleEventResponse,
    PlanSummaryResponse,
    TenantDetailResponse,
    TenantLifecycleHistoryResponse,
    TenantSummaryResponse,
)
from modules.platform_admin.schemas.tenant_lifecycle import (
    TenantLifecycleActionRequest,
    TenantLifecycleResponse,
)
from modules.platform_admin.schemas.usage import (
    TenantUsageResponse,
    UsageRecordResponse,
)
from modules.platform_admin.services.ai_credit_service import AiCreditService
from modules.platform_admin.services.dashboard_service import (
    DashboardService,
    DashboardWidget,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.platform_admin.services.health_service import HealthService
from modules.platform_admin.services.override_service import OverrideService
from modules.platform_admin.services.plan_service import PlanService
from modules.platform_admin.services.platform_administrator_service import (
    PlatformAdministratorService,
)
from modules.platform_admin.services.platform_audit_query_service import (
    PlatformAuditQueryService,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_auth_service import PlatformAuthService
from modules.platform_admin.services.platform_rbac_service import PlatformRbacService
from modules.platform_admin.services.quota_admin_service import QuotaAdminService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService
from modules.platform_admin.services.support_access_service import (
    SupportAccessService,
)
from modules.platform_admin.services.tenant_directory_service import (
    TenantDetail,
    TenantDirectoryService,
)
from modules.platform_admin.services.tenant_lifecycle_service import (
    TenantLifecycleService,
)
from modules.platform_admin.services.usage_service import current_month_period

router = APIRouter(prefix="/auth", tags=["Platform Authentication"])
admin_router = APIRouter(tags=["Platform Administrators"])
rbac_router = APIRouter(tags=["Platform RBAC"])
tenant_router = APIRouter(tags=["Platform Tenants"])
support_access_router = APIRouter(tags=["Platform Support Access"])
plan_router = APIRouter(tags=["Platform Plans"])
audit_router = APIRouter(tags=["Platform Audit"])
dashboard_router = APIRouter(tags=["Platform Dashboard"])
health_router = APIRouter(tags=["Platform Health"])


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


def _role_response(role: PlatformRole, repo: PlatformRbacRepository) -> RoleResponse:
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


def _plan_response(plan: Plan, repo: PlanRepository) -> PlanResponse:
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


# ---------------------------------------------------------------------------
# Entitlements (T123) — UX-only read; the mount-level
# require_capability_entitled dependency (T122) is the security boundary.
# ---------------------------------------------------------------------------


@tenant_router.get(
    "/tenants/{companyId}/entitlements",
    response_model=StandardResponse[TenantEntitlementsResponse],
    summary="Effective entitlements for a tenant (Plan x Toggle x Override)",
    dependencies=[Depends(require_platform_permission("platform.entitlements.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_tenant_entitlements(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    db: Session = Depends(get_db),
) -> StandardResponse[TenantEntitlementsResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

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
    capabilities = CapabilityRepository(db).list_all(is_active=True)
    entitlements = []
    for capability in capabilities:
        result = service.resolve_effective_entitlement(
            company_id=companyId, capability_key=capability.key
        )
        entitlements.append(
            CapabilityEntitlementResponse(
                capability_key=capability.key,
                available=result.available,
                reason=result.reason,
            )
        )
    return StandardResponse(
        data=TenantEntitlementsResponse(
            company_id=str(companyId), entitlements=entitlements
        ),
        message=f"{len(entitlements)} capability entitlement(s) resolved.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Entitlement overrides (T146/T147/T157, FR-9A-171)
# ---------------------------------------------------------------------------


def _override_service(db: Session = Depends(get_db)) -> OverrideService:
    return OverrideService(
        db=db,
        repo=OverrideRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


@tenant_router.post(
    "/tenants/{companyId}/entitlement-overrides",
    response_model=StandardResponse[EntitlementOverrideResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Grant a time-boxed (or permanent) entitlement override",
    dependencies=[
        Depends(require_platform_permission("platform.entitlements.override"))
    ],
    responses={
        404: {"description": "Company not found"},
        409: {"description": "An active override already exists for this capability"},
    },
)
async def grant_entitlement_override(
    request: Request,
    payload: GrantEntitlementOverrideRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: OverrideService = Depends(_override_service),
    db: Session = Depends(get_db),
) -> StandardResponse[EntitlementOverrideResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    override = svc.grant(
        company_id=companyId,
        capability_key=payload.capability_key,
        reason=payload.reason,
        actor_platform_administrator_id=current.platform_administrator_id,
        expires_at=payload.expires_at,
    )
    return StandardResponse(
        data=EntitlementOverrideResponse.model_validate(override),
        message="Entitlement override granted.",
        meta=_meta(request),
    )


@tenant_router.delete(
    "/tenants/{companyId}/entitlement-overrides/{overrideId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an active entitlement override",
    dependencies=[
        Depends(require_platform_permission("platform.entitlements.override"))
    ],
    responses={404: {"description": "Override not found or already inactive"}},
)
async def revoke_entitlement_override(
    overrideId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: OverrideService = Depends(_override_service),
) -> None:
    svc.revoke(
        override_id=overrideId,
        actor_platform_administrator_id=current.platform_administrator_id,
    )


# ---------------------------------------------------------------------------
# Quotas & quota overrides (T149/T152/T157)
# ---------------------------------------------------------------------------


def _quota_admin_service(db: Session = Depends(get_db)) -> QuotaAdminService:
    return QuotaAdminService(
        db=db,
        repo=QuotaRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


@tenant_router.get(
    "/tenants/{companyId}/quotas",
    response_model=StandardResponse[TenantQuotasResponse],
    summary="Effective quota status per category",
    dependencies=[Depends(require_platform_permission("platform.quotas.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_tenant_quotas(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    db: Session = Depends(get_db),
) -> StandardResponse[TenantQuotasResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    quota_repo = QuotaRepository(db)
    usage_repo = UsageRepository(db)
    quota_service = QuotaService(quota_repo)
    subscription = SubscriptionRepository(db).get_active_for_company(companyId)
    plan_id = subscription.plan_id if subscription is not None else None
    period_start, period_end = current_month_period()

    statuses = []
    for definition in quota_repo.list_definitions():
        usage_record = usage_repo.get_for_period(
            company_id=companyId,
            metric_key=definition.key,
            period_start=period_start,
            period_end=period_end,
        )
        resolution = quota_service.resolve(
            company_id=companyId,
            plan_id=plan_id,
            quota_key=definition.key,
            current_usage=usage_record.quantity if usage_record is not None else None,
        )
        statuses.append(
            QuotaStatusResponse(
                quota_key=resolution.quota_key,
                state=resolution.state.value,
                limit=resolution.limit,
                current_usage=resolution.current_usage,
                enforcement_style=resolution.enforcement_style,
            )
        )
    return StandardResponse(
        data=TenantQuotasResponse(company_id=str(companyId), quotas=statuses),
        message=f"{len(statuses)} quota categor(y/ies) resolved.",
        meta=_meta(request),
    )


@tenant_router.post(
    "/tenants/{companyId}/quota-overrides",
    response_model=StandardResponse[QuotaOverrideResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Grant a time-boxed (or permanent) quota override",
    dependencies=[Depends(require_platform_permission("platform.quotas.override"))],
    responses={
        404: {"description": "Company not found"},
        409: {"description": "An active override already exists for this quota key"},
    },
)
async def grant_quota_override(
    request: Request,
    payload: GrantQuotaOverrideRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: QuotaAdminService = Depends(_quota_admin_service),
    db: Session = Depends(get_db),
) -> StandardResponse[QuotaOverrideResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    override = svc.grant(
        company_id=companyId,
        quota_key=payload.quota_key,
        override_limit=payload.override_limit,
        reason=payload.reason,
        actor_platform_administrator_id=current.platform_administrator_id,
        expires_at=payload.expires_at,
    )
    return StandardResponse(
        data=QuotaOverrideResponse.model_validate(override),
        message="Quota override granted.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Usage (T150/T151/T152/T157)
# ---------------------------------------------------------------------------


@tenant_router.get(
    "/tenants/{companyId}/usage",
    response_model=StandardResponse[TenantUsageResponse],
    summary="Usage records for a tenant per metric/period",
    dependencies=[Depends(require_platform_permission("platform.quotas.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_tenant_usage(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    db: Session = Depends(get_db),
) -> StandardResponse[TenantUsageResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    records = UsageRepository(db).list_for_company(companyId)
    return StandardResponse(
        data=TenantUsageResponse(
            company_id=str(companyId),
            records=[UsageRecordResponse.model_validate(r) for r in records],
        ),
        message=f"{len(records)} usage record(s) found.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# AI credits (T154/T155/T157, BR-9A-026/027)
# ---------------------------------------------------------------------------


def _ai_credit_service(db: Session = Depends(get_db)) -> AiCreditService:
    return AiCreditService(
        db=db,
        repo=AiCreditRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


@tenant_router.get(
    "/tenants/{companyId}/ai-credits",
    response_model=StandardResponse[TenantAiCreditsResponse],
    summary="AI credit ledger and current balance",
    description="Empty/'not yet active' until an AI capability exists (data-model.md §19).",
    dependencies=[Depends(require_platform_permission("platform.ai_usage.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_tenant_ai_credits(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    db: Session = Depends(get_db),
) -> StandardResponse[TenantAiCreditsResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    repo = AiCreditRepository(db)
    entries = repo.list_for_company(companyId)
    balance = repo.get_balance(companyId)
    status_label = "not_yet_active" if not entries else "active"
    return StandardResponse(
        data=TenantAiCreditsResponse(
            company_id=str(companyId),
            status=status_label,
            balance=balance,
            entries=[AiCreditLedgerEntryResponse.model_validate(e) for e in entries],
        ),
        message=(
            "No AI capability is active for this tenant yet."
            if not entries
            else f"{len(entries)} AI credit ledger entry(ies) found."
        ),
        meta=_meta(request),
    )


@tenant_router.post(
    "/tenants/{companyId}/ai-credits",
    response_model=StandardResponse[AiCreditLedgerEntryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Manual AI credit adjustment",
    description="Reason required, audited (BR-9A-026/027). No AI provider is integrated.",
    dependencies=[Depends(require_platform_permission("platform.ai_credits.adjust"))],
    responses={404: {"description": "Company not found"}},
)
async def adjust_ai_credits(
    request: Request,
    payload: AdjustAiCreditsRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: AiCreditService = Depends(_ai_credit_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AiCreditLedgerEntryResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    entry = svc.adjust(
        company_id=companyId,
        delta=payload.delta,
        reason=payload.reason,
        actor_platform_administrator_id=current.platform_administrator_id,
    )
    return StandardResponse(
        data=AiCreditLedgerEntryResponse.model_validate(entry),
        message="AI credit ledger entry recorded.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Support access (T158-T162, Gate F) — time-bounded, reason-required,
# inspection-only. This module imports no business-record repository from
# any of Inventory/Purchase/Sales/Accounting/CRM (T163) — there is no
# route here that returns tenant business data at all.
# ---------------------------------------------------------------------------


def _support_access_service(db: Session = Depends(get_db)) -> SupportAccessService:
    return SupportAccessService(
        db=db,
        repo=SupportAccessRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


@tenant_router.post(
    "/tenants/{companyId}/support-access",
    response_model=StandardResponse[SupportAccessGrantResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a time-bounded, reason-required, inspection-only support-access grant",
    dependencies=[
        Depends(require_platform_permission("platform.support_access.initiate"))
    ],
    responses={404: {"description": "Company not found"}},
)
async def initiate_support_access(
    request: Request,
    payload: InitiateSupportAccessRequest,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: SupportAccessService = Depends(_support_access_service),
    db: Session = Depends(get_db),
) -> StandardResponse[SupportAccessGrantResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    grant = svc.initiate(
        company_id=companyId,
        reason=payload.reason,
        actor_platform_administrator_id=current.platform_administrator_id,
    )
    return StandardResponse(
        data=SupportAccessGrantResponse.model_validate(grant),
        message="Support-access grant initiated.",
        meta=_meta(request),
    )


@support_access_router.delete(
    "/support-access/{grantId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate an active support-access grant",
    dependencies=[
        Depends(require_platform_permission("platform.support_access.initiate"))
    ],
    responses={
        403: {"description": "Grant already expired or terminated"},
        404: {"description": "Grant not found"},
    },
)
async def terminate_support_access(
    grantId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: SupportAccessService = Depends(_support_access_service),
) -> None:
    svc.terminate(
        grant_id=grantId,
        actor_platform_administrator_id=current.platform_administrator_id,
    )


@support_access_router.get(
    "/support-access",
    response_model=PaginatedResponse[SupportAccessGrantResponse],
    summary="List support-access grant history",
    dependencies=[Depends(require_platform_permission("platform.support_access.read"))],
)
async def list_support_access(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SupportAccessGrantResponse]:
    repo = SupportAccessRepository(db)
    items, total = repo.list_paginated(offset=(page - 1) * page_size, limit=page_size)
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[SupportAccessGrantResponse.model_validate(g) for g in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} support-access grant(s) found.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Tenant directory, 360° detail, lifecycle history (T167-T169)
# ---------------------------------------------------------------------------


def _tenant_directory_service(db: Session = Depends(get_db)) -> TenantDirectoryService:
    return TenantDirectoryService(
        db=db,
        company_repo=CompanyRepository(db),
        subscription_repo=SubscriptionRepository(db),
        plan_repo=PlanRepository(db),
        quota_repo=QuotaRepository(db),
        usage_repo=UsageRepository(db),
        capability_repo=CapabilityRepository(db),
        audit_repo=PlatformAuditRepository(db),
    )


def _tenant_detail_response(detail: TenantDetail) -> TenantDetailResponse:
    company = detail.company
    return TenantDetailResponse(
        id=company.id,
        legal_name=company.legal_name,
        slug=company.slug,
        status=company.status,
        pre_suspension_status=company.pre_suspension_status,
        access_invalidated_at=company.access_invalidated_at,
        email=company.email,
        country=company.country,
        created_at=company.created_at,
        plan=(
            PlanSummaryResponse(
                id=detail.plan.id,
                code=detail.plan.code,
                name=detail.plan.name,
                status=detail.plan.status,
            )
            if detail.plan is not None
            else None
        ),
        subscription=(
            SubscriptionResponse.model_validate(detail.subscription)
            if detail.subscription is not None
            else None
        ),
        entitlements=[
            CapabilityEntitlementResponse(
                capability_key=e.capability_key, available=e.available, reason=e.reason
            )
            for e in detail.entitlements
        ],
        quotas=[
            QuotaStatusResponse(
                quota_key=q.quota_key,
                state=q.state.value,
                limit=q.limit,
                current_usage=q.current_usage,
                enforcement_style=q.enforcement_style,
            )
            for q in detail.quotas
        ],
        user_count=detail.user_count,
        lifecycle_history=[
            LifecycleEventResponse.model_validate(e) for e in detail.lifecycle_history
        ],
        recent_audit_events=[
            AuditEventSummaryResponse.model_validate(e)
            for e in detail.recent_audit_events
        ],
    )


@tenant_router.get(
    "/tenants",
    response_model=PaginatedResponse[TenantSummaryResponse],
    summary="Search/filter/sort/paginate the full tenant list across all CompanyStatus values",
    dependencies=[Depends(require_platform_permission("platform.tenants.read"))],
)
async def list_tenants(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    country: str | None = Query(None),
    search: str | None = Query(None),
    include_deleted: bool = Query(True),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: TenantDirectoryService = Depends(_tenant_directory_service),
) -> PaginatedResponse[TenantSummaryResponse]:
    filters = {
        "status": status_filter,
        "country": country,
        "search": search,
        "include_deleted": include_deleted,
    }
    items, total = svc.list_tenants(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[TenantSummaryResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} tenant(s) found.",
        meta=_meta(request),
    )


@tenant_router.get(
    "/tenants/{companyId}",
    response_model=StandardResponse[TenantDetailResponse],
    summary="Tenant 360 detail view (aggregate/summary only — never business records)",
    dependencies=[Depends(require_platform_permission("platform.tenants.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_tenant_detail(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    svc: TenantDirectoryService = Depends(_tenant_directory_service),
) -> StandardResponse[TenantDetailResponse]:
    detail = svc.get_tenant_detail(companyId)
    if detail is None:
        raise NotFoundException(message="Company not found.")
    return StandardResponse(
        data=_tenant_detail_response(detail),
        message="Tenant detail resolved.",
        meta=_meta(request),
    )


@tenant_router.get(
    "/tenants/{companyId}/lifecycle-history",
    response_model=StandardResponse[TenantLifecycleHistoryResponse],
    summary="Every status transition for a tenant with actor/timestamp/reason",
    dependencies=[Depends(require_platform_permission("platform.tenants.read"))],
    responses={404: {"description": "Company not found"}},
)
async def get_tenant_lifecycle_history(
    request: Request,
    companyId: UUID = Path(...),  # noqa: N803 — matches contract's path parameter name
    db: Session = Depends(get_db),
    svc: TenantDirectoryService = Depends(_tenant_directory_service),
) -> StandardResponse[TenantLifecycleHistoryResponse]:
    if CompanyRepository(db).get_by_id(companyId) is None:
        raise NotFoundException(message="Company not found.")

    events = svc.get_lifecycle_history(companyId)
    return StandardResponse(
        data=TenantLifecycleHistoryResponse(
            company_id=str(companyId),
            events=[LifecycleEventResponse.model_validate(e) for e in events],
        ),
        message=f"{len(events)} lifecycle event(s) found.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Platform audit (T170) — the read surface for PlatformAuditQueryService (T78)
# ---------------------------------------------------------------------------


def _audit_query_service(db: Session = Depends(get_db)) -> PlatformAuditQueryService:
    return PlatformAuditQueryService(PlatformAuditRepository(db))


def _parse_outcome(outcome: str | None) -> Literal["success", "denied"] | None:
    if outcome == "success":
        return "success"
    if outcome == "denied":
        return "denied"
    return None


@audit_router.get(
    "/audit",
    response_model=PaginatedResponse[AuditEventSummaryResponse],
    summary="Platform audit view, filterable by administrator/tenant/action/resource/date/status",
    dependencies=[Depends(require_platform_permission("platform.audit.read"))],
)
async def list_audit_events(
    request: Request,
    actor_platform_administrator_id: UUID | None = Query(None),
    company_id: UUID | None = Query(None),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    target_id: UUID | None = Query(None),
    created_after: str | None = Query(None),
    created_before: str | None = Query(None),
    outcome: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    svc: PlatformAuditQueryService = Depends(_audit_query_service),
) -> PaginatedResponse[AuditEventSummaryResponse]:
    items, total = svc.query(
        actor_platform_administrator_id=actor_platform_administrator_id,
        company_id=company_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        created_after=datetime.fromisoformat(created_after) if created_after else None,
        created_before=(
            datetime.fromisoformat(created_before) if created_before else None
        ),
        outcome=_parse_outcome(outcome),
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[AuditEventSummaryResponse.model_validate(e) for e in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} audit event(s) found.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Platform health (T174) — surfaces the existing /api/v1/health checks plus
# outbox counts, with an honestly-labeled logging-only relay stub.
# ---------------------------------------------------------------------------


def _health_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthService:
    return HealthService(
        db=db, outbox_repo=EventOutboxRepository(db), settings=settings
    )


@health_router.get(
    "/health",
    response_model=StandardResponse[PlatformHealthResponse],
    summary="Platform operational health",
    description=(
        "DB, outbox pending/published counts, honestly labeled stub relay "
        "(no message-bus is integrated in this Epic)."
    ),
    dependencies=[Depends(require_platform_permission("platform.monitoring.read"))],
)
async def get_platform_health(
    request: Request,
    svc: HealthService = Depends(_health_service),
) -> StandardResponse[PlatformHealthResponse]:
    health = svc.get_health()
    return StandardResponse(
        data=PlatformHealthResponse(
            status=health.status,
            checks=health.checks,
            outbox_pending=health.outbox_pending,
            outbox_published=health.outbox_published,
            relay=health.relay,
        ),
        message=f"Platform health: {health.status}.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Platform Dashboard (T171-T173)
# ---------------------------------------------------------------------------


def _dashboard_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DashboardService:
    return DashboardService(
        db=db,
        audit_repo=PlatformAuditRepository(db),
        health_service=HealthService(
            db=db, outbox_repo=EventOutboxRepository(db), settings=settings
        ),
    )


def _serialize_widget(name: str, widget: DashboardWidget) -> DashboardWidgetResponse:
    data = widget.data
    if name == "recent_platform_actions" and data is not None:
        data = [AuditEventSummaryResponse.model_validate(e).model_dump() for e in data]
    elif name == "health_summary" and data is not None:
        data = {
            "status": data.status,
            "checks": data.checks,
            "outbox_pending": data.outbox_pending,
            "outbox_published": data.outbox_published,
            "relay": data.relay,
        }
    return DashboardWidgetResponse(state=widget.state.value, data=data)


@dashboard_router.get(
    "/dashboard",
    response_model=StandardResponse[DashboardResponse],
    summary="Platform Dashboard aggregates",
    dependencies=[Depends(require_platform_permission("platform.dashboard.view"))],
)
async def get_dashboard(
    request: Request,
    current: PlatformPrincipal = Depends(get_current_platform_admin),
    svc: DashboardService = Depends(_dashboard_service),
    db: Session = Depends(get_db),
) -> StandardResponse[DashboardResponse]:
    # T213: reuses the same request-scoped cache
    # `require_platform_permission("platform.dashboard.view")` (this
    # route's own `dependencies=[]` entry) already populated — one
    # `get_effective_permissions()` DB read per request, not two.
    held_permissions = get_effective_permissions_cached(request, current, db)
    widgets = svc.get_dashboard(held_permissions=held_permissions)
    return StandardResponse(
        data=DashboardResponse(
            widgets={
                name: _serialize_widget(name, widget)
                for name, widget in widgets.items()
            }
        ),
        message=f"{len(widgets)} dashboard widget(s) resolved.",
        meta=_meta(request),
    )

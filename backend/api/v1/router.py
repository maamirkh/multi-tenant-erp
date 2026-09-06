"""API v1 Router — Health and Feature Endpoints.

This module defines all v1 health / infrastructure endpoints and includes
feature-specific routers from their respective modules.

Endpoints (health):
    GET /api/v1/health       — combined liveness + readiness check
    GET /api/v1/health/live  — liveness (always succeeds if process is up)
    GET /api/v1/health/ready — readiness (verifies DB connectivity)

Feature routers included:
    /api/v1/auth/*                               — Authentication (Epic 002)
    /api/v1/companies/*                          — Companies (Epic 003)
    /api/v1/companies/{company_id}/members/*     — Users & Roles members (Epic 004)
    /api/v1/companies/{company_id}/roles/*       — Users & Roles roles (Epic 004)
    /api/v1/permissions/*                        — Permissions catalogue (Epic 004)
    /api/v1/profile/*                            — User profile (Epic 004)
    /api/v1/preferences/*                        — User preferences (Epic 004)
    /api/v1/inventory/*                          — Inventory module health (Epic 005)
    /api/v1/companies/{company_id}/inventory/*   — Inventory company endpoints (Epic 005)
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.auth.router import router as auth_router
from modules.companies.router import router as companies_router
from modules.inventory.router import router as inventory_router
from modules.users_roles.ownership_router import ownership_router
from modules.users_roles.permissions_router import permissions_router
from modules.users_roles.preferences_router import preferences_router
from modules.users_roles.profile_router import profile_router
from modules.users_roles.roles_router import roles_router
from modules.users_roles.router import router as users_roles_router

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Include feature routers.
router.include_router(auth_router)
router.include_router(companies_router, prefix="/companies")
router.include_router(
    users_roles_router,
    prefix="/companies/{company_id}/members",
)
router.include_router(
    roles_router,
    prefix="/companies/{company_id}/roles",
)
router.include_router(
    ownership_router,
    prefix="/companies/{company_id}",
)
router.include_router(
    permissions_router,
    prefix="/permissions",
)
router.include_router(
    profile_router,
    prefix="/profile",
)
router.include_router(
    preferences_router,
    prefix="/preferences",
)
router.include_router(
    inventory_router,
    prefix="/inventory",
)
router.include_router(
    inventory_router,
    prefix="/companies/{company_id}/inventory",
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class HealthData(BaseModel):
    """Health check response payload."""

    status: str
    version: str
    environment: str
    timestamp: datetime
    checks: dict[str, str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=StandardResponse[HealthData],
    summary="Combined health check",
    description=(
        "Returns liveness and readiness status. "
        "503 when any infrastructure dependency is unavailable."
    ),
)
async def health_check(
    response: Response,
    db: Session = Depends(get_db),
) -> StandardResponse[HealthData]:
    """Combined liveness + readiness health check."""
    from core.config.settings import get_settings

    settings = get_settings()
    checks: dict[str, str] = {}
    overall = "healthy"

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except OperationalError as exc:
        logger.warning("Database health check failed: %s", exc)
        checks["database"] = "unavailable"
        overall = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Auth configuration check — verify JWT settings are initialised without exposing values.
    try:
        jwt_ok = (
            bool(settings.JWT_SECRET_KEY)
            and len(settings.JWT_SECRET_KEY) >= 32
            and bool(settings.JWT_ALGORITHM)
        )
        checks["auth_config"] = "ok" if jwt_ok else "misconfigured"
        if not jwt_ok:
            overall = "degraded"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as exc:  # noqa: BLE001
        logger.warning("Auth config health check failed: %s", exc)
        checks["auth_config"] = "unavailable"
        overall = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    now = utcnow()
    return StandardResponse(
        data=HealthData(
            status=overall,
            version=settings.API_VERSION,
            environment=settings.ENVIRONMENT,
            timestamp=now,
            checks=checks,
        ),
        message="Health check completed",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Always returns 200 while the process is running.",
)
async def liveness() -> dict[str, str]:
    """Kubernetes / container liveness probe — never fails."""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Returns 200 when all infrastructure dependencies are ready.",
)
async def readiness(
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Readiness probe — verifies DB connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except OperationalError as exc:
        logger.warning("Readiness probe failed: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "reason": "database_unavailable"}

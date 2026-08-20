"""Platform Administration module API router.

Endpoints (Phase 4):
    POST /platform/auth/login    — public, per contracts/platform-admin-v1.yaml
    POST /platform/auth/refresh  — public
    POST /platform/auth/logout   — requires a valid Platform session

Mounted at ``/api/v1/platform`` by ``api/v1/router.py`` (T053) — without
``get_current_company_member``, since Platform is never company-scoped.

Router discipline: delegates to the service layer — no business logic in
the router (plan.md §10 API Contract Lock). Contract traceability:
operations 1-3 of ``platform-admin-v1.yaml`` (the 3 public `/auth/*`
operations — no `x-permission`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.platform_admin.dependencies import (
    PlatformPrincipal,
    get_current_platform_admin,
)
from modules.platform_admin.schemas.platform_auth import (
    PlatformLoginRequest,
    PlatformLoginResponse,
    PlatformRefreshTokenRequest,
    PlatformRefreshTokenResponse,
)
from modules.platform_admin.services.platform_auth_service import PlatformAuthService

router = APIRouter(prefix="/auth", tags=["Platform Authentication"])


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

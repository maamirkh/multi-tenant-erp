"""Authentication API router.

Registers all authentication endpoints under the ``/auth`` prefix.
This router is mounted at ``/api/v1`` by ``api/v1/router.py``.

Endpoints:
    POST   /auth/login
    POST   /auth/logout
    POST   /auth/refresh
    GET    /auth/me
    POST   /auth/forgot-password
    POST   /auth/reset-password
    POST   /auth/change-password
    POST   /auth/verify-email

Rate limits (applied per IP or per user_id):
    /login          : 10 / minute per IP
    /refresh        : 30 / minute per IP
    /logout         : 30 / minute per IP
    /me             : 60 / minute per IP
    /forgot-password: 3 / 15 minutes per IP
    /reset-password : 5 / 15 minutes per IP
    /change-password: 5 / 15 minutes per user_id
    /verify-email   : 10 / hour per IP
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.auth.dependencies import (
    require_authenticated,
    require_session_id,
    require_user_id,
)
from core.auth.interfaces import CurrentUser
from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.auth.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from modules.auth.schemas.password import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from modules.auth.schemas.user import UserProfileResponse
from modules.auth.schemas.verify import VerifyEmailRequest
from modules.auth.services.auth_service import AuthService

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def _meta(request: Request) -> ResponseMeta:
    """Build a ``ResponseMeta`` for the current request."""
    return ResponseMeta(
        request_id=REQUEST_ID_CONTEXT.get("-"),
        timestamp=utcnow(),
    )


def _auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    """FastAPI dependency that constructs ``AuthService`` for the request."""
    return AuthService(db=db, settings=settings)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=StandardResponse[LoginResponse],
    status_code=status.HTTP_200_OK,
    summary="User login",
    description=(
        "Authenticate with email and password. "
        "Returns a short-lived JWT access token and an opaque refresh token. "
        "Rate limited to 10 requests per minute per IP address."
    ),
    responses={
        200: {
            "description": "Login successful",
            "model": StandardResponse[LoginResponse],
        },
        401: {"description": "Invalid credentials"},
        403: {"description": "Account is inactive"},
        422: {"description": "Validation error"},
        423: {"description": "Account is locked"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    svc: AuthService = Depends(_auth_service),
) -> StandardResponse[LoginResponse]:
    """Authenticate a user and issue access and refresh tokens."""
    result = svc.login(
        email=str(payload.email),
        password=payload.password,
        remember_me=payload.remember_me,
        request=request,
    )
    return StandardResponse(
        data=LoginResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        ),
        message="Login successful.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=StandardResponse[RefreshTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description=(
        "Exchange a valid refresh token for a new access token and rotated refresh token. "
        "The old refresh token is immediately invalidated. "
        "Rate limited to 30 requests per minute per IP."
    ),
    responses={
        200: {
            "description": "Token refreshed",
            "model": StandardResponse[RefreshTokenResponse],
        },
        401: {"description": "Invalid or expired refresh token"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    svc: AuthService = Depends(_auth_service),
) -> StandardResponse[RefreshTokenResponse]:
    """Rotate a refresh token and issue a new access token."""
    result = svc.refresh(
        raw_refresh_token=payload.refresh_token,
        request=request,
    )
    return StandardResponse(
        data=RefreshTokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_in=result.expires_in,
        ),
        message="Token refreshed.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    response_model=StandardResponse[LogoutResponse],
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description=(
        "Revoke the current session and all associated refresh tokens. "
        "Requires a valid JWT Bearer token. "
        "Rate limited to 30 requests per minute per IP."
    ),
    responses={
        200: {"description": "Logout successful"},
        401: {"description": "Not authenticated"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("30/minute")
async def logout(
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AuthService = Depends(_auth_service),
) -> StandardResponse[LogoutResponse]:
    """Revoke the current session and all its refresh tokens."""
    svc.logout(
        user_id=require_user_id(current_user),
        session_id=require_session_id(current_user),
        request=request,
    )
    return StandardResponse(
        data=LogoutResponse(message="Successfully logged out."),
        message="Logout successful.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=StandardResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="Current user profile",
    description=(
        "Return the authenticated user's profile. "
        "Credential fields (password hash, history) are never included. "
        "Requires a valid JWT Bearer token. "
        "Rate limited to 60 requests per minute per IP."
    ),
    responses={
        200: {
            "description": "User profile",
            "model": StandardResponse[UserProfileResponse],
        },
        401: {"description": "Not authenticated"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("60/minute")
async def get_me(
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AuthService = Depends(_auth_service),
) -> StandardResponse[UserProfileResponse]:
    """Return the current authenticated user's profile."""
    profile = svc.get_current_user_profile(require_user_id(current_user))
    return StandardResponse(
        data=UserProfileResponse(
            user_id=profile.user_id,
            email=profile.email,
            display_name=profile.display_name,
            account_status=profile.account_status,
            is_email_verified=profile.is_email_verified,
            created_at=profile.created_at,
        ),
        message="User profile retrieved.",
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# POST /auth/forgot-password
# ---------------------------------------------------------------------------


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description=(
        "Initiate the password reset flow. "
        "Always returns the same success message regardless of whether the email exists "
        "(anti-enumeration, FR-026). "
        "Rate limited to 3 requests per 15 minutes per IP."
    ),
    response_model=None,
    responses={
        200: {"description": "Reset instructions sent (always returned)"},
        422: {"description": "Validation error"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("3/15minutes")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    svc: AuthService = Depends(_auth_service),
) -> JSONResponse:
    """Initiate the password reset flow (anti-enumeration)."""
    svc.forgot_password(email=str(payload.email), request=request)
    return JSONResponse(
        status_code=200,
        content={"message": "If this email is registered, a reset link has been sent."},
    )


# ---------------------------------------------------------------------------
# POST /auth/reset-password
# ---------------------------------------------------------------------------


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    description=(
        "Complete the password reset using the token from the reset email. "
        "Rate limited to 5 requests per 15 minutes per IP."
    ),
    response_model=None,
    responses={
        200: {"description": "Password reset successfully"},
        400: {"description": "Invalid or expired reset token"},
        422: {"description": "Password does not meet requirements"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("5/15minutes")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    svc: AuthService = Depends(_auth_service),
) -> JSONResponse:
    """Reset a user's password using a one-time reset token."""
    svc.reset_password(
        raw_token=payload.token,
        new_password=payload.new_password,
        request=request,
    )
    return JSONResponse(
        status_code=200,
        content={
            "message": "Password has been reset successfully. Please log in with your new password."
        },
    )


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description=(
        "Change password for an authenticated user. "
        "Requires the current password for verification. "
        "All sessions are revoked after a successful password change. "
        "Rate limited to 5 requests per 15 minutes per authenticated user."
    ),
    response_model=None,
    responses={
        200: {"description": "Password changed successfully"},
        401: {"description": "Current password is incorrect or not authenticated"},
        422: {"description": "New password does not meet requirements"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("5/15minutes")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AuthService = Depends(_auth_service),
) -> JSONResponse:
    """Change password for the currently authenticated user."""
    svc.change_password(
        user_id=require_user_id(current_user),
        current_password=payload.current_password,
        new_password=payload.new_password,
        request=request,
    )
    return JSONResponse(
        status_code=200,
        content={"message": "Password changed successfully. Please log in again."},
    )


# ---------------------------------------------------------------------------
# POST /auth/verify-email
# ---------------------------------------------------------------------------


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description=(
        "Confirm email ownership using the token sent at registration. "
        "Rate limited to 10 requests per hour per IP."
    ),
    response_model=None,
    responses={
        200: {"description": "Email verified successfully"},
        400: {"description": "Invalid or expired verification token"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit("10/hour")
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    svc: AuthService = Depends(_auth_service),
) -> JSONResponse:
    """Verify a user's email address using a one-time token."""
    svc.verify_email(raw_token=payload.token, request=request)
    return JSONResponse(
        status_code=200,
        content={"message": "Email address verified successfully."},
    )

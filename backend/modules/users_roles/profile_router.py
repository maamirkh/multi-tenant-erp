"""FastAPI router for user profile management.

Endpoints are mounted under ``/api/v1/profile`` by ``api/v1/router.py``.
All endpoints are user-scoped (not company-scoped) and require authentication.

Spec reference: contracts/profile-api.yaml, tasks T063.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.users_roles.dependencies import get_profile_service
from modules.users_roles.schemas.profile import (
    AvatarUploadResponse,
    ProfileResponse,
    UpdateProfileRequest,
)
from modules.users_roles.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

profile_router = APIRouter(prefix="", tags=["Profile"])


@profile_router.get(
    "",
    response_model=StandardResponse[ProfileResponse],
    summary="Get current user's profile",
)
def get_profile(
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: ProfileService = Depends(get_profile_service),
) -> StandardResponse[ProfileResponse]:
    """Return the authenticated user's profile."""
    user = service.get_profile(current_user.user_id)  # type: ignore[arg-type]
    return StandardResponse[ProfileResponse](
        data=ProfileResponse.model_validate(user),
        message="Profile retrieved.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@profile_router.patch(
    "",
    response_model=StandardResponse[ProfileResponse],
    summary="Update current user's profile",
)
def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: ProfileService = Depends(get_profile_service),
) -> StandardResponse[ProfileResponse]:
    """Update the authenticated user's display name and/or phone number."""
    # Use sentinel ... for phone when not included in the request body
    phone_value = body.phone if "phone" in (body.model_fields_set or set()) else ...

    user = service.update_profile(
        current_user.user_id,  # type: ignore[arg-type]
        display_name=body.display_name,
        phone=phone_value,
    )
    return StandardResponse[ProfileResponse](
        data=ProfileResponse.model_validate(user),
        message="Profile updated.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@profile_router.post(
    "/avatar",
    response_model=StandardResponse[AvatarUploadResponse],
    status_code=status.HTTP_200_OK,
    summary="Upload user avatar",
)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, WebP; max 5 MB)"),
    current_user: CurrentUser = Depends(require_authenticated),
    service: ProfileService = Depends(get_profile_service),
) -> StandardResponse[AvatarUploadResponse]:
    """Upload a new avatar image for the authenticated user.

    Validates format (JPEG, PNG, WebP) and size (≤ USER_AVATAR_MAX_BYTES)
    before uploading to object storage.
    """
    file_bytes = await file.read()
    avatar_url = service.upload_avatar(
        current_user.user_id,  # type: ignore[arg-type]
        file_bytes=file_bytes,
        filename=file.filename or "avatar",
    )
    return StandardResponse[AvatarUploadResponse](
        data=AvatarUploadResponse(avatar_url=avatar_url),
        message="Avatar uploaded.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@profile_router.delete(
    "/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove current avatar",
)
def delete_avatar(
    current_user: CurrentUser = Depends(require_authenticated),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    """Remove the authenticated user's current avatar.

    The S3 file is retained for AVATAR_RETENTION_DAYS days before cleanup.
    """
    service.delete_avatar(current_user.user_id)  # type: ignore[arg-type]
    return Response(status_code=status.HTTP_204_NO_CONTENT)

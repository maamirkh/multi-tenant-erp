"""FastAPI router for user preference management.

Endpoints are mounted under ``/api/v1/preferences`` by ``api/v1/router.py``.
All endpoints are user-scoped (not company-scoped) and require authentication.

Spec reference: contracts/profile-api.yaml, tasks T064.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.users_roles.dependencies import get_preference_service
from modules.users_roles.schemas.preference import (
    PreferenceResponse,
    UpdatePreferenceRequest,
)
from modules.users_roles.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)

preferences_router = APIRouter(prefix="", tags=["Preferences"])


@preferences_router.get(
    "",
    response_model=StandardResponse[PreferenceResponse],
    summary="Get current user's preferences",
)
def get_preferences(
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: PreferenceService = Depends(get_preference_service),
) -> StandardResponse[PreferenceResponse]:
    """Return the authenticated user's preferences.

    If no preference record exists yet, one is created with sensible defaults.
    """
    pref = service.get_preferences(current_user.user_id)  # type: ignore[arg-type]
    return StandardResponse[PreferenceResponse](
        data=PreferenceResponse.model_validate(pref),
        message="Preferences retrieved.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@preferences_router.put(
    "",
    response_model=StandardResponse[PreferenceResponse],
    summary="Update user preferences",
)
def update_preferences(
    body: UpdatePreferenceRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: PreferenceService = Depends(get_preference_service),
) -> StandardResponse[PreferenceResponse]:
    """Update the authenticated user's preferences.

    All fields are optional; only provided fields are updated.
    """
    pref = service.update_preferences(
        current_user.user_id,  # type: ignore[arg-type]
        language=body.language,
        timezone=body.timezone,
        date_format=body.date_format,
        number_format=body.number_format,
        theme=body.theme,
    )
    return StandardResponse[PreferenceResponse](
        data=PreferenceResponse.model_validate(pref),
        message="Preferences updated.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )

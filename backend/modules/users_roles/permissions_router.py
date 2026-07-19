"""FastAPI router for global permission listing.

Endpoints are mounted under ``/api/v1/permissions``
by ``api/v1/router.py``.

Spec reference: Epic 4 — Users & Roles, tasks T054.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.users_roles.dependencies import get_permission_service
from modules.users_roles.schemas.permission import (
    PermissionGroupResponse,
    PermissionResponse,
)
from modules.users_roles.services.permission_service import PermissionService

logger = logging.getLogger(__name__)

permissions_router = APIRouter(prefix="", tags=["Permissions"])


@permissions_router.get(
    "",
    response_model=StandardResponse[list[PermissionGroupResponse]],
    summary="List all permissions grouped by module",
)
def list_permissions(
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: PermissionService = Depends(get_permission_service),
) -> StandardResponse[list[PermissionGroupResponse]]:
    """List all platform permissions grouped by module.

    Global endpoint — not company-scoped. Requires authentication only.
    """
    groups = service.list_all_permissions()

    items = [
        PermissionGroupResponse(
            module=g["module"],
            permissions=[
                PermissionResponse(
                    code=p.code,
                    label=p.label,
                    module=p.module,
                    action=p.action,
                    description=p.description,
                )
                for p in g["permissions"]
            ],
        )
        for g in groups
    ]

    return StandardResponse[list[PermissionGroupResponse]](
        data=items,
        message=f"{len(items)} permission groups found.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )

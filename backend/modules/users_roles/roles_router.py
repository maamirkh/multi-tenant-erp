"""FastAPI router for role CRUD endpoints.

Endpoints are mounted under ``/api/v1/companies/{company_id}/roles``
by ``api/v1/router.py``.

Spec reference: Epic 4 — Users & Roles, tasks T051, T052, T053, T084.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.users_roles.dependencies import (
    get_actor_role_rank,
    get_current_company_member,
    get_role_service,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.schemas.role import (
    CreateRoleRequest,
    PermissionResponse,
    RoleDetailResponse,
    RoleListItem,
    UpdateRoleRequest,
)
from modules.users_roles.services.role_service import RoleService

logger = logging.getLogger(__name__)

roles_router = APIRouter(prefix="", tags=["Roles"])


def _request_context(request: Request) -> dict[str, str | None]:
    """Extract audit context from the HTTP request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("x-request-id"),
    }


def _build_role_detail(
    role: Role,
    permissions: list[Permission] | None = None,
    member_count: int = 0,
) -> RoleDetailResponse:
    """Convert a Role ORM instance to RoleDetailResponse.

    Args:
        role:         The ``Role`` ORM instance.
        permissions:  List of ``Permission`` ORM instances to embed.
        member_count: Number of active members assigned to this role.
    """
    return RoleDetailResponse(
        id=role.id,
        company_id=role.company_id,
        name=role.name,
        slug=role.slug,
        rank=role.rank,
        description=role.description,
        is_system=role.is_system,
        is_active=role.is_active,
        member_count=member_count,
        permissions=[
            PermissionResponse(
                id=p.id,
                code=p.code,
                label=p.label,
                module=p.module,
                action=p.action,
                description=p.description,
            )
            for p in (permissions or [])
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@roles_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[RoleDetailResponse],
    summary="Create a custom role",
)
def create_role(
    company_id: UUID,
    body: CreateRoleRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: RoleService = Depends(get_role_service),
) -> StandardResponse[RoleDetailResponse]:
    """Create a new custom role with optional permission assignments."""
    role = service.create_custom_role(
        company_id=company_id,
        name=body.name,
        rank=body.rank,
        description=body.description,
        permission_codes=body.permission_codes,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )

    _, permissions, member_count = service.get_role_with_permissions(
        role.id, company_id
    )

    return StandardResponse[RoleDetailResponse](
        data=_build_role_detail(role, permissions, member_count),
        message="Custom role created successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@roles_router.patch(
    "/{role_id}",
    response_model=StandardResponse[RoleDetailResponse],
    summary="Update a custom role",
)
def update_role(
    company_id: UUID,
    role_id: UUID,
    body: UpdateRoleRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: RoleService = Depends(get_role_service),
) -> StandardResponse[RoleDetailResponse]:
    """Update a custom role. System roles cannot be modified."""
    role = service.update_custom_role(
        company_id=company_id,
        role_id=role_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        name=body.name,
        # sentinel: "not provided" vs None-to-clear
        description=(body.description if body.description is not None else ...),
        rank=body.rank,
        permission_codes=body.permission_codes,
        request_context=_request_context(request),
    )

    _, permissions, member_count = service.get_role_with_permissions(
        role.id, company_id
    )

    return StandardResponse[RoleDetailResponse](
        data=_build_role_detail(role, permissions, member_count),
        message="Custom role updated successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@roles_router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom role",
)
def delete_role(
    company_id: UUID,
    role_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: RoleService = Depends(get_role_service),
) -> Response:
    """Delete a custom role. Only allowed if no active members assigned."""
    service.delete_role(
        company_id=company_id,
        role_id=role_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roles_router.get(
    "",
    response_model=StandardResponse[list[RoleListItem]],
    summary="List roles for a company",
)
def list_roles(
    company_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    service: RoleService = Depends(get_role_service),
    include_inactive: bool = False,
) -> StandardResponse[list[RoleListItem]]:
    """List all roles for a company with member counts."""
    role_data, total = service.list_roles(company_id, include_inactive=include_inactive)

    items = [
        RoleListItem(
            id=d["role"].id,
            name=d["role"].name,
            slug=d["role"].slug,
            rank=d["role"].rank,
            is_system=d["role"].is_system,
            is_active=d["role"].is_active,
            description=d["role"].description,
            member_count=d["member_count"],
            created_at=d["role"].created_at,
        )
        for d in role_data
    ]

    return StandardResponse[list[RoleListItem]](
        data=items,
        message=f"{total} roles found.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@roles_router.get(
    "/{role_id}",
    response_model=StandardResponse[RoleDetailResponse],
    summary="Get role details",
)
def get_role(
    company_id: UUID,
    role_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    service: RoleService = Depends(get_role_service),
) -> StandardResponse[RoleDetailResponse]:
    """Return full details of a specific role."""
    role, permissions, member_count = service.get_role_with_permissions(
        role_id=role_id, company_id=company_id
    )

    return StandardResponse[RoleDetailResponse](
        data=_build_role_detail(role, permissions, member_count),
        message="Role retrieved successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )

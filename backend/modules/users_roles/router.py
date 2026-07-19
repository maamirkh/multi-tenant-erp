"""FastAPI router for the users & roles module.

All route handlers are thin: validate input (Pydantic), authorize via
dependency guards, delegate to services, and return standard response
envelopes.  Business logic lives exclusively in the service layer.

Endpoints are mounted under ``/api/v1/companies/{company_id}/members``
and related sub-paths by ``api/v1/router.py``.

Spec reference: Epic 4 — Users & Roles, tasks T034, T043, T044, T072, T077, T081.
"""

from __future__ import annotations

import logging
import math
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.schemas.pagination import PaginatedData, PaginatedResponse
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.auth.repositories.user_repository import UserRepository
from modules.users_roles.constants import ADMIN_RANK
from modules.users_roles.dependencies import (
    get_actor_role_rank,
    get_current_company_member,
    get_invitation_service,
    get_member_service,
    require_rank,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.schemas.member import (
    AddMemberRequest,
    MemberDetailResponse,
    MemberListItem,
    MemberResponse,
    RoleSummary,
    UpdateMemberRequest,
)
from modules.users_roles.schemas.member_status import ArchiveRequest, SuspendRequest
from modules.users_roles.services.invitation_service import InvitationService
from modules.users_roles.services.member_service import MemberService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Users & Roles"])


def _build_member_response(member: CompanyMember) -> MemberResponse:
    """Convert a CompanyMember ORM instance to MemberResponse schema."""
    role = member.role
    return MemberResponse(
        id=member.id,
        user_id=member.user_id,
        role=RoleSummary(
            id=role.id,
            name=role.name,
            slug=role.slug,
            rank=role.rank,
        ),
        status=member.status,
        created_at=member.created_at,
    )


def _build_member_detail_response(
    member: CompanyMember, actor_rank: int
) -> MemberDetailResponse:
    """Convert a CompanyMember ORM instance to MemberDetailResponse schema.

    Args:
        member:     The loaded ``CompanyMember`` with eagerly loaded ``user``
                    and ``role`` relationships.
        actor_rank: Rank of the requesting user's role.  Notes are hidden when
                    ``actor_rank < ADMIN_RANK`` (FR-023).
    """
    role = member.role
    user = member.user
    return MemberDetailResponse(
        id=member.id,
        user_id=member.user_id,
        company_id=member.company_id,
        display_name=user.display_name or user.email,
        email=user.email,
        avatar_url=getattr(user, "avatar_url", None),
        role=RoleSummary(
            id=role.id,
            name=role.name,
            slug=role.slug,
            rank=role.rank,
        ),
        status=member.status,
        employee_id=member.employee_id,
        job_title=member.job_title,
        department=member.department,
        work_phone=member.work_phone,
        hire_date=member.hire_date,
        notes=member.notes if actor_rank >= ADMIN_RANK else None,
        invited_by=member.invited_by,
        invitation_accepted_at=member.invitation_accepted_at,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _build_member_list_item(member: CompanyMember) -> MemberListItem:
    """Convert a CompanyMember (with eagerly loaded user + role) to MemberListItem."""
    user = member.user
    role = member.role
    return MemberListItem(
        id=member.id,
        user_id=member.user_id,
        display_name=user.display_name or user.email,
        email=user.email,
        avatar_url=getattr(user, "avatar_url", None),
        role=RoleSummary(
            id=role.id,
            name=role.name,
            slug=role.slug,
            rank=role.rank,
        ),
        status=member.status,
        department=member.department,
        job_title=member.job_title,
        created_at=member.created_at,
    )


def _request_context(request: Request) -> dict[str, str | None]:
    """Extract audit context from the HTTP request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("x-request-id"),
    }


@router.get(
    "",
    response_model=PaginatedResponse[MemberListItem],
    summary="List company members with pagination and filters",
)
def list_members(
    company_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    service: MemberService = Depends(get_member_service),
    status: str | None = Query(None, description="Filter by membership status."),
    role_id: UUID | None = Query(None, description="Filter by role ID."),
    department: str | None = Query(
        None, description="Filter by department (exact match)."
    ),
    search: str | None = Query(
        None,
        max_length=100,
        description="Search by display name, email, or employee ID.",
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page."),
    sort_by: Literal["name", "created_at", "role_rank", "department"] = Query(
        "name", description="Sort column."
    ),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Sort direction."),
) -> PaginatedResponse[MemberListItem]:
    """Return a paginated, filterable list of company members.

    All authenticated members can list members. Filters: status, role_id,
    department (exact), search (case-insensitive substring on name/email/
    employee_id). Supports sorting by name, created_at, role_rank, department.
    """
    members, total = service.list_members(
        company_id,
        status=status,
        role_id=role_id,
        department=department,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    items = [_build_member_list_item(m) for m in members]
    pages = math.ceil(total / page_size) if page_size > 0 else 0

    return PaginatedResponse[MemberListItem](
        data=PaginatedData[MemberListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} member(s) found.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[MemberResponse],
    summary="Add a new member to the company",
)
def add_member(
    company_id: UUID,
    body: AddMemberRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberResponse]:
    """Add a new member to the company.

    Requires the actor to have an active membership with sufficient rank
    to assign the requested role.
    """
    # Look up user by email
    user_repo = UserRepository(service._db)
    user = user_repo.find_by_email(body.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered user found with email '{body.email}'.",
        )

    member = service.add_member(
        company_id=company_id,
        user_id=user.id,
        role_id=body.role_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        actor_role_rank=actor_rank,
        employee_id=body.employee_id,
        job_title=body.job_title,
        department=body.department,
        work_phone=body.work_phone,
        hire_date=body.hire_date,
        notes=body.notes,
        request_context=_request_context(request),
    )

    return StandardResponse[MemberResponse](
        data=_build_member_response(member),
        message="Member added successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.get(
    "/{member_id}",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Get member details",
)
def get_member(
    company_id: UUID,
    member_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Return full details of a specific member.

    Notes are hidden when the requesting user's rank is below Admin (FR-023).
    """
    member = service.get_member(member_id=member_id, company_id=company_id)

    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member retrieved successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.patch(
    "/{member_id}",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Update member role or employee info",
)
def update_member(
    company_id: UUID,
    member_id: UUID,
    body: UpdateMemberRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Update a member's role and/or employee information.

    Requires the actor to have an active membership with sufficient rank
    to manage the target member.
    """
    member = service.update_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        actor_role_rank=actor_rank,
        role_id=body.role_id,
        employee_id=body.employee_id if body.employee_id is not None else ...,
        job_title=body.job_title if body.job_title is not None else ...,
        department=body.department if body.department is not None else ...,
        work_phone=body.work_phone if body.work_phone is not None else ...,
        hire_date=body.hire_date if body.hire_date is not None else ...,
        notes=body.notes if body.notes is not None else ...,
        request_context=_request_context(request),
    )

    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member updated successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


# ---------------------------------------------------------------------------
# Lifecycle endpoints — US5 (T072)
# All require Admin+ rank (ADMIN_RANK = 80)
# ---------------------------------------------------------------------------


@router.post(
    "/{member_id}/deactivate",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Deactivate a member (active → inactive)",
    dependencies=[Depends(require_rank(ADMIN_RANK))],
)
def deactivate_member(
    company_id: UUID,
    member_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Deactivate a member (status: active → inactive).

    Revokes all active sessions. Requires Admin+ rank.
    """
    member = service.deactivate_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member deactivated.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "/{member_id}/reactivate",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Reactivate a member (inactive/suspended/locked → active)",
    dependencies=[Depends(require_rank(ADMIN_RANK))],
)
def reactivate_member(
    company_id: UUID,
    member_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Reactivate a member from inactive, suspended, or locked status."""
    member = service.reactivate_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member reactivated.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "/{member_id}/suspend",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Suspend a member (active/locked → suspended)",
    dependencies=[Depends(require_rank(ADMIN_RANK))],
)
def suspend_member(
    company_id: UUID,
    member_id: UUID,
    body: SuspendRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Suspend a member with a mandatory reason. Revokes all active sessions."""
    member = service.suspend_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        reason=body.reason,
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member suspended.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "/{member_id}/lock",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Lock a member (active → locked)",
    dependencies=[Depends(require_rank(ADMIN_RANK))],
)
def lock_member(
    company_id: UUID,
    member_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Lock a member (security-triggered restriction). Revokes all active sessions."""
    member = service.lock_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member locked.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "/{member_id}/archive",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Archive (soft-delete) a member",
    dependencies=[Depends(require_rank(ADMIN_RANK))],
)
def archive_member(
    company_id: UUID,
    member_id: UUID,
    body: ArchiveRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Soft-delete a member with a mandatory reason. Sets deleted_at and revokes sessions."""
    member = service.archive_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        reason=body.reason,
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member archived.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "/{member_id}/restore",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Restore an archived member (archived → active)",
    dependencies=[Depends(require_rank(ADMIN_RANK))],
)
def restore_member(
    company_id: UUID,
    member_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: MemberService = Depends(get_member_service),
) -> StandardResponse[MemberDetailResponse]:
    """Restore an archived member to active status. Clears deleted_at."""
    member = service.restore_member(
        company_id=company_id,
        member_id=member_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Member restored.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )


@router.post(
    "/{member_id}/accept-invitation",
    response_model=StandardResponse[MemberDetailResponse],
    summary="Accept a pending membership invitation",
)
def accept_invitation(
    company_id: UUID,
    member_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    actor_rank: int = Depends(get_actor_role_rank),
    service: InvitationService = Depends(get_invitation_service),
) -> StandardResponse[MemberDetailResponse]:
    """Accept a pending invitation for the authenticated user.

    The caller must be the invited user (ownership of the membership record
    is validated inside ``InvitationService.accept_invitation``).
    """
    member = service.accept_invitation(
        member_id=member_id,
        company_id=company_id,
        user_id=current_user.user_id,  # type: ignore[arg-type]
        request_context=_request_context(request),
    )
    return StandardResponse[MemberDetailResponse](
        data=_build_member_detail_response(member, actor_rank),
        message="Invitation accepted.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )

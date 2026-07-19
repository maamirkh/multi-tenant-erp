"""FastAPI router for the ownership transfer endpoint.

Mounted under ``/api/v1/companies/{company_id}`` by ``api/v1/router.py``.
Exposes a single endpoint:

    POST /api/v1/companies/{company_id}/transfer-ownership

Access: Owner-only (rank ≥ 100).  Business logic delegated to
``OwnershipService.transfer_ownership``.

Spec reference: Epic 4, Phase 15 (T128).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.users_roles.constants import OWNER_RANK
from modules.users_roles.dependencies import (
    get_current_company_member,
    get_ownership_service,
    require_rank,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.schemas.ownership import TransferOwnershipRequest
from modules.users_roles.services.ownership_service import OwnershipService

logger = logging.getLogger(__name__)

ownership_router = APIRouter(tags=["Ownership"])


def _request_context(request: Request) -> dict[str, str | None]:
    """Extract audit context from the HTTP request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("x-request-id"),
    }


@ownership_router.post(
    "/transfer-ownership",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Transfer company ownership to an active member (Owner-only)",
    dependencies=[Depends(require_rank(OWNER_RANK))],
)
def transfer_ownership(
    company_id: UUID,
    body: TransferOwnershipRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    current_member: CompanyMember = Depends(get_current_company_member),
    service: OwnershipService = Depends(get_ownership_service),
) -> StandardResponse[None]:
    """Transfer ownership to an active member within the same company.

    The requesting user must hold the Owner role (rank = 100).  After a
    successful transfer:
    - The target member receives the Owner role.
    - The former Owner is demoted to Admin.
    - ``companies.owner_id`` is updated atomically.
    - An ``OWNERSHIP_TRANSFERRED`` audit log entry is recorded.
    - An ``OwnershipTransferredEvent`` is published to the event outbox.

    This action is irreversible without the new Owner's consent.
    """
    service.transfer_ownership(
        company_id=company_id,
        actor_user_id=current_user.user_id,  # type: ignore[arg-type]
        target_member_id=body.target_member_id,
        request_context=_request_context(request),
    )
    return StandardResponse(
        data=None,
        message="Ownership transferred successfully.",
        meta=ResponseMeta(
            request_id=request.headers.get("x-request-id", ""),
            timestamp=utcnow(),
        ),
    )

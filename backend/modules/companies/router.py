"""FastAPI router for the companies module.

All route handlers are thin: validate input (Pydantic), authorize via
dependency guards, delegate to services, and return standard response
envelopes.  Business logic lives exclusively in the service layer.

Spec reference: Phase 9, T042–T048.
"""

from __future__ import annotations

import math
from typing import Any, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.pagination import PaginatedData, PaginatedResponse
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.auth.router import limiter
from modules.companies.dependencies import (
    get_company_logo_service,
    get_company_service,
    get_current_company,
    require_admin_or_above,
    require_owner,
    require_super_admin,
)
from modules.companies.exceptions import CompanyNotFoundError
from modules.companies.models.company import Company
from modules.companies.schemas import (
    ActivateResponse,
    AuditLogEntryResponse,
    AuditLogListResponse,
    CompanyAddressResponse,
    CompanyDetailResponse,
    CompanyListItem,
    CompanyResponse,
    CompanySettingsResponse,
    CreateAddressRequest,
    CreateCompanyRequest,
    DeactivateRequest,
    DeactivateResponse,
    DeleteCompanyRequest,
    DeleteCompanyResponse,
    RestoreResponse,
    UpdateAddressRequest,
    UpdateCompanyRequest,
    UpdateSettingsRequest,
)
from modules.companies.services.company_logo_service import CompanyLogoService
from modules.companies.services.company_service import CompanyService
from modules.users_roles.dependencies import get_member_service, get_role_seed_service
from modules.users_roles.services.member_service import MemberService
from modules.users_roles.services.role_seed_service import RoleSeedService

router = APIRouter(prefix="", tags=["companies"])

# Super-admin role constant matches dependencies.py
_ROLE_SUPER_ADMIN = "super_admin"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class LogoUploadResponse(BaseModel):
    """Response body for POST /companies/{id}/logo."""

    company_id: UUID
    logo_url: str


def _meta() -> ResponseMeta:
    """Build a ResponseMeta from the current request context."""
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


def _request_context(request: Request) -> dict[str, Any]:
    """Extract audit-relevant fields from the HTTP request.

    ``request_id`` is cast from string to UUID because the audit log model
    stores it as a UUID column; SQLAlchemy rejects plain strings.
    """
    request_id_str = REQUEST_ID_CONTEXT.get(None)
    try:
        request_id: UUID | None = UUID(request_id_str) if request_id_str else None
    except (ValueError, AttributeError):
        request_id = None
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request_id,
    }


def _requester_role(company: Company, current_user: CurrentUser) -> str:
    """Return a role label used for sensitive-field masking."""
    if _ROLE_SUPER_ADMIN in current_user.roles:
        return _ROLE_SUPER_ADMIN
    if company.owner_id == current_user.user_id:
        return "owner"
    return "viewer"


# ---------------------------------------------------------------------------
# SuperAdmin endpoint — registered first to avoid path-param ambiguity
# ---------------------------------------------------------------------------


@router.get(
    "/admin/companies",
    response_model=PaginatedResponse[CompanyListItem],
    summary="List all companies (SuperAdmin only)",
    description="Returns a paginated list of all companies across all tenants.",
)
async def admin_list_companies(
    request: Request,
    _: CurrentUser = Depends(require_super_admin()),
    service: CompanyService = Depends(get_company_service),
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page."),
    status: str | None = Query(None, description="Filter by company status."),
    country: str | None = Query(
        None, description="Filter by ISO 3166-1 alpha-2 country code."
    ),
    search: str | None = Query(
        None, description="Search by legal name (case-insensitive)."
    ),
    include_deleted: bool = Query(False, description="Include soft-deleted companies."),
) -> PaginatedResponse[CompanyListItem]:
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    if country:
        filters["country"] = country
    if search:
        filters["search"] = search
    if include_deleted:
        filters["include_deleted"] = True

    items, total = service.list_all_companies(
        filters=filters,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[CompanyListItem.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message="Companies retrieved.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Company CRUD endpoints (T042)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=StandardResponse[CompanyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new company",
)
@limiter.limit("10/minute")
async def create_company(
    body: CreateCompanyRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
    seed_service: RoleSeedService = Depends(get_role_seed_service),
    member_service: MemberService = Depends(get_member_service),
) -> StandardResponse[CompanyResponse]:
    # Use model_dump() (not exclude_unset) so Pydantic defaults like
    # default_currency="USD" are included in the company record.
    data = body.model_dump()
    actor_id = cast(UUID, current_user.user_id)
    company = service.create_company(
        actor_id=actor_id,
        data=data,
        request_context=_request_context(request),
    )

    # Seed 8 system roles + permissions for the new company (idempotent).
    seed_service.seed_all(company.id, actor_id)

    # Create an active Owner membership for the company creator.
    member_service.create_bootstrap_owner(
        company_id=company.id,
        user_id=actor_id,
        request_context=_request_context(request),
    )

    return StandardResponse(
        data=CompanyResponse.model_validate(company),
        message="Company created successfully.",
        meta=_meta(),
    )


@router.get(
    "/{company_id}",
    response_model=StandardResponse[CompanyDetailResponse],
    summary="Get company details",
)
async def get_company(
    company: Company = Depends(get_current_company),
    current_user: CurrentUser = Depends(require_authenticated),
) -> StandardResponse[CompanyDetailResponse]:
    role = _requester_role(company, current_user)
    detail = CompanyDetailResponse.model_validate(company)
    masked = CompanyDetailResponse.model_validate(detail.for_role(role))
    return StandardResponse(
        data=masked,
        message="Company retrieved.",
        meta=_meta(),
    )


@router.patch(
    "/{company_id}",
    response_model=StandardResponse[CompanyDetailResponse],
    summary="Update company profile (partial update)",
)
async def update_company(
    body: UpdateCompanyRequest,
    request: Request,
    company: Company = Depends(require_admin_or_above()),
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[CompanyDetailResponse]:
    data = body.model_dump(exclude_unset=True)
    updated = service.update_company(
        company_id=company.id,
        actor_id=cast(UUID, current_user.user_id),
        data=data,
        request_context=_request_context(request),
    )
    role = _requester_role(updated, current_user)
    detail = CompanyDetailResponse.model_validate(updated)
    masked = CompanyDetailResponse.model_validate(detail.for_role(role))
    return StandardResponse(
        data=masked,
        message="Company updated.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Status endpoints (T043)
# ---------------------------------------------------------------------------


@router.post(
    "/{company_id}/activate",
    response_model=StandardResponse[ActivateResponse],
    summary="Activate a company",
)
async def activate_company(
    request: Request,
    company: Company = Depends(require_owner()),
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[ActivateResponse]:
    activated = service.activate_company(
        company_id=company.id,
        actor_id=cast(UUID, current_user.user_id),
        request_context=_request_context(request),
    )
    return StandardResponse(
        data=ActivateResponse(
            id=activated.id,
            status=activated.status,
            updated_at=activated.updated_at,
            message="Company activated successfully.",
        ),
        message="Company activated.",
        meta=_meta(),
    )


@router.post(
    "/{company_id}/deactivate",
    response_model=StandardResponse[DeactivateResponse],
    summary="Deactivate a company",
)
async def deactivate_company(
    body: DeactivateRequest,
    request: Request,
    company: Company = Depends(require_owner()),
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[DeactivateResponse]:
    deactivated = service.deactivate_company(
        company_id=company.id,
        actor_id=cast(UUID, current_user.user_id),
        reason=body.reason,
        request_context=_request_context(request),
    )
    return StandardResponse(
        data=DeactivateResponse(
            id=deactivated.id,
            status=deactivated.status,
            updated_at=deactivated.updated_at,
            message="Company deactivated.",
        ),
        message="Company deactivated.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Lifecycle endpoints (T044)
# ---------------------------------------------------------------------------


@router.delete(
    "/{company_id}",
    response_model=StandardResponse[DeleteCompanyResponse],
    summary="Soft-delete a company",
)
async def soft_delete_company(
    body: DeleteCompanyRequest,
    request: Request,
    company: Company = Depends(require_owner()),
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[DeleteCompanyResponse]:
    deleted = service.soft_delete_company(
        company_id=company.id,
        actor_id=cast(UUID, current_user.user_id),
        reason=body.reason,
        force_delete=body.force_delete,
        request_context=_request_context(request),
    )
    return StandardResponse(
        data=DeleteCompanyResponse(
            id=deleted.id,
            status=deleted.status,
            deleted_at=deleted.deleted_at,
            message="Company deleted. Data retained for 90 days before permanent purge.",
        ),
        message="Company deleted.",
        meta=_meta(),
    )


@router.post(
    "/{company_id}/restore",
    response_model=StandardResponse[RestoreResponse],
    summary="Restore a soft-deleted company",
)
async def restore_company(
    company_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[RestoreResponse]:
    # get_current_company cannot be used here — it rejects deleted companies (404).
    # We perform the ownership check manually before delegating to the service.
    raw = service._company_repo.get_by_id(company_id)
    if raw is None:
        raise CompanyNotFoundError()
    is_owner = raw.owner_id == current_user.user_id
    is_super_admin = _ROLE_SUPER_ADMIN in current_user.roles
    if not is_owner and not is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you are not a member of this company.",
        )

    restored = service.restore_company(
        company_id=company_id,
        actor_id=cast(UUID, current_user.user_id),
        request_context=_request_context(request),
    )
    return StandardResponse(
        data=RestoreResponse(
            id=restored.id,
            status=restored.status,
            updated_at=restored.updated_at,
            message="Company restored successfully.",
        ),
        message="Company restored.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Settings and address endpoints (T045)
# ---------------------------------------------------------------------------


@router.patch(
    "/{company_id}/settings",
    response_model=StandardResponse[CompanySettingsResponse],
    summary="Update company settings",
)
async def update_company_settings(
    body: UpdateSettingsRequest,
    company: Company = Depends(require_admin_or_above()),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[CompanySettingsResponse]:
    try:
        validated = service._settings_service.validate_settings(body.settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    merged = service._settings_service.merge_settings(company.settings or {}, validated)
    updated = service._company_repo.update(company, {"settings": merged})
    return StandardResponse(
        data=CompanySettingsResponse(
            company_id=updated.id,
            settings=updated.settings,
            updated_at=updated.updated_at,
        ),
        message="Company settings updated.",
        meta=_meta(),
    )


@router.get(
    "/{company_id}/addresses",
    response_model=StandardResponse[list[CompanyAddressResponse]],
    summary="List company addresses",
)
async def list_addresses(
    company: Company = Depends(get_current_company),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[list[CompanyAddressResponse]]:
    addresses = service._address_repo.list_by_company(company.id)
    return StandardResponse(
        data=[CompanyAddressResponse.model_validate(a) for a in addresses],
        message="Addresses retrieved.",
        meta=_meta(),
    )


@router.post(
    "/{company_id}/addresses",
    response_model=StandardResponse[CompanyAddressResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a company address",
)
async def create_address(
    body: CreateAddressRequest,
    company: Company = Depends(require_admin_or_above()),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[CompanyAddressResponse]:
    address = service._address_repo.create(company.id, body.model_dump())
    return StandardResponse(
        data=CompanyAddressResponse.model_validate(address),
        message="Address created.",
        meta=_meta(),
    )


@router.put(
    "/{company_id}/addresses/{address_id}",
    response_model=StandardResponse[CompanyAddressResponse],
    summary="Update a company address",
)
async def update_address(
    address_id: UUID,
    body: UpdateAddressRequest,
    company: Company = Depends(require_admin_or_above()),
    service: CompanyService = Depends(get_company_service),
) -> StandardResponse[CompanyAddressResponse]:
    address = service._address_repo.get_by_id(address_id, company.id)
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found."
        )
    updated = service._address_repo.update(address, body.model_dump(exclude_unset=True))
    return StandardResponse(
        data=CompanyAddressResponse.model_validate(updated),
        message="Address updated.",
        meta=_meta(),
    )


@router.delete(
    "/{company_id}/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company address",
)
async def delete_address(
    address_id: UUID,
    company: Company = Depends(require_admin_or_above()),
    service: CompanyService = Depends(get_company_service),
) -> None:
    address = service._address_repo.get_by_id(address_id, company.id)
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found."
        )
    service._address_repo.delete(address)


# ---------------------------------------------------------------------------
# Logo upload endpoint (T046)
# ---------------------------------------------------------------------------


@router.post(
    "/{company_id}/logo",
    response_model=StandardResponse[LogoUploadResponse],
    summary="Upload company logo",
)
async def upload_logo(
    logo_file: UploadFile = File(...),
    company: Company = Depends(require_admin_or_above()),
    service: CompanyService = Depends(get_company_service),
    logo_service: CompanyLogoService = Depends(get_company_logo_service),
) -> StandardResponse[LogoUploadResponse]:
    file_bytes = await logo_file.read()
    mime_type = logo_service.validate_file(file_bytes, logo_file.filename or "")
    previous_url = company.logo_url
    logo_url = logo_service.upload(file_bytes, company.id, mime_type)
    logo_service.schedule_previous_cleanup(previous_url)
    service._company_repo.update(company, {"logo_url": logo_url})
    return StandardResponse(
        data=LogoUploadResponse(company_id=company.id, logo_url=logo_url),
        message="Logo uploaded successfully.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Audit log endpoint (T047)
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/audit-logs",
    response_model=AuditLogListResponse,
    summary="List company audit log entries",
)
async def list_audit_logs(
    company: Company = Depends(require_admin_or_above()),
    service: CompanyService = Depends(get_company_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    action: str | None = Query(
        None, description="Filter by action label (e.g. COMPANY_CREATED)."
    ),
) -> AuditLogListResponse:
    filters: dict[str, Any] = {}
    if action:
        filters["action"] = action

    items, total = service._audit_log_repo.list_by_company(
        company.id,
        filters=filters,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return AuditLogListResponse(
        data=PaginatedData(
            items=[AuditLogEntryResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message="Audit log retrieved.",
        meta=_meta(),
    )

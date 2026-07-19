"""Companies schemas package — Pydantic v2 request/response models."""

from modules.companies.schemas.address import (
    CompanyAddressResponse,
    CreateAddressRequest,
    UpdateAddressRequest,
)
from modules.companies.schemas.audit import AuditLogEntryResponse, AuditLogListResponse
from modules.companies.schemas.company import (
    CompanyDetailResponse,
    CompanyListItem,
    CompanyListResponse,
    CompanyResponse,
    CreateCompanyRequest,
    UpdateCompanyRequest,
)
from modules.companies.schemas.settings import (
    CompanySettingsResponse,
    UpdateSettingsRequest,
)
from modules.companies.schemas.status import (
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    DeleteCompanyRequest,
    DeleteCompanyResponse,
    RestoreResponse,
)

__all__ = [
    # address
    "CompanyAddressResponse",
    "CreateAddressRequest",
    "UpdateAddressRequest",
    # audit
    "AuditLogEntryResponse",
    "AuditLogListResponse",
    # company
    "CompanyDetailResponse",
    "CompanyListItem",
    "CompanyListResponse",
    "CompanyResponse",
    "CreateCompanyRequest",
    "UpdateCompanyRequest",
    # settings
    "CompanySettingsResponse",
    "UpdateSettingsRequest",
    # status
    "ActivateResponse",
    "DeactivateRequest",
    "DeactivateResponse",
    "DeleteCompanyRequest",
    "DeleteCompanyResponse",
    "RestoreResponse",
]

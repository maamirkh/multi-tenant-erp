"""Company request/response schemas for the companies module.

Validator functions from ``modules.companies.validators`` are wired to the
relevant fields so Pydantic v2 raises ``ValidationError`` with structured
details when invalid values are submitted.

Sensitive fields (``tax_number``, ``registration_number``) are masked in
``CompanyDetailResponse`` for callers without the required role.  The masking
is applied at serialisation time via a helper method rather than a FastAPI
dependency so that schemas remain decoupled from the HTTP layer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from modules.companies.models.enums import BusinessType
from modules.companies.schemas.address import CompanyAddressResponse
from modules.companies.validators import (
    validate_bcp47_language,
    validate_e164_phone,
    validate_hex_color,
    validate_iana_timezone,
    validate_iso_3166_country,
    validate_iso_4217_currency,
    validate_slug_format,
)

# Roles that may see unmasked sensitive fields.
_SENSITIVE_ROLES: frozenset[str] = frozenset(
    {"owner", "admin", "accountant", "super_admin"}
)
_MASKED_VALUE = "****"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateCompanyRequest(BaseModel):
    """Request body for POST /api/v1/companies."""

    model_config = ConfigDict(from_attributes=True)

    legal_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Official registered company name. Globally unique (case-insensitive).",
    )
    trade_name: str | None = Field(
        None,
        max_length=255,
        description="Doing-business-as (DBA) name. Not required to be unique.",
    )
    email: EmailStr = Field(
        ..., description="Primary company contact email (RFC 5322)."
    )
    phone_primary: str | None = Field(
        None, description="Primary phone in E.164 format."
    )
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code.")
    default_currency: str = Field("USD", description="ISO 4217 currency code.")
    default_language: str = Field("en-US", description="BCP 47 language tag.")
    default_timezone: str = Field("UTC", description="IANA timezone identifier.")
    slug: str | None = Field(
        None,
        description="URL-safe slug. Auto-derived from legal_name if omitted.",
    )

    @field_validator("phone_primary")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_e164_phone(v)

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_iso_3166_country(v)

    @field_validator("default_currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return validate_iso_4217_currency(v)

    @field_validator("default_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        return validate_bcp47_language(v)

    @field_validator("default_timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        return validate_iana_timezone(v)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_slug_format(v)


class UpdateCompanyRequest(BaseModel):
    """Request body for PATCH /api/v1/companies/{company_id}.

    All fields are optional; only provided fields are updated (partial update).
    ``confirm_currency_change`` must be set to ``True`` when changing
    ``default_currency`` while existing transactions exist (the service enforces
    this via ``CurrencyChangeWarningError``).
    """

    model_config = ConfigDict(from_attributes=True)

    legal_name: str | None = Field(None, min_length=2, max_length=255)
    slug: str | None = Field(
        None, description="URL-safe slug. Immutable after first activation."
    )
    trade_name: str | None = Field(None, max_length=255)
    email: EmailStr | None = Field(None)
    phone_primary: str | None = Field(None)
    phone_secondary: str | None = Field(None)
    website: str | None = Field(None, max_length=2048)
    tax_number: str | None = Field(None, max_length=50)
    registration_number: str | None = Field(None, max_length=50)
    business_category: str | None = Field(None, max_length=100)
    business_type: BusinessType | None = Field(None)
    incorporation_date: date | None = Field(None)
    default_currency: str | None = Field(None)
    default_language: str | None = Field(None)
    default_timezone: str | None = Field(None)
    country: str | None = Field(None)
    fiscal_year_start_month: int | None = Field(None, ge=1, le=12)
    date_format: str | None = Field(None, max_length=20)
    brand_color_primary: str | None = Field(None)
    brand_color_secondary: str | None = Field(None)
    tagline: str | None = Field(None, max_length=255)
    confirm_currency_change: bool = Field(
        False,
        description="Set to true to confirm a currency change with existing transactions.",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_slug_format(v)

    @field_validator("phone_primary", "phone_secondary")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_e164_phone(v)

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_iso_3166_country(v)

    @field_validator("default_currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_iso_4217_currency(v)

    @field_validator("default_language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_bcp47_language(v)

    @field_validator("default_timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_iana_timezone(v)

    @field_validator("brand_color_primary", "brand_color_secondary")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_hex_color(v)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CompanyResponse(BaseModel):
    """Summary company record — returned by POST /companies (creation) and list items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Company unique identifier.")
    legal_name: str = Field(..., description="Official registered company name.")
    trade_name: str | None = Field(None, description="DBA name.")
    slug: str = Field(..., description="URL-safe company identifier.")
    status: str = Field(..., description="Company lifecycle status.")
    owner_id: UUID = Field(..., description="User who owns this company.")
    email: str = Field(..., description="Primary company contact email.")
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code.")
    default_currency: str | None = Field(None, description="ISO 4217 currency code.")
    default_language: str | None = Field(None, description="BCP 47 language tag.")
    default_timezone: str | None = Field(None, description="IANA timezone identifier.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-updated timestamp.")


class CompanyDetailResponse(BaseModel):
    """Full company record returned by GET /companies/{id}.

    Sensitive fields (``tax_number``, ``registration_number``) are masked to
    ``"****"`` for callers without the required role.  Use
    ``for_role(requester_role)`` to serialise with appropriate masking.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_name: str
    trade_name: str | None = None
    slug: str
    status: str
    owner_id: UUID
    primary_admin_id: UUID | None = None
    email: str
    phone_primary: str | None = None
    phone_secondary: str | None = None
    website: str | None = None
    tax_number: str | None = None
    registration_number: str | None = None
    business_category: str | None = None
    business_type: BusinessType | None = None
    incorporation_date: date | None = None
    default_currency: str | None = None
    default_timezone: str | None = None
    default_language: str | None = None
    country: str | None = None
    fiscal_year_start_month: int | None = None
    date_format: str | None = None
    number_format: dict[str, Any] = Field(default_factory=dict)
    logo_url: str | None = None
    brand_color_primary: str | None = None
    brand_color_secondary: str | None = None
    tagline: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    addresses: list[CompanyAddressResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    def for_role(self, requester_role: str) -> dict[str, Any]:
        """Return a serialisable dict with sensitive fields masked if role is insufficient.

        Args:
            requester_role: The role of the API caller (e.g. ``"viewer"``, ``"owner"``).

        Returns:
            Dict representation with ``tax_number`` and ``registration_number``
            masked to ``"****"`` for unauthorised roles.
        """
        data = self.model_dump()
        if requester_role not in _SENSITIVE_ROLES:
            if data.get("tax_number") is not None:
                data["tax_number"] = _MASKED_VALUE
            if data.get("registration_number") is not None:
                data["registration_number"] = _MASKED_VALUE
        return data


class CompanyListItem(BaseModel):
    """Compact company record used in paginated list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Company unique identifier.")
    legal_name: str = Field(..., description="Official registered company name.")
    slug: str = Field(..., description="URL-safe company identifier.")
    status: str = Field(..., description="Company lifecycle status.")
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code.")
    default_currency: str | None = Field(None, description="ISO 4217 currency code.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")


# Convenience type aliases used by routers
CompanyListResponse = list[CompanyListItem]

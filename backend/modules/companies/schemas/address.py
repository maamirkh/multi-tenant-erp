"""Address schemas for the companies module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.companies.models.enums import AddressType
from modules.companies.validators import validate_iso_3166_country


class CreateAddressRequest(BaseModel):
    """Request body for POST /companies/{id}/addresses."""

    model_config = ConfigDict(from_attributes=True)

    address_type: AddressType = Field(..., description="Purpose of this address.")
    street_line_1: str = Field(
        ..., min_length=1, max_length=255, description="Primary street address."
    )
    street_line_2: str | None = Field(
        None, max_length=255, description="Secondary address line."
    )
    city: str = Field(
        ..., min_length=1, max_length=100, description="City or municipality."
    )
    state_province: str | None = Field(
        None, max_length=100, description="State, province, or region."
    )
    postal_code: str | None = Field(
        None, max_length=20, description="Postal or ZIP code."
    )
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code.")
    is_primary: bool = Field(False, description="Mark as primary address of this type.")

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        return validate_iso_3166_country(v)


class UpdateAddressRequest(BaseModel):
    """Request body for PUT /companies/{id}/addresses/{address_id}."""

    model_config = ConfigDict(from_attributes=True)

    address_type: AddressType | None = Field(
        None, description="Purpose of this address."
    )
    street_line_1: str | None = Field(
        None, min_length=1, max_length=255, description="Primary street address."
    )
    street_line_2: str | None = Field(
        None, max_length=255, description="Secondary address line."
    )
    city: str | None = Field(
        None, min_length=1, max_length=100, description="City or municipality."
    )
    state_province: str | None = Field(
        None, max_length=100, description="State, province, or region."
    )
    postal_code: str | None = Field(
        None, max_length=20, description="Postal or ZIP code."
    )
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code.")
    is_primary: bool | None = Field(
        None, description="Mark as primary address of this type."
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_iso_3166_country(v)


class CompanyAddressResponse(BaseModel):
    """Address record returned in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Address unique identifier.")
    company_id: UUID = Field(..., description="Owning company identifier.")
    address_type: AddressType = Field(..., description="Purpose of this address.")
    street_line_1: str = Field(..., description="Primary street address.")
    street_line_2: str | None = Field(None, description="Secondary address line.")
    city: str = Field(..., description="City or municipality.")
    state_province: str | None = Field(None, description="State, province, or region.")
    postal_code: str | None = Field(None, description="Postal or ZIP code.")
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code.")
    is_primary: bool = Field(
        ..., description="True if this is the primary address of its type."
    )
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-updated timestamp.")

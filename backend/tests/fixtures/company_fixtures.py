"""Company test fixtures — pure data factories with no database interaction.

Used by unit and integration test suites that need company-shaped test data.
"""

from __future__ import annotations

import uuid
from typing import Any


def make_address_data(
    *,
    address_type: str = "registered",
    street_line_1: str = "123 Business Ave",
    street_line_2: str | None = None,
    city: str = "San Francisco",
    state_province: str | None = "CA",
    postal_code: str | None = "94105",
    country: str = "US",
    is_primary: bool = True,
) -> dict[str, Any]:
    """Return a dict with all required address fields."""
    return {
        "address_type": address_type,
        "street_line_1": street_line_1,
        "street_line_2": street_line_2,
        "city": city,
        "state_province": state_province,
        "postal_code": postal_code,
        "country": country,
        "is_primary": is_primary,
    }


def make_settings_data(
    *,
    default_currency: str = "USD",
    default_timezone: str = "America/Los_Angeles",
    default_language: str = "en",
    date_format: str = "MM/DD/YYYY",
    number_format: dict[str, Any] | None = None,
    fiscal_year_start_month: int = 1,
) -> dict[str, Any]:
    """Return a dict with all required company settings fields."""
    return {
        "default_currency": default_currency,
        "default_timezone": default_timezone,
        "default_language": default_language,
        "date_format": date_format,
        "number_format": number_format or {"decimal": ".", "thousands": ","},
        "fiscal_year_start_month": fiscal_year_start_month,
    }


def make_company_data(
    *,
    legal_name: str = "Acme Corporation LLC",
    trade_name: str | None = "Acme Corp",
    slug: str | None = None,
    email: str = "contact@acmecorp.example.com",
    phone_primary: str = "+14155550100",
    phone_secondary: str | None = None,
    website: str | None = "https://acmecorp.example.com",
    tax_number: str | None = "12-3456789",
    registration_number: str | None = "CA-2024-001",
    business_category: str = "Technology",
    business_type: str = "llc",
    country: str = "US",
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Return a dict with all required company fields.

    ``slug`` defaults to a UUID-based value to guarantee uniqueness in tests.
    ``owner_id`` defaults to a random UUID to allow creation without a real user.
    """
    return {
        "legal_name": legal_name,
        "trade_name": trade_name,
        "slug": slug or f"acme-corp-{uuid.uuid4().hex[:8]}",
        "email": email,
        "phone_primary": phone_primary,
        "phone_secondary": phone_secondary,
        "website": website,
        "tax_number": tax_number,
        "registration_number": registration_number,
        "business_category": business_category,
        "business_type": business_type,
        "country": country,
        "owner_id": uuid.UUID(owner_id) if owner_id else uuid.uuid4(),
        **make_settings_data(),
    }

"""Unit tests for modules/companies/validators.py.

Each validator is tested with:
  - One valid input case (returns the validated/normalised value)
  - Three invalid input cases (boundary, format, wrong type) — each must raise ValueError

No database, HTTP, or filesystem interaction — pure unit tests.
"""

from __future__ import annotations

import pytest

from modules.companies.validators import (
    validate_bcp47_language,
    validate_e164_phone,
    validate_hex_color,
    validate_iana_timezone,
    validate_iso_3166_country,
    validate_iso_4217_currency,
    validate_slug_format,
)

# ---------------------------------------------------------------------------
# validate_iso_4217_currency
# ---------------------------------------------------------------------------


class TestValidateIso4217Currency:
    def test_valid_usd(self) -> None:
        assert validate_iso_4217_currency("USD") == "USD"

    def test_valid_lowercase_normalised(self) -> None:
        assert validate_iso_4217_currency("eur") == "EUR"

    def test_invalid_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="not a valid ISO 4217"):
            validate_iso_4217_currency("XYZ")

    def test_invalid_too_short(self) -> None:
        with pytest.raises(ValueError, match="not a valid ISO 4217"):
            validate_iso_4217_currency("US")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_iso_4217_currency(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_iana_timezone
# ---------------------------------------------------------------------------


class TestValidateIanaTimezone:
    def test_valid_new_york(self) -> None:
        assert validate_iana_timezone("America/New_York") == "America/New_York"

    def test_valid_utc(self) -> None:
        assert validate_iana_timezone("UTC") == "UTC"

    def test_invalid_fake_zone(self) -> None:
        with pytest.raises(ValueError, match="not a valid IANA"):
            validate_iana_timezone("Fake/Zone")

    def test_invalid_empty_string(self) -> None:
        with pytest.raises(ValueError, match="not a valid IANA"):
            validate_iana_timezone("")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_iana_timezone(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_iso_3166_country
# ---------------------------------------------------------------------------


class TestValidateIso3166Country:
    def test_valid_us(self) -> None:
        assert validate_iso_3166_country("US") == "US"

    def test_valid_lowercase_normalised(self) -> None:
        assert validate_iso_3166_country("gb") == "GB"

    def test_invalid_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="not a valid ISO 3166-1"):
            validate_iso_3166_country("XX")

    def test_invalid_too_long(self) -> None:
        with pytest.raises(ValueError, match="not a valid ISO 3166-1"):
            validate_iso_3166_country("USA")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_iso_3166_country(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_hex_color
# ---------------------------------------------------------------------------


class TestValidateHexColor:
    def test_valid_six_digit_lowercase_normalised(self) -> None:
        assert validate_hex_color("#ff5733") == "#FF5733"

    def test_valid_three_digit_expanded(self) -> None:
        assert validate_hex_color("#F00") == "#FF0000"

    def test_valid_without_hash(self) -> None:
        assert validate_hex_color("AABBCC") == "#AABBCC"

    def test_invalid_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="not a valid hex colour"):
            validate_hex_color("#12345")

    def test_invalid_non_hex_chars(self) -> None:
        with pytest.raises(ValueError, match="not a valid hex colour"):
            validate_hex_color("#GGHHII")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_hex_color(0xFF5733)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_e164_phone
# ---------------------------------------------------------------------------


class TestValidateE164Phone:
    def test_valid_us_number(self) -> None:
        assert validate_e164_phone("+14155550100") == "+14155550100"

    def test_valid_uk_number(self) -> None:
        assert validate_e164_phone("+447911123456") == "+447911123456"

    def test_invalid_no_plus(self) -> None:
        with pytest.raises(ValueError, match="not a valid E.164"):
            validate_e164_phone("14155550100")

    def test_invalid_starts_with_zero(self) -> None:
        with pytest.raises(ValueError, match="not a valid E.164"):
            validate_e164_phone("+04155550100")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_e164_phone(14155550100)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_slug_format
# ---------------------------------------------------------------------------


class TestValidateSlugFormat:
    def test_valid_simple_slug(self) -> None:
        assert validate_slug_format("acme-corp") == "acme-corp"

    def test_valid_alphanumeric_only(self) -> None:
        assert validate_slug_format("acmecorp2024") == "acmecorp2024"

    def test_invalid_consecutive_hyphens(self) -> None:
        with pytest.raises(ValueError, match="consecutive hyphens"):
            validate_slug_format("a--b")

    def test_invalid_starts_with_hyphen(self) -> None:
        with pytest.raises(ValueError, match="not a valid slug"):
            validate_slug_format("-acme-corp")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_slug_format(123)  # type: ignore[arg-type]

    def test_invalid_uppercase_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a valid slug"):
            validate_slug_format("Acme-Corp")

    def test_invalid_single_char(self) -> None:
        with pytest.raises(ValueError, match="not a valid slug"):
            validate_slug_format("a")


# ---------------------------------------------------------------------------
# validate_bcp47_language
# ---------------------------------------------------------------------------


class TestValidateBcp47Language:
    def test_valid_en_us(self) -> None:
        assert validate_bcp47_language("en-US") == "en-US"

    def test_valid_base_language(self) -> None:
        assert validate_bcp47_language("fr") == "fr"

    def test_invalid_unsupported_tag(self) -> None:
        with pytest.raises(ValueError, match="not a supported BCP 47"):
            validate_bcp47_language("xx-YY")

    def test_invalid_empty_string(self) -> None:
        with pytest.raises(ValueError, match="not a supported BCP 47"):
            validate_bcp47_language("")

    def test_invalid_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_bcp47_language(42)  # type: ignore[arg-type]

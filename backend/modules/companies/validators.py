"""Companies module field validators.

Pure functions with no side effects.  No database, HTTP, or ORM dependency.
Each function accepts a raw string value, validates (and optionally normalizes)
it, and returns the validated/normalized value, or raises ``ValueError`` with a
descriptive message on failure.

Used by Pydantic schemas (Phase 6) and service-layer pre-checks.
"""

from __future__ import annotations

import re
import zoneinfo

# ---------------------------------------------------------------------------
# ISO 4217 — Currency codes (alphabetic, 3-letter)
# Source: ISO 4217:2015 active codes (180 codes)
# ---------------------------------------------------------------------------

_ISO_4217_CODES: frozenset[str] = frozenset(
    {
        "AED",
        "AFN",
        "ALL",
        "AMD",
        "ANG",
        "AOA",
        "ARS",
        "AUD",
        "AWG",
        "AZN",
        "BAM",
        "BBD",
        "BDT",
        "BGN",
        "BHD",
        "BIF",
        "BMD",
        "BND",
        "BOB",
        "BOV",
        "BRL",
        "BSD",
        "BTN",
        "BWP",
        "BYN",
        "BZD",
        "CAD",
        "CDF",
        "CHE",
        "CHF",
        "CHW",
        "CLF",
        "CLP",
        "CNY",
        "COP",
        "COU",
        "CRC",
        "CUC",
        "CUP",
        "CVE",
        "CZK",
        "DJF",
        "DKK",
        "DOP",
        "DZD",
        "EGP",
        "ERN",
        "ETB",
        "EUR",
        "FJD",
        "FKP",
        "GBP",
        "GEL",
        "GHS",
        "GIP",
        "GMD",
        "GNF",
        "GTQ",
        "GYD",
        "HKD",
        "HNL",
        "HRK",
        "HTG",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "IQD",
        "IRR",
        "ISK",
        "JMD",
        "JOD",
        "JPY",
        "KES",
        "KGS",
        "KHR",
        "KMF",
        "KPW",
        "KRW",
        "KWD",
        "KYD",
        "KZT",
        "LAK",
        "LBP",
        "LKR",
        "LRD",
        "LSL",
        "LYD",
        "MAD",
        "MDL",
        "MGA",
        "MKD",
        "MMK",
        "MNT",
        "MOP",
        "MRU",
        "MUR",
        "MVR",
        "MWK",
        "MXN",
        "MXV",
        "MYR",
        "MZN",
        "NAD",
        "NGN",
        "NIO",
        "NOK",
        "NPR",
        "NZD",
        "OMR",
        "PAB",
        "PEN",
        "PGK",
        "PHP",
        "PKR",
        "PLN",
        "PYG",
        "QAR",
        "RON",
        "RSD",
        "RUB",
        "RWF",
        "SAR",
        "SBD",
        "SCR",
        "SDG",
        "SEK",
        "SGD",
        "SHP",
        "SLE",
        "SLL",
        "SOS",
        "SRD",
        "SSP",
        "STN",
        "SVC",
        "SYP",
        "SZL",
        "THB",
        "TJS",
        "TMT",
        "TND",
        "TOP",
        "TRY",
        "TTD",
        "TWD",
        "TZS",
        "UAH",
        "UGX",
        "USD",
        "USN",
        "UYI",
        "UYU",
        "UYW",
        "UZS",
        "VES",
        "VND",
        "VUV",
        "WST",
        "XAF",
        "XAG",
        "XAU",
        "XBA",
        "XBB",
        "XBC",
        "XBD",
        "XCD",
        "XDR",
        "XOF",
        "XPD",
        "XPF",
        "XPT",
        "XSU",
        "XTS",
        "XUA",
        "XXX",
        "YER",
        "ZAR",
        "ZMW",
        "ZWL",
    }
)


def validate_iso_4217_currency(value: str) -> str:
    """Validate an ISO 4217 alphabetic currency code.

    Args:
        value: Raw input string (e.g. ``"USD"``, ``"EUR"``).

    Returns:
        The validated code in uppercase.

    Raises:
        ValueError: If the code is not a recognised ISO 4217 code.
    """
    if not isinstance(value, str):
        raise ValueError(f"Currency code must be a string, got {type(value).__name__}.")
    normalised = value.strip().upper()
    if normalised not in _ISO_4217_CODES:
        raise ValueError(
            f"{value!r} is not a valid ISO 4217 currency code. "
            "Expected a 3-letter alphabetic code such as 'USD', 'EUR', or 'GBP'."
        )
    return normalised


# ---------------------------------------------------------------------------
# IANA Timezone — validated against the system's zoneinfo database
# ---------------------------------------------------------------------------


def validate_iana_timezone(value: str) -> str:
    """Validate an IANA timezone identifier.

    Args:
        value: Raw input string (e.g. ``"America/New_York"``).

    Returns:
        The validated timezone string unchanged.

    Raises:
        ValueError: If the identifier is not in ``zoneinfo.available_timezones()``.
    """
    if not isinstance(value, str):
        raise ValueError(f"Timezone must be a string, got {type(value).__name__}.")
    stripped = value.strip()
    if stripped not in zoneinfo.available_timezones():
        raise ValueError(
            f"{value!r} is not a valid IANA timezone identifier. "
            "Examples: 'America/New_York', 'Europe/London', 'Asia/Tokyo'."
        )
    return stripped


# ---------------------------------------------------------------------------
# ISO 3166-1 alpha-2 — Country codes (249 codes)
# Source: ISO 3166-1 Maintenance Agency, as of 2024
# ---------------------------------------------------------------------------

_ISO_3166_CODES: frozenset[str] = frozenset(
    {
        "AD",
        "AE",
        "AF",
        "AG",
        "AI",
        "AL",
        "AM",
        "AO",
        "AQ",
        "AR",
        "AS",
        "AT",
        "AU",
        "AW",
        "AX",
        "AZ",
        "BA",
        "BB",
        "BD",
        "BE",
        "BF",
        "BG",
        "BH",
        "BI",
        "BJ",
        "BL",
        "BM",
        "BN",
        "BO",
        "BQ",
        "BR",
        "BS",
        "BT",
        "BV",
        "BW",
        "BY",
        "BZ",
        "CA",
        "CC",
        "CD",
        "CF",
        "CG",
        "CH",
        "CI",
        "CK",
        "CL",
        "CM",
        "CN",
        "CO",
        "CR",
        "CU",
        "CV",
        "CW",
        "CX",
        "CY",
        "CZ",
        "DE",
        "DJ",
        "DK",
        "DM",
        "DO",
        "DZ",
        "EC",
        "EE",
        "EG",
        "EH",
        "ER",
        "ES",
        "ET",
        "FI",
        "FJ",
        "FK",
        "FM",
        "FO",
        "FR",
        "GA",
        "GB",
        "GD",
        "GE",
        "GF",
        "GG",
        "GH",
        "GI",
        "GL",
        "GM",
        "GN",
        "GP",
        "GQ",
        "GR",
        "GS",
        "GT",
        "GU",
        "GW",
        "GY",
        "HK",
        "HM",
        "HN",
        "HR",
        "HT",
        "HU",
        "ID",
        "IE",
        "IL",
        "IM",
        "IN",
        "IO",
        "IQ",
        "IR",
        "IS",
        "IT",
        "JE",
        "JM",
        "JO",
        "JP",
        "KE",
        "KG",
        "KH",
        "KI",
        "KM",
        "KN",
        "KP",
        "KR",
        "KW",
        "KY",
        "KZ",
        "LA",
        "LB",
        "LC",
        "LI",
        "LK",
        "LR",
        "LS",
        "LT",
        "LU",
        "LV",
        "LY",
        "MA",
        "MC",
        "MD",
        "ME",
        "MF",
        "MG",
        "MH",
        "MK",
        "ML",
        "MM",
        "MN",
        "MO",
        "MP",
        "MQ",
        "MR",
        "MS",
        "MT",
        "MU",
        "MV",
        "MW",
        "MX",
        "MY",
        "MZ",
        "NA",
        "NC",
        "NE",
        "NF",
        "NG",
        "NI",
        "NL",
        "NO",
        "NP",
        "NR",
        "NU",
        "NZ",
        "OM",
        "PA",
        "PE",
        "PF",
        "PG",
        "PH",
        "PK",
        "PL",
        "PM",
        "PN",
        "PR",
        "PS",
        "PT",
        "PW",
        "PY",
        "QA",
        "RE",
        "RO",
        "RS",
        "RU",
        "RW",
        "SA",
        "SB",
        "SC",
        "SD",
        "SE",
        "SG",
        "SH",
        "SI",
        "SJ",
        "SK",
        "SL",
        "SM",
        "SN",
        "SO",
        "SR",
        "SS",
        "ST",
        "SV",
        "SX",
        "SY",
        "SZ",
        "TC",
        "TD",
        "TF",
        "TG",
        "TH",
        "TJ",
        "TK",
        "TL",
        "TM",
        "TN",
        "TO",
        "TR",
        "TT",
        "TV",
        "TW",
        "TZ",
        "UA",
        "UG",
        "UM",
        "US",
        "UY",
        "UZ",
        "VA",
        "VC",
        "VE",
        "VG",
        "VI",
        "VN",
        "VU",
        "WF",
        "WS",
        "YE",
        "YT",
        "ZA",
        "ZM",
        "ZW",
    }
)


def validate_iso_3166_country(value: str) -> str:
    """Validate an ISO 3166-1 alpha-2 country code.

    Args:
        value: Raw input string (e.g. ``"US"``, ``"GB"``).

    Returns:
        The validated code in uppercase.

    Raises:
        ValueError: If the code is not a recognised ISO 3166-1 alpha-2 code.
    """
    if not isinstance(value, str):
        raise ValueError(f"Country code must be a string, got {type(value).__name__}.")
    normalised = value.strip().upper()
    if normalised not in _ISO_3166_CODES:
        raise ValueError(
            f"{value!r} is not a valid ISO 3166-1 alpha-2 country code. "
            "Expected a 2-letter code such as 'US', 'GB', or 'DE'."
        )
    return normalised


# ---------------------------------------------------------------------------
# Hex colour — normalise to #RRGGBB uppercase
# ---------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r"^#?(?P<hex>[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def validate_hex_color(value: str) -> str:
    """Validate and normalise a CSS hex colour string.

    Accepts 3- or 6-digit hex with or without a leading ``#``.
    Normalises 3-digit shorthand (``#RGB``) to 6-digit (``#RRGGBB``).

    Args:
        value: Raw input string (e.g. ``"#ff5733"``, ``"F00"``).

    Returns:
        Normalised colour in ``#RRGGBB`` uppercase (e.g. ``"#FF5733"``).

    Raises:
        ValueError: If the string is not a valid hex colour.
    """
    if not isinstance(value, str):
        raise ValueError(f"Hex colour must be a string, got {type(value).__name__}.")
    match = _HEX_COLOR_RE.match(value.strip())
    if not match:
        raise ValueError(
            f"{value!r} is not a valid hex colour. "
            "Expected 3 or 6 hex digits, optionally prefixed with '#' (e.g. '#FF5733')."
        )
    hex_digits = match.group("hex").upper()
    if len(hex_digits) == 3:
        hex_digits = "".join(c * 2 for c in hex_digits)
    return f"#{hex_digits}"


# ---------------------------------------------------------------------------
# E.164 phone number
# ---------------------------------------------------------------------------

_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_e164_phone(value: str) -> str:
    """Validate a phone number in E.164 international format.

    Format: ``+<country_code><subscriber_number>``, 2–15 digits after ``+``,
    first digit of the country code must be 1–9.

    Args:
        value: Raw input string (e.g. ``"+14155550100"``).

    Returns:
        The validated phone number unchanged.

    Raises:
        ValueError: If the value does not match E.164 format.
    """
    if not isinstance(value, str):
        raise ValueError(f"Phone number must be a string, got {type(value).__name__}.")
    stripped = value.strip()
    if not _E164_RE.match(stripped):
        raise ValueError(
            f"{value!r} is not a valid E.164 phone number. "
            "Expected format: '+<country_code><number>' with 2–15 digits total "
            "(e.g. '+14155550100')."
        )
    return stripped


# ---------------------------------------------------------------------------
# Slug — URL-safe lowercase identifier
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$")
_CONSECUTIVE_HYPHENS_RE = re.compile(r"-{2,}")


def validate_slug_format(value: str) -> str:
    """Validate a company URL slug.

    Rules:
    - 2–100 characters long (first and last must be alphanumeric).
    - Only lowercase letters, digits, and single hyphens.
    - No consecutive hyphens (``--``).
    - No leading or trailing hyphens.

    Args:
        value: Raw input string (e.g. ``"acme-corp"``).

    Returns:
        The validated slug unchanged.

    Raises:
        ValueError: If the slug does not meet the format requirements.
    """
    if not isinstance(value, str):
        raise ValueError(f"Slug must be a string, got {type(value).__name__}.")
    stripped = value.strip()
    if _CONSECUTIVE_HYPHENS_RE.search(stripped):
        raise ValueError(
            f"{value!r} contains consecutive hyphens. "
            "A slug must use single hyphens only (e.g. 'acme-corp')."
        )
    if not _SLUG_RE.match(stripped):
        raise ValueError(
            f"{value!r} is not a valid slug. "
            "Use 2–100 lowercase letters, digits, and single hyphens. "
            "Must start and end with a letter or digit (e.g. 'acme-corp-2024')."
        )
    return stripped


# ---------------------------------------------------------------------------
# BCP 47 — Language tags
# Subset: ISO 639-1 language + optional ISO 3166-1 region
# ---------------------------------------------------------------------------

_BCP47_SUPPORTED: frozenset[str] = frozenset(
    {
        # Most widely used BCP 47 language tags (base language + common regional variants)
        "af",
        "af-ZA",
        "ar",
        "ar-AE",
        "ar-BH",
        "ar-DZ",
        "ar-EG",
        "ar-IQ",
        "ar-JO",
        "ar-KW",
        "ar-LB",
        "ar-LY",
        "ar-MA",
        "ar-OM",
        "ar-QA",
        "ar-SA",
        "ar-SY",
        "ar-TN",
        "ar-YE",
        "az",
        "az-AZ",
        "be",
        "be-BY",
        "bg",
        "bg-BG",
        "bs",
        "bs-BA",
        "ca",
        "ca-ES",
        "cs",
        "cs-CZ",
        "cy",
        "cy-GB",
        "da",
        "da-DK",
        "de",
        "de-AT",
        "de-CH",
        "de-DE",
        "de-LI",
        "de-LU",
        "el",
        "el-GR",
        "en",
        "en-AU",
        "en-BZ",
        "en-CA",
        "en-CB",
        "en-GB",
        "en-IE",
        "en-IN",
        "en-JM",
        "en-NZ",
        "en-PH",
        "en-SG",
        "en-TT",
        "en-US",
        "en-ZA",
        "en-ZW",
        "es",
        "es-AR",
        "es-BO",
        "es-CL",
        "es-CO",
        "es-CR",
        "es-DO",
        "es-EC",
        "es-ES",
        "es-GT",
        "es-HN",
        "es-MX",
        "es-NI",
        "es-PA",
        "es-PE",
        "es-PR",
        "es-PY",
        "es-SV",
        "es-UY",
        "es-VE",
        "et",
        "et-EE",
        "eu",
        "eu-ES",
        "fa",
        "fa-IR",
        "fi",
        "fi-FI",
        "fo",
        "fo-FO",
        "fr",
        "fr-BE",
        "fr-CA",
        "fr-CH",
        "fr-FR",
        "fr-LU",
        "fr-MC",
        "gl",
        "gl-ES",
        "gu",
        "gu-IN",
        "he",
        "he-IL",
        "hi",
        "hi-IN",
        "hr",
        "hr-BA",
        "hr-HR",
        "hu",
        "hu-HU",
        "hy",
        "hy-AM",
        "id",
        "id-ID",
        "is",
        "is-IS",
        "it",
        "it-CH",
        "it-IT",
        "ja",
        "ja-JP",
        "ka",
        "ka-GE",
        "kk",
        "kk-KZ",
        "kn",
        "kn-IN",
        "ko",
        "ko-KR",
        "ky",
        "ky-KG",
        "lt",
        "lt-LT",
        "lv",
        "lv-LV",
        "mi",
        "mi-NZ",
        "mk",
        "mk-MK",
        "ml",
        "ml-IN",
        "mn",
        "mn-MN",
        "mr",
        "mr-IN",
        "ms",
        "ms-BN",
        "ms-MY",
        "mt",
        "mt-MT",
        "nb",
        "nb-NO",
        "nl",
        "nl-BE",
        "nl-NL",
        "nn",
        "nn-NO",
        "pa",
        "pa-IN",
        "pl",
        "pl-PL",
        "pt",
        "pt-BR",
        "pt-PT",
        "ro",
        "ro-RO",
        "ru",
        "ru-RU",
        "sa",
        "sa-IN",
        "sk",
        "sk-SK",
        "sl",
        "sl-SI",
        "sq",
        "sq-AL",
        "sr",
        "sr-BA",
        "sr-CS",
        "sr-RS",
        "sv",
        "sv-FI",
        "sv-SE",
        "sw",
        "sw-KE",
        "ta",
        "ta-IN",
        "te",
        "te-IN",
        "th",
        "th-TH",
        "tl",
        "tl-PH",
        "tr",
        "tr-TR",
        "tt",
        "tt-RU",
        "uk",
        "uk-UA",
        "ur",
        "ur-PK",
        "uz",
        "uz-UZ",
        "vi",
        "vi-VN",
        "zh",
        "zh-CN",
        "zh-HK",
        "zh-MO",
        "zh-SG",
        "zh-TW",
        "zu",
        "zu-ZA",
    }
)


def validate_bcp47_language(value: str) -> str:
    """Validate a BCP 47 language tag against the supported locale list.

    Accepts both base language codes (``"en"``) and language-region pairs
    (``"en-US"``).  Only the tags in the supported locale set are accepted.

    Args:
        value: Raw input string (e.g. ``"en-US"``, ``"fr"``).

    Returns:
        The validated tag unchanged.

    Raises:
        ValueError: If the tag is not in the supported locale set.
    """
    if not isinstance(value, str):
        raise ValueError(f"Language tag must be a string, got {type(value).__name__}.")
    stripped = value.strip()
    if stripped not in _BCP47_SUPPORTED:
        raise ValueError(
            f"{value!r} is not a supported BCP 47 language tag. "
            "Examples of supported tags: 'en', 'en-US', 'fr', 'fr-FR', 'zh-CN'."
        )
    return stripped

"""Users & Roles module field validators.

Pure functions with no side effects.  No database, HTTP, or ORM dependency.
Each function validates (and optionally normalises) a raw value, returning
the validated value or raising ``ValueError`` on failure.

Used by Pydantic schemas and service-layer pre-checks.

Spec reference: spec Section 9 (Validation Rules).
"""

from __future__ import annotations

import re

from modules.users_roles.constants import MAX_RANK, MIN_RANK, OWNER_RANK

# ---------------------------------------------------------------------------
# Email format (RFC 5322 simplified — mirrors auth module pattern)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


def validate_email_format(value: str) -> str:
    """Validate an email address format.

    Returns:
        The email address stripped and lowercased.

    Raises:
        ValueError: If the email format is invalid.
    """
    stripped = value.strip().lower()
    if not _EMAIL_RE.match(stripped) or len(stripped) > 254:
        raise ValueError(f"{value!r} is not a valid email address.")
    return stripped


# ---------------------------------------------------------------------------
# Phone format (E.164) — reuses companies module pattern
# ---------------------------------------------------------------------------

_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_phone_format(value: str) -> str:
    """Validate a phone number in E.164 international format.

    Returns:
        The validated phone number unchanged.

    Raises:
        ValueError: If the value does not match E.164 format.
    """
    stripped = value.strip()
    if not _E164_RE.match(stripped):
        raise ValueError(
            f"{value!r} is not a valid E.164 phone number. "
            "Expected format: '+<country_code><number>' with 2-15 digits."
        )
    return stripped


# ---------------------------------------------------------------------------
# Employee ID format
# ---------------------------------------------------------------------------

_EMPLOYEE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_.]{0,48}[A-Za-z0-9]$")


def validate_employee_id(value: str) -> str:
    """Validate a company-assigned employee identifier.

    Rules:
    - 2-50 characters
    - Alphanumeric, hyphens, underscores, dots
    - Must start and end with alphanumeric

    Returns:
        The validated employee ID stripped.

    Raises:
        ValueError: If the format is invalid.
    """
    stripped = value.strip()
    if len(stripped) < 2 or not _EMPLOYEE_ID_RE.match(stripped):
        raise ValueError(
            f"{value!r} is not a valid employee ID. "
            "Use 2-50 alphanumeric characters, hyphens, underscores, or dots."
        )
    return stripped


# ---------------------------------------------------------------------------
# Role name
# ---------------------------------------------------------------------------

_ROLE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 \-]{0,48}[A-Za-z0-9]$")


def validate_role_name(value: str) -> str:
    """Validate a role display name.

    Rules:
    - 2-50 characters
    - Must start with a letter
    - Letters, digits, spaces, hyphens allowed
    - Must end with letter or digit

    Returns:
        The validated role name stripped.

    Raises:
        ValueError: If the format is invalid.
    """
    stripped = value.strip()
    if len(stripped) < 2 or not _ROLE_NAME_RE.match(stripped):
        raise ValueError(
            f"{value!r} is not a valid role name. "
            "Use 2-50 characters starting with a letter; letters, digits, spaces, and hyphens allowed."
        )
    return stripped


# ---------------------------------------------------------------------------
# Rank range
# ---------------------------------------------------------------------------


def validate_rank(value: int, *, actor_rank: int | None = None) -> int:
    """Validate a numeric role rank.

    Rules:
    - Must be between MIN_RANK (1) and MAX_RANK (100)
    - Custom roles cannot use OWNER_RANK (100)
    - If actor_rank provided, rank must be strictly less than actor_rank

    Returns:
        The validated rank.

    Raises:
        ValueError: If the rank is out of range or violates hierarchy.
    """
    if value < MIN_RANK or value > MAX_RANK:
        raise ValueError(
            f"Rank must be between {MIN_RANK} and {MAX_RANK}, got {value}."
        )
    if value == OWNER_RANK:
        raise ValueError(f"Rank {OWNER_RANK} is reserved for the Owner role.")
    if actor_rank is not None and value >= actor_rank:
        raise ValueError(
            f"Custom role rank ({value}) must be strictly less than your rank ({actor_rank})."
        )
    return value


# ---------------------------------------------------------------------------
# Department (free-text, sanitised)
# ---------------------------------------------------------------------------


def validate_department(value: str) -> str:
    """Validate a department name (free-text field, ADR-E4-004).

    Rules:
    - 1-100 characters after stripping whitespace
    - No leading/trailing whitespace preserved

    Returns:
        The validated department name stripped.

    Raises:
        ValueError: If the value is empty or exceeds length.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("Department name cannot be empty.")
    if len(stripped) > 100:
        raise ValueError(
            f"Department name must be 100 characters or less, got {len(stripped)}."
        )
    return stripped


# ---------------------------------------------------------------------------
# Date validators
# ---------------------------------------------------------------------------

_VALID_DATE_FORMATS = frozenset(
    {"YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD-MM-YYYY"}
)
_VALID_THEMES = frozenset({"light", "dark", "system"})


def validate_date_format_preference(value: str) -> str:
    """Validate a date display format preference.

    Returns:
        The validated format string.

    Raises:
        ValueError: If the format is not supported.
    """
    if value not in _VALID_DATE_FORMATS:
        raise ValueError(
            f"{value!r} is not a supported date format. "
            f"Supported: {', '.join(sorted(_VALID_DATE_FORMATS))}."
        )
    return value


def validate_theme_preference(value: str) -> str:
    """Validate a UI theme preference.

    Returns:
        The validated theme string.

    Raises:
        ValueError: If the theme is not supported.
    """
    if value not in _VALID_THEMES:
        raise ValueError(
            f"{value!r} is not a supported theme. "
            f"Supported: {', '.join(sorted(_VALID_THEMES))}."
        )
    return value

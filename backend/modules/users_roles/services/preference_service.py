"""PreferenceService — business logic for user preference management.

Handles:
- get_preferences: load (or initialise with defaults) the user's preference record
- update_preferences: validate and persist language, timezone, date_format, theme, etc.

Validation rules:
- language: BCP-47 tag, 2-10 characters
- timezone: must be a valid IANA timezone identifier (via ``zoneinfo``)
- date_format: one of the four allowed patterns
- theme: one of ['light', 'dark', 'system']

Spec reference: spec.md FR-016 through FR-019, tasks T059.
"""

from __future__ import annotations

import logging
import zoneinfo
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.users_roles.exceptions import UsersRolesException
from modules.users_roles.models.user_preference import UserPreference
from modules.users_roles.repositories.user_preference_repository import (
    UserPreferenceRepository,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_ALLOWED_DATE_FORMATS: frozenset[str] = frozenset(
    {"YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD-MM-YYYY"}
)

_ALLOWED_THEMES: frozenset[str] = frozenset({"light", "dark", "system"})


class InvalidPreferenceValueError(UsersRolesException):
    """A preference field contains an invalid value."""

    def __init__(self, field: str, value: str, reason: str) -> None:
        super().__init__(
            message=f"Invalid value for preference '{field}': {reason}",
            code="INVALID_PREFERENCE_VALUE",
            details={"field": field, "value": value, "reason": reason},
            http_status=400,
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PreferenceService:
    """Manages user preference records.

    Args:
        db:        SQLAlchemy ``Session``.
        pref_repo: ``UserPreferenceRepository`` for preference CRUD.
    """

    def __init__(
        self,
        db: Session,
        pref_repo: UserPreferenceRepository,
    ) -> None:
        self._db = db
        self._pref_repo = pref_repo

    # ── Public API ─────────────────────────────────────────────────────────

    def get_preferences(self, user_id: UUID) -> UserPreference:
        """Return the preference record for ``user_id``.

        Creates a record with sensible defaults if none exists yet.

        Args:
            user_id: Authenticated user's UUID.

        Returns:
            The ``UserPreference`` ORM instance.
        """
        pref = self._pref_repo.get_by_user_id(user_id)
        if pref is None:
            pref = self._pref_repo.create_with_defaults(user_id)
            logger.debug(
                "UserPreference initialised with defaults",
                extra={"user_id": str(user_id)},
            )
        return pref

    def update_preferences(
        self,
        user_id: UUID,
        *,
        language: str | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        number_format: str | None = None,
        theme: str | None = None,
    ) -> UserPreference:
        """Validate and persist updated preference values for ``user_id``.

        Only provided (non-``None``) values are validated and stored.
        Omitted values retain their current (or default) values.

        Args:
            user_id:       Authenticated user's UUID.
            language:      BCP-47 language tag (2–10 characters).
            timezone:      IANA timezone name (validated via ``zoneinfo``).
            date_format:   One of ``_ALLOWED_DATE_FORMATS``.
            number_format: Locale string for number formatting.
            theme:         One of ``_ALLOWED_THEMES``.

        Returns:
            The updated ``UserPreference`` instance.

        Raises:
            InvalidPreferenceValueError: If any supplied value fails validation.
        """
        updates: dict[str, Any] = {}

        if language is not None:
            self._validate_language(language)
            updates["language"] = language

        if timezone is not None:
            self._validate_timezone(timezone)
            updates["timezone"] = timezone

        if date_format is not None:
            self._validate_date_format(date_format)
            updates["date_format"] = date_format

        if number_format is not None:
            updates["number_format"] = number_format

        if theme is not None:
            self._validate_theme(theme)
            updates["theme"] = theme

        pref = self._pref_repo.create_or_update(user_id, updates)

        logger.info(
            "Preferences updated",
            extra={"user_id": str(user_id), "fields": list(updates.keys())},
        )
        return pref

    # ── Private validators ─────────────────────────────────────────────────

    @staticmethod
    def _validate_language(value: str) -> None:
        """Raise ``InvalidPreferenceValueError`` if language tag is out of range."""
        if not (2 <= len(value) <= 10):
            raise InvalidPreferenceValueError(
                field="language",
                value=value,
                reason="Language tag must be 2–10 characters (BCP-47).",
            )

    @staticmethod
    def _validate_timezone(value: str) -> None:
        """Raise ``InvalidPreferenceValueError`` if timezone is not a valid IANA name."""
        try:
            zoneinfo.ZoneInfo(value)
        except (zoneinfo.ZoneInfoNotFoundError, KeyError):
            raise InvalidPreferenceValueError(
                field="timezone",
                value=value,
                reason="Must be a valid IANA timezone identifier (e.g. 'UTC', 'Europe/London').",
            )

    @staticmethod
    def _validate_date_format(value: str) -> None:
        """Raise ``InvalidPreferenceValueError`` if date_format is not in the allowed set."""
        if value not in _ALLOWED_DATE_FORMATS:
            raise InvalidPreferenceValueError(
                field="date_format",
                value=value,
                reason=f"Must be one of: {sorted(_ALLOWED_DATE_FORMATS)}.",
            )

    @staticmethod
    def _validate_theme(value: str) -> None:
        """Raise ``InvalidPreferenceValueError`` if theme is not in the allowed set."""
        if value not in _ALLOWED_THEMES:
            raise InvalidPreferenceValueError(
                field="theme",
                value=value,
                reason=f"Must be one of: {sorted(_ALLOWED_THEMES)}.",
            )

"""Unit tests for PreferenceService — Phase 6 (US4).

Tests: get with defaults (creates if missing), update individual fields,
invalid timezone rejection, invalid language rejection, invalid date_format
rejection, invalid theme rejection.

Spec reference: tasks T066.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.users_roles.models.user_preference import UserPreference
from modules.users_roles.services.preference_service import (
    InvalidPreferenceValueError,
    PreferenceService,
)


def _make_pref(
    *,
    user_id: uuid.UUID | None = None,
    language: str = "en",
    timezone: str = "UTC",
    date_format: str = "YYYY-MM-DD",
    number_format: str = "en-US",
    theme: str = "system",
) -> MagicMock:
    pref = MagicMock(spec=UserPreference)
    pref.user_id = user_id or uuid.uuid4()
    pref.language = language
    pref.timezone = timezone
    pref.date_format = date_format
    pref.number_format = number_format
    pref.theme = theme
    pref.notification_preferences = {}
    return pref


def _make_service(
    *,
    existing_pref: MagicMock | None = None,
    created_pref: MagicMock | None = None,
    updated_pref: MagicMock | None = None,
) -> tuple[PreferenceService, MagicMock]:
    """Return (service, pref_repo_mock)."""
    db = MagicMock()
    pref_repo = MagicMock()

    pref_repo.get_by_user_id.return_value = existing_pref

    if created_pref is not None:
        pref_repo.create_with_defaults.return_value = created_pref

    if updated_pref is not None:
        pref_repo.create_or_update.return_value = updated_pref

    service = PreferenceService(db=db, pref_repo=pref_repo)
    return service, pref_repo


# ---------------------------------------------------------------------------
# TestGetPreferences
# ---------------------------------------------------------------------------


class TestGetPreferences:
    def test_returns_existing_pref(self):
        pref = _make_pref()
        service, pref_repo = _make_service(existing_pref=pref)

        result = service.get_preferences(pref.user_id)

        assert result is pref
        pref_repo.create_with_defaults.assert_not_called()

    def test_creates_defaults_when_no_pref_exists(self):
        user_id = uuid.uuid4()
        new_pref = _make_pref(user_id=user_id)
        service, pref_repo = _make_service(existing_pref=None, created_pref=new_pref)

        result = service.get_preferences(user_id)

        pref_repo.create_with_defaults.assert_called_once_with(user_id)
        assert result is new_pref


# ---------------------------------------------------------------------------
# TestUpdatePreferences
# ---------------------------------------------------------------------------


class TestUpdatePreferences:
    def test_update_language(self):
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id, language="fr")
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        result = service.update_preferences(user_id, language="fr")

        pref_repo.create_or_update.assert_called_once_with(user_id, {"language": "fr"})
        assert result is updated

    def test_update_timezone(self):
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id, timezone="Europe/London")
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        result = service.update_preferences(user_id, timezone="Europe/London")

        call_updates = pref_repo.create_or_update.call_args[0][1]
        assert call_updates["timezone"] == "Europe/London"

    def test_update_date_format(self):
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id, date_format="DD/MM/YYYY")
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        result = service.update_preferences(user_id, date_format="DD/MM/YYYY")

        call_updates = pref_repo.create_or_update.call_args[0][1]
        assert call_updates["date_format"] == "DD/MM/YYYY"

    def test_update_theme(self):
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id, theme="dark")
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        result = service.update_preferences(user_id, theme="dark")

        call_updates = pref_repo.create_or_update.call_args[0][1]
        assert call_updates["theme"] == "dark"

    def test_none_fields_are_omitted(self):
        """Only non-None fields should appear in the updates dict."""
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id)
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        service.update_preferences(user_id, language="de")

        call_updates = pref_repo.create_or_update.call_args[0][1]
        assert "timezone" not in call_updates
        assert "theme" not in call_updates


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_invalid_timezone_raises_error(self):
        user_id = uuid.uuid4()
        service, _ = _make_service()

        with pytest.raises(InvalidPreferenceValueError) as exc_info:
            service.update_preferences(user_id, timezone="Not/A/Timezone")

        assert "timezone" in exc_info.value.details["field"]

    def test_invalid_language_too_short_raises_error(self):
        user_id = uuid.uuid4()
        service, _ = _make_service()

        with pytest.raises(InvalidPreferenceValueError) as exc_info:
            service.update_preferences(user_id, language="x")  # too short (< 2 chars)

        assert "language" in exc_info.value.details["field"]

    def test_invalid_language_too_long_raises_error(self):
        user_id = uuid.uuid4()
        service, _ = _make_service()

        with pytest.raises(InvalidPreferenceValueError) as exc_info:
            service.update_preferences(user_id, language="toolonglanguagetag")

        assert "language" in exc_info.value.details["field"]

    def test_invalid_date_format_raises_error(self):
        user_id = uuid.uuid4()
        service, _ = _make_service()

        with pytest.raises(InvalidPreferenceValueError) as exc_info:
            service.update_preferences(user_id, date_format="YY/MM/DD")

        assert "date_format" in exc_info.value.details["field"]

    def test_invalid_theme_raises_error(self):
        user_id = uuid.uuid4()
        service, _ = _make_service()

        with pytest.raises(InvalidPreferenceValueError) as exc_info:
            service.update_preferences(user_id, theme="rainbow")

        assert "theme" in exc_info.value.details["field"]

    def test_valid_utc_timezone_accepted(self):
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id)
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        # Should not raise
        service.update_preferences(user_id, timezone="UTC")

    def test_valid_iana_timezone_accepted(self):
        user_id = uuid.uuid4()
        updated = _make_pref(user_id=user_id)
        service, pref_repo = _make_service(
            existing_pref=_make_pref(user_id=user_id), updated_pref=updated
        )

        # Should not raise
        service.update_preferences(user_id, timezone="America/New_York")

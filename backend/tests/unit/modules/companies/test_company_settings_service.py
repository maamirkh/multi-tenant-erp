"""Unit tests for CompanySettingsService — settings validation and merge.

All tests are pure unit tests (no database, no mocks needed).
"""

from __future__ import annotations

import pytest

from modules.companies.services.company_settings_service import (
    ALLOWED_SETTINGS,
    CompanySettingsService,
)


@pytest.fixture()
def service() -> CompanySettingsService:
    return CompanySettingsService()


# ---------------------------------------------------------------------------
# validate_settings
# ---------------------------------------------------------------------------


class TestValidateSettings:
    def test_known_key_valid_value_succeeds(
        self, service: CompanySettingsService
    ) -> None:
        result = service.validate_settings({"invoice_prefix": "INV-"})
        assert result == {"invoice_prefix": "INV-"}

    def test_multiple_valid_keys_succeeds(
        self, service: CompanySettingsService
    ) -> None:
        updates = {
            "invoice_prefix": "INV-",
            "invoice_next_number": 1001,
            "multi_currency_enabled": True,
        }
        result = service.validate_settings(updates)
        assert result == updates

    def test_unknown_key_raises_value_error(
        self, service: CompanySettingsService
    ) -> None:
        with pytest.raises(ValueError, match="Unknown setting key"):
            service.validate_settings({"nonexistent_key": "value"})

    def test_wrong_type_raises_value_error(
        self, service: CompanySettingsService
    ) -> None:
        with pytest.raises(ValueError, match="expects type"):
            service.validate_settings({"invoice_next_number": "not-an-int"})

    def test_bool_for_str_field_raises_value_error(
        self, service: CompanySettingsService
    ) -> None:
        with pytest.raises(ValueError, match="expects type"):
            service.validate_settings({"invoice_prefix": True})

    def test_invalid_allowed_value_raises_value_error(
        self, service: CompanySettingsService
    ) -> None:
        with pytest.raises(ValueError, match="not in allowed values"):
            service.validate_settings({"date_display_format": "MM.DD.YYYY"})

    def test_valid_allowed_value_succeeds(
        self, service: CompanySettingsService
    ) -> None:
        result = service.validate_settings({"date_display_format": "DD/MM/YYYY"})
        assert result["date_display_format"] == "DD/MM/YYYY"

    def test_empty_updates_succeeds(self, service: CompanySettingsService) -> None:
        result = service.validate_settings({})
        assert result == {}

    def test_error_message_includes_key_name(
        self, service: CompanySettingsService
    ) -> None:
        with pytest.raises(ValueError, match="bad_key"):
            service.validate_settings({"bad_key": 1})


# ---------------------------------------------------------------------------
# merge_settings
# ---------------------------------------------------------------------------


class TestMergeSettings:
    def test_merge_overwrites_existing_key(
        self, service: CompanySettingsService
    ) -> None:
        existing = {"invoice_prefix": "OLD-", "po_prefix": "PO-"}
        updates = {"invoice_prefix": "NEW-"}
        result = service.merge_settings(existing, updates)
        assert result["invoice_prefix"] == "NEW-"

    def test_merge_keeps_existing_keys_not_in_update(
        self, service: CompanySettingsService
    ) -> None:
        existing = {"invoice_prefix": "INV-", "po_prefix": "PO-"}
        updates = {"invoice_prefix": "NEW-"}
        result = service.merge_settings(existing, updates)
        assert result["po_prefix"] == "PO-"

    def test_merge_adds_new_keys_from_update(
        self, service: CompanySettingsService
    ) -> None:
        existing = {"invoice_prefix": "INV-"}
        updates = {"po_prefix": "PO-"}
        result = service.merge_settings(existing, updates)
        assert result["invoice_prefix"] == "INV-"
        assert result["po_prefix"] == "PO-"

    def test_merge_does_not_mutate_existing(
        self, service: CompanySettingsService
    ) -> None:
        existing = {"invoice_prefix": "INV-"}
        updates = {"invoice_prefix": "NEW-"}
        service.merge_settings(existing, updates)
        assert existing["invoice_prefix"] == "INV-"

    def test_merge_empty_update_returns_existing_unchanged(
        self, service: CompanySettingsService
    ) -> None:
        existing = {"invoice_prefix": "INV-"}
        result = service.merge_settings(existing, {})
        assert result == existing

    def test_merge_into_empty_existing(self, service: CompanySettingsService) -> None:
        result = service.merge_settings({}, {"invoice_prefix": "INV-"})
        assert result == {"invoice_prefix": "INV-"}


# ---------------------------------------------------------------------------
# ALLOWED_SETTINGS registry
# ---------------------------------------------------------------------------


class TestAllowedSettingsRegistry:
    def test_registry_is_non_empty(self) -> None:
        assert len(ALLOWED_SETTINGS) > 0

    def test_all_entries_have_correct_structure(self) -> None:
        for key, value in ALLOWED_SETTINGS.items():
            assert isinstance(key, str), f"Key {key!r} is not a str"
            assert isinstance(value, tuple) and len(value) == 2, (
                f"Entry for {key!r} must be a 2-tuple"
            )
            expected_type, allowed_values = value
            assert isinstance(expected_type, type), (
                f"First element for {key!r} must be a type"
            )
            assert allowed_values is None or isinstance(allowed_values, list), (
                f"Second element for {key!r} must be a list or None"
            )

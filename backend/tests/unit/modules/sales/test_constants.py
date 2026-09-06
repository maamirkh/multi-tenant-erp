"""Unit tests for sales module constants.

Tests:
  - Permission codes are unique
  - Feature flag keys are unique
  - All permission codes follow sales.* naming convention
  - All feature flag keys follow sales.* naming convention
  - Lookup dicts contain all entries
  - Default enabled flag set is correct

Task: T027
"""

from __future__ import annotations

from modules.sales.constants import (
    DOCUMENT_TYPES,
    MODULE_NAME,
    MODULE_VERSION,
    SALES_DEFAULT_ENABLED_FLAGS,
    SALES_FEATURE_FLAGS,
    SALES_FLAG_BY_KEY,
    SALES_PERMISSION_BY_CODE,
    SALES_PERMISSIONS,
)


class TestSalesPermissions:
    """Test permission constant integrity."""

    def test_permission_codes_are_unique(self) -> None:
        codes = [p.code for p in SALES_PERMISSIONS]
        assert len(codes) == len(set(codes)), (
            f"Duplicate codes: {[c for c in codes if codes.count(c) > 1]}"
        )

    def test_all_permissions_follow_naming_convention(self) -> None:
        for p in SALES_PERMISSIONS:
            assert p.code.startswith("sales."), (
                f"Permission '{p.code}' does not start with 'sales.'"
            )

    def test_all_permissions_have_module_sales(self) -> None:
        for p in SALES_PERMISSIONS:
            assert p.module == "sales", f"Permission '{p.code}' has module='{p.module}'"

    def test_lookup_dict_contains_all_permissions(self) -> None:
        assert len(SALES_PERMISSION_BY_CODE) == len(SALES_PERMISSIONS)
        for p in SALES_PERMISSIONS:
            assert p.code in SALES_PERMISSION_BY_CODE

    def test_all_permissions_have_required_fields(self) -> None:
        for p in SALES_PERMISSIONS:
            assert p.code, "Empty code"
            assert p.label, "Empty label"
            assert p.action, "Empty action"
            assert p.description, "Empty description"


class TestSalesFeatureFlags:
    """Test feature flag constant integrity."""

    def test_flag_keys_are_unique(self) -> None:
        keys = [f.key for f in SALES_FEATURE_FLAGS]
        assert len(keys) == len(set(keys)), (
            f"Duplicate keys: {[k for k in keys if keys.count(k) > 1]}"
        )

    def test_all_flags_follow_naming_convention(self) -> None:
        for f in SALES_FEATURE_FLAGS:
            assert f.key.startswith("sales."), (
                f"Flag '{f.key}' does not start with 'sales.'"
            )

    def test_lookup_dict_contains_all_flags(self) -> None:
        assert len(SALES_FLAG_BY_KEY) == len(SALES_FEATURE_FLAGS)
        for f in SALES_FEATURE_FLAGS:
            assert f.key in SALES_FLAG_BY_KEY

    def test_14_feature_flags_defined(self) -> None:
        assert len(SALES_FEATURE_FLAGS) == 14

    def test_default_enabled_flags_subset(self) -> None:
        all_keys = {f.key for f in SALES_FEATURE_FLAGS}
        assert SALES_DEFAULT_ENABLED_FLAGS.issubset(all_keys)

    def test_default_enabled_flags_match(self) -> None:
        expected = {f.key for f in SALES_FEATURE_FLAGS if f.default_enabled}
        assert SALES_DEFAULT_ENABLED_FLAGS == expected

    def test_all_flags_have_required_fields(self) -> None:
        for f in SALES_FEATURE_FLAGS:
            assert f.key, "Empty key"
            assert f.label, "Empty label"
            assert f.description, "Empty description"


class TestDocumentTypes:
    """Test document type constants."""

    def test_five_document_types(self) -> None:
        assert len(DOCUMENT_TYPES) == 5
        assert set(DOCUMENT_TYPES) == {"SQ", "SO", "DN", "SI", "SR"}


class TestModuleConstants:
    """Test module-level constants."""

    def test_module_name(self) -> None:
        assert MODULE_NAME == "sales"

    def test_module_version(self) -> None:
        assert MODULE_VERSION == "1.0.0"

"""Unit tests for Inventory module constants (Phase 0 — T021).

Tests cover:
  - All permissions have unique codes
  - All permissions follow the inventory.<domain>.<action> pattern
  - All feature flags have unique keys
  - All feature flags follow the inventory.<capability> pattern
  - INVENTORY_PERMISSION_BY_CODE and INVENTORY_FLAG_BY_KEY lookups are consistent
  - INVENTORY_DEFAULT_ENABLED_FLAGS is a subset of all flag keys
"""

from __future__ import annotations

import re

from modules.inventory.constants import (
    INVENTORY_DEFAULT_ENABLED_FLAGS,
    INVENTORY_FEATURE_FLAGS,
    INVENTORY_FLAG_BY_KEY,
    INVENTORY_PERMISSION_BY_CODE,
    INVENTORY_PERMISSIONS,
    MODULE_NAME,
    MODULE_VERSION,
    SPEC_VERSION,
)

_PERMISSION_CODE_PATTERN = re.compile(r"^inventory\..+\..+$")
_FLAG_KEY_PATTERN = re.compile(r"^inventory\..+$")


class TestPermissions:
    def test_all_permission_codes_are_unique(self) -> None:
        codes = [p.code for p in INVENTORY_PERMISSIONS]
        assert len(codes) == len(set(codes)), "Duplicate permission codes detected"

    def test_permission_codes_follow_naming_convention(self) -> None:
        for perm in INVENTORY_PERMISSIONS:
            assert _PERMISSION_CODE_PATTERN.match(perm.code), (
                f"Permission code '{perm.code}' does not match 'inventory.<domain>.<action>'"
            )

    def test_permission_by_code_lookup_consistent(self) -> None:
        assert len(INVENTORY_PERMISSION_BY_CODE) == len(INVENTORY_PERMISSIONS)
        for perm in INVENTORY_PERMISSIONS:
            assert INVENTORY_PERMISSION_BY_CODE[perm.code] is perm

    def test_all_permissions_have_non_empty_fields(self) -> None:
        for perm in INVENTORY_PERMISSIONS:
            assert perm.code.strip(), f"Empty code for permission: {perm}"
            assert perm.label.strip(), f"Empty label for: {perm.code}"
            assert perm.module.strip(), f"Empty module for: {perm.code}"
            assert perm.action.strip(), f"Empty action for: {perm.code}"
            assert perm.description.strip(), f"Empty description for: {perm.code}"

    def test_permission_count_meets_minimum(self) -> None:
        # At least the permissions defined in spec §26 must be present
        assert len(INVENTORY_PERMISSIONS) >= 10


class TestFeatureFlags:
    def test_all_flag_keys_are_unique(self) -> None:
        keys = [f.key for f in INVENTORY_FEATURE_FLAGS]
        assert len(keys) == len(set(keys)), "Duplicate feature flag keys detected"

    def test_flag_keys_follow_naming_convention(self) -> None:
        for flag in INVENTORY_FEATURE_FLAGS:
            assert _FLAG_KEY_PATTERN.match(flag.key), (
                f"Flag key '{flag.key}' does not match 'inventory.<capability>'"
            )

    def test_flag_by_key_lookup_consistent(self) -> None:
        assert len(INVENTORY_FLAG_BY_KEY) == len(INVENTORY_FEATURE_FLAGS)
        for flag in INVENTORY_FEATURE_FLAGS:
            assert INVENTORY_FLAG_BY_KEY[flag.key] is flag

    def test_default_enabled_flags_are_subset_of_all_flags(self) -> None:
        all_keys = {f.key for f in INVENTORY_FEATURE_FLAGS}
        assert INVENTORY_DEFAULT_ENABLED_FLAGS <= all_keys

    def test_default_enabled_flags_matches_definition(self) -> None:
        expected = frozenset(
            f.key for f in INVENTORY_FEATURE_FLAGS if f.default_enabled
        )
        assert INVENTORY_DEFAULT_ENABLED_FLAGS == expected

    def test_all_flags_have_non_empty_fields(self) -> None:
        for flag in INVENTORY_FEATURE_FLAGS:
            assert flag.key.strip(), f"Empty key for flag: {flag}"
            assert flag.label.strip(), f"Empty label for: {flag.key}"
            assert flag.description.strip(), f"Empty description for: {flag.key}"

    def test_flag_count_meets_minimum(self) -> None:
        # At least core flags from spec §27 must be present
        assert len(INVENTORY_FEATURE_FLAGS) >= 10


class TestModuleMetadata:
    def test_module_name(self) -> None:
        assert MODULE_NAME == "inventory"

    def test_module_version_format(self) -> None:
        parts = MODULE_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_spec_version_format(self) -> None:
        parts = SPEC_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

"""Unit tests for purchase module constants.

Tests:
  - Permission codes are unique and follow naming convention
  - Feature flag keys are unique and follow naming convention
  - Required document types are present
  - Module constants are correct

Spec ref: specs/006-purchase-management/spec.md §28, §29
"""

from __future__ import annotations

from modules.purchase.constants import (
    DOCUMENT_TYPES,
    MODULE_NAME,
    MODULE_VERSION,
    PURCHASE_DEFAULT_ENABLED_FLAGS,
    PURCHASE_FEATURE_FLAGS,
    PURCHASE_FLAG_BY_KEY,
    PURCHASE_PERMISSION_BY_CODE,
    PURCHASE_PERMISSIONS,
    SUPPLIER_CATEGORY_MAX_DEPTH,
)


class TestPermissionConstants:
    def test_permission_codes_are_unique(self) -> None:
        codes = [p.code for p in PURCHASE_PERMISSIONS]
        assert len(codes) == len(set(codes)), "Duplicate permission codes found"

    def test_permission_codes_follow_naming_convention(self) -> None:
        for perm in PURCHASE_PERMISSIONS:
            assert perm.code.startswith("purchase."), (
                f"Permission code '{perm.code}' must start with 'purchase.'"
            )
            parts = perm.code.split(".")
            assert len(parts) >= 3, (
                f"Permission code '{perm.code}' must follow 'purchase.<domain>.<action>'"
            )

    def test_permission_by_code_dict_matches_tuple(self) -> None:
        assert len(PURCHASE_PERMISSION_BY_CODE) == len(PURCHASE_PERMISSIONS)
        for perm in PURCHASE_PERMISSIONS:
            assert perm.code in PURCHASE_PERMISSION_BY_CODE
            assert PURCHASE_PERMISSION_BY_CODE[perm.code] is perm

    def test_required_permissions_exist(self) -> None:
        required = [
            "purchase.suppliers.create",
            "purchase.suppliers.read",
            "purchase.orders.create",
            "purchase.orders.approve",
            "purchase.receipts.confirm",
            "purchase.settings.update",
        ]
        for code in required:
            assert code in PURCHASE_PERMISSION_BY_CODE, (
                f"Required permission '{code}' missing"
            )

    def test_permission_module_field_is_purchase(self) -> None:
        for perm in PURCHASE_PERMISSIONS:
            assert perm.module == "purchase"


class TestFeatureFlagConstants:
    def test_flag_keys_are_unique(self) -> None:
        keys = [f.key for f in PURCHASE_FEATURE_FLAGS]
        assert len(keys) == len(set(keys)), "Duplicate feature flag keys found"

    def test_flag_keys_follow_naming_convention(self) -> None:
        for flag in PURCHASE_FEATURE_FLAGS:
            assert flag.key.startswith("purchase."), (
                f"Feature flag key '{flag.key}' must start with 'purchase.'"
            )

    def test_exactly_12_feature_flags(self) -> None:
        assert len(PURCHASE_FEATURE_FLAGS) == 14, (
            f"Expected 14 purchase feature flags, got {len(PURCHASE_FEATURE_FLAGS)}"
        )

    def test_flag_by_key_dict_matches_tuple(self) -> None:
        assert len(PURCHASE_FLAG_BY_KEY) == len(PURCHASE_FEATURE_FLAGS)
        for flag in PURCHASE_FEATURE_FLAGS:
            assert flag.key in PURCHASE_FLAG_BY_KEY

    def test_approval_flags_default_enabled(self) -> None:
        approval_flags = [
            "purchase.approval_required_pr",
            "purchase.approval_required_po",
            "purchase.approval_required_rma",
        ]
        for key in approval_flags:
            assert key in PURCHASE_FLAG_BY_KEY, f"Approval flag '{key}' missing"
            assert PURCHASE_FLAG_BY_KEY[key].default_enabled, (
                f"Approval flag '{key}' should default to enabled (safe default)"
            )

    def test_channel_and_ai_flags_default_disabled(self) -> None:
        opt_in_flags = [
            "purchase.supplier_portal",
            "purchase.ai_procurement_assistant",
            "purchase.direct_po_allowed",
        ]
        for key in opt_in_flags:
            assert key in PURCHASE_FLAG_BY_KEY, f"Flag '{key}' missing"
            assert not PURCHASE_FLAG_BY_KEY[key].default_enabled, (
                f"Flag '{key}' should default to disabled (opt-in)"
            )

    def test_default_enabled_flags_set_is_consistent(self) -> None:
        expected = frozenset(f.key for f in PURCHASE_FEATURE_FLAGS if f.default_enabled)
        assert PURCHASE_DEFAULT_ENABLED_FLAGS == expected


class TestModuleConstants:
    def test_module_name(self) -> None:
        assert MODULE_NAME == "purchase"

    def test_module_version_format(self) -> None:
        parts = MODULE_VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_document_types(self) -> None:
        assert set(DOCUMENT_TYPES) == {"PR", "PO", "GR", "RMA"}

    def test_supplier_category_max_depth(self) -> None:
        assert SUPPLIER_CATEGORY_MAX_DEPTH == 5
        assert isinstance(SUPPLIER_CATEGORY_MAX_DEPTH, int)

"""Inventory module constants.

Permission codes follow the pattern ``inventory.<sub_domain>.<action>``
as defined in spec.md §26 Permission Matrix.

Feature flag keys follow the pattern ``inventory.<capability>``
as defined in spec.md §27 Feature Matrix.

All definitions are frozen datastructures to prevent accidental mutation.

Spec ref: specs/005-inventory-management/spec.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Permission Definitions (spec §26 — Permission Matrix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InventoryPermissionDefinition:
    """Immutable definition of an inventory module permission."""

    code: str
    label: str
    module: str
    action: str
    description: str


INVENTORY_PERMISSIONS: Final[tuple[InventoryPermissionDefinition, ...]] = (
    # --- Product Master permissions ---
    InventoryPermissionDefinition(
        "inventory.products.create",
        "Create Products",
        "inventory",
        "products.create",
        "Create new products in the product catalogue",
    ),
    InventoryPermissionDefinition(
        "inventory.products.read",
        "View Products",
        "inventory",
        "products.read",
        "View product details and catalogue",
    ),
    InventoryPermissionDefinition(
        "inventory.products.update",
        "Edit Products",
        "inventory",
        "products.update",
        "Update product information and attributes",
    ),
    InventoryPermissionDefinition(
        "inventory.products.delete",
        "Archive Products",
        "inventory",
        "products.delete",
        "Archive and soft-delete products",
    ),
    InventoryPermissionDefinition(
        "inventory.products.import",
        "Import Products",
        "inventory",
        "products.import",
        "Bulk import products via CSV/Excel",
    ),
    InventoryPermissionDefinition(
        "inventory.products.export",
        "Export Products",
        "inventory",
        "products.export",
        "Bulk export products to CSV/Excel",
    ),
    # --- Warehouse Management permissions ---
    InventoryPermissionDefinition(
        "inventory.warehouses.create",
        "Create Warehouses",
        "inventory",
        "warehouses.create",
        "Create new warehouse locations",
    ),
    InventoryPermissionDefinition(
        "inventory.warehouses.read",
        "View Warehouses",
        "inventory",
        "warehouses.read",
        "View warehouse details and locations",
    ),
    InventoryPermissionDefinition(
        "inventory.warehouses.update",
        "Edit Warehouses",
        "inventory",
        "warehouses.update",
        "Update warehouse configuration",
    ),
    InventoryPermissionDefinition(
        "inventory.warehouses.delete",
        "Archive Warehouses",
        "inventory",
        "warehouses.delete",
        "Archive warehouse locations",
    ),
    # --- Stock Operations permissions ---
    InventoryPermissionDefinition(
        "inventory.stock.read",
        "View Stock",
        "inventory",
        "stock.read",
        "View stock levels and movements",
    ),
    InventoryPermissionDefinition(
        "inventory.stock.adjust",
        "Adjust Stock",
        "inventory",
        "stock.adjust",
        "Create stock adjustment entries",
    ),
    InventoryPermissionDefinition(
        "inventory.stock.transfer",
        "Transfer Stock",
        "inventory",
        "stock.transfer",
        "Initiate and complete warehouse transfers",
    ),
    InventoryPermissionDefinition(
        "inventory.stock.approve_adjustment",
        "Approve Adjustments",
        "inventory",
        "stock.approve_adjustment",
        "Approve or reject pending stock adjustments",
    ),
    # --- Inventory Intelligence permissions ---
    InventoryPermissionDefinition(
        "inventory.alerts.read",
        "View Alerts",
        "inventory",
        "alerts.read",
        "View low stock and reorder alerts",
    ),
    InventoryPermissionDefinition(
        "inventory.alerts.manage",
        "Manage Alerts",
        "inventory",
        "alerts.manage",
        "Configure reorder rules and alert thresholds",
    ),
    # --- Reporting permissions ---
    InventoryPermissionDefinition(
        "inventory.reports.read",
        "View Reports",
        "inventory",
        "reports.read",
        "View inventory reports and analytics",
    ),
    InventoryPermissionDefinition(
        "inventory.reports.export",
        "Export Reports",
        "inventory",
        "reports.export",
        "Export inventory reports to CSV/Excel",
    ),
    # --- Settings permissions ---
    InventoryPermissionDefinition(
        "inventory.settings.read",
        "View Inventory Settings",
        "inventory",
        "settings.read",
        "View inventory module configuration",
    ),
    InventoryPermissionDefinition(
        "inventory.settings.update",
        "Edit Inventory Settings",
        "inventory",
        "settings.update",
        "Update inventory module configuration and feature flags",
    ),
)

INVENTORY_PERMISSION_BY_CODE: Final[dict[str, InventoryPermissionDefinition]] = {
    p.code: p for p in INVENTORY_PERMISSIONS
}


# ---------------------------------------------------------------------------
# Feature Flag Keys (spec §27 — Feature Matrix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureFlagDefinition:
    """Immutable definition of a feature flag."""

    key: str
    label: str
    description: str
    default_enabled: bool


INVENTORY_FEATURE_FLAGS: Final[tuple[FeatureFlagDefinition, ...]] = (
    # --- Ready & Enabled (Phase 0 default) ---
    FeatureFlagDefinition(
        key="inventory.product_master",
        label="Product Master",
        description="Core product catalogue management",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.warehouse_management",
        label="Warehouse Management",
        description="Multi-warehouse location management",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.stock_ledger",
        label="Stock Ledger",
        description="Immutable stock movement recording",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.stock_adjustments",
        label="Stock Adjustments",
        description="Manual stock adjustment with approval workflow",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.stock_transfers",
        label="Stock Transfers",
        description="Inter-warehouse stock transfer operations",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.low_stock_alerts",
        label="Low Stock Alerts",
        description="Reorder rules and low stock detection",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.bulk_import",
        label="Bulk Import",
        description="CSV/Excel bulk product import",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="inventory.bulk_export",
        label="Bulk Export",
        description="CSV/Excel bulk product export",
        default_enabled=True,
    ),
    # --- Ready but Disabled (require explicit activation) ---
    FeatureFlagDefinition(
        key="inventory.adjustment_approval",
        label="Adjustment Approval Workflow",
        description="Require managerial approval for stock adjustments above threshold",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.negative_stock",
        label="Allow Negative Stock",
        description="Permit stock positions to go below zero (e.g. for back-orders)",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.product_variants",
        label="Product Variants",
        description="Support for multi-attribute product variants (size, colour, etc.)",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.fifo_valuation",
        label="FIFO Valuation",
        description="First-In-First-Out cost valuation method (default: Weighted Average Cost)",
        default_enabled=False,
    ),
    # --- Future (architecture reserved, not yet implemented) ---
    FeatureFlagDefinition(
        key="inventory.physical_count",
        label="Physical Count",
        description="Full physical inventory count workflow",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.cycle_count",
        label="Cycle Count",
        description="Partial rolling cycle count workflow",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.bin_management",
        label="Bin Management",
        description="Sub-location bin/rack management within warehouses",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.serial_tracking",
        label="Serial Number Tracking",
        description="Per-unit serial number traceability",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.batch_tracking",
        label="Batch/Lot Tracking",
        description="Batch and lot number traceability with expiry dates",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.overstock_alerts",
        label="Overstock Alerts",
        description="Raise an alert when stock exceeds maximum_stock threshold",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="inventory.demand_forecasting",
        label="AI Demand Forecasting",
        description="AI-powered demand prediction and auto-reorder",
        default_enabled=False,
    ),
)

INVENTORY_FLAG_BY_KEY: Final[dict[str, FeatureFlagDefinition]] = {
    f.key: f for f in INVENTORY_FEATURE_FLAGS
}

# Set of keys that default to enabled — used for seeding
INVENTORY_DEFAULT_ENABLED_FLAGS: Final[frozenset[str]] = frozenset(
    f.key for f in INVENTORY_FEATURE_FLAGS if f.default_enabled
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MODULE_NAME: Final[str] = "inventory"
MODULE_VERSION: Final[str] = "1.0.0"
SPEC_VERSION: Final[str] = "1.1.0"

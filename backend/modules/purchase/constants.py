"""Purchase module constants.

Permission codes follow the pattern ``purchase.<sub_domain>.<action>``
as defined in spec.md §28 Permission Matrix.

Feature flag keys follow the pattern ``purchase.<capability>``
as defined in spec.md §29 Feature Matrix.

All definitions are frozen datastructures to prevent accidental mutation.

Spec ref: specs/006-purchase-management/spec.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Permission Definitions (spec §28 — Permission Matrix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PurchasePermissionDefinition:
    """Immutable definition of a purchase module permission."""

    code: str
    label: str
    module: str
    action: str
    description: str


PURCHASE_PERMISSIONS: Final[tuple[PurchasePermissionDefinition, ...]] = (
    # --- Supplier Master permissions ---
    PurchasePermissionDefinition(
        "purchase.suppliers.create",
        "Create Suppliers",
        "purchase",
        "suppliers.create",
        "Create new suppliers in the supplier master",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.read",
        "View Suppliers",
        "purchase",
        "suppliers.read",
        "View supplier details and master catalogue",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.update",
        "Edit Suppliers",
        "purchase",
        "suppliers.update",
        "Update supplier information and enrichment data",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.delete",
        "Archive Suppliers",
        "purchase",
        "suppliers.delete",
        "Archive and soft-delete suppliers",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.activate",
        "Activate Suppliers",
        "purchase",
        "suppliers.activate",
        "Transition supplier status to ACTIVE",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.block",
        "Block Suppliers",
        "purchase",
        "suppliers.block",
        "Block supplier from receiving new purchase documents",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.import",
        "Import Suppliers",
        "purchase",
        "suppliers.import",
        "Bulk import suppliers via CSV/Excel",
    ),
    PurchasePermissionDefinition(
        "purchase.suppliers.export",
        "Export Suppliers",
        "purchase",
        "suppliers.export",
        "Bulk export suppliers to CSV/Excel",
    ),
    # --- Purchase Request permissions ---
    PurchasePermissionDefinition(
        "purchase.requests.create",
        "Create Purchase Requests",
        "purchase",
        "requests.create",
        "Create new purchase requests",
    ),
    PurchasePermissionDefinition(
        "purchase.requests.read",
        "View Purchase Requests",
        "purchase",
        "requests.read",
        "View purchase request details and list",
    ),
    PurchasePermissionDefinition(
        "purchase.requests.update",
        "Edit Purchase Requests",
        "purchase",
        "requests.update",
        "Update draft purchase requests",
    ),
    PurchasePermissionDefinition(
        "purchase.requests.cancel",
        "Cancel Purchase Requests",
        "purchase",
        "requests.cancel",
        "Cancel pending or draft purchase requests",
    ),
    PurchasePermissionDefinition(
        "purchase.requests.approve",
        "Approve Purchase Requests",
        "purchase",
        "requests.approve",
        "Approve or reject purchase requests pending approval",
    ),
    # --- Purchase Order permissions ---
    PurchasePermissionDefinition(
        "purchase.orders.create",
        "Create Purchase Orders",
        "purchase",
        "orders.create",
        "Create new purchase orders",
    ),
    PurchasePermissionDefinition(
        "purchase.orders.read",
        "View Purchase Orders",
        "purchase",
        "orders.read",
        "View purchase order details and list",
    ),
    PurchasePermissionDefinition(
        "purchase.orders.update",
        "Edit Purchase Orders",
        "purchase",
        "orders.update",
        "Update draft purchase orders",
    ),
    PurchasePermissionDefinition(
        "purchase.orders.approve",
        "Approve Purchase Orders",
        "purchase",
        "orders.approve",
        "Approve or reject purchase orders pending approval",
    ),
    PurchasePermissionDefinition(
        "purchase.orders.cancel",
        "Cancel Purchase Orders",
        "purchase",
        "orders.cancel",
        "Cancel approved or draft purchase orders",
    ),
    PurchasePermissionDefinition(
        "purchase.orders.amend",
        "Amend Purchase Orders",
        "purchase",
        "orders.amend",
        "Initiate amendment workflow for approved purchase orders",
    ),
    PurchasePermissionDefinition(
        "purchase.orders.export",
        "Export Purchase Orders",
        "purchase",
        "orders.export",
        "Export purchase orders to CSV/Excel/PDF",
    ),
    # --- Goods Receipt permissions ---
    PurchasePermissionDefinition(
        "purchase.receipts.create",
        "Create Goods Receipts",
        "purchase",
        "receipts.create",
        "Create goods receipt against an approved purchase order",
    ),
    PurchasePermissionDefinition(
        "purchase.receipts.read",
        "View Goods Receipts",
        "purchase",
        "receipts.read",
        "View goods receipt details and list",
    ),
    PurchasePermissionDefinition(
        "purchase.receipts.confirm",
        "Confirm Goods Receipts",
        "purchase",
        "receipts.confirm",
        "Confirm goods receipt and trigger stock update",
    ),
    # --- Vendor Return permissions ---
    PurchasePermissionDefinition(
        "purchase.returns.create",
        "Create Vendor Returns",
        "purchase",
        "returns.create",
        "Initiate vendor return (RMA) against a goods receipt",
    ),
    PurchasePermissionDefinition(
        "purchase.returns.read",
        "View Vendor Returns",
        "purchase",
        "returns.read",
        "View vendor return details and list",
    ),
    PurchasePermissionDefinition(
        "purchase.returns.approve",
        "Approve Vendor Returns",
        "purchase",
        "returns.approve",
        "Approve or reject vendor return requests",
    ),
    PurchasePermissionDefinition(
        "purchase.returns.dispatch",
        "Dispatch Vendor Returns",
        "purchase",
        "returns.dispatch",
        "Mark vendor return as dispatched to supplier",
    ),
    # --- Purchase Costing permissions ---
    PurchasePermissionDefinition(
        "purchase.costing.read",
        "View Purchase Costs",
        "purchase",
        "costing.read",
        "View purchase cost entries and PPV data",
    ),
    PurchasePermissionDefinition(
        "purchase.costing.manage",
        "Manage Additional Charges",
        "purchase",
        "costing.manage",
        "Add freight, handling and other additional charges to POs",
    ),
    # --- Approval Matrix permissions ---
    PurchasePermissionDefinition(
        "purchase.approval_matrix.read",
        "View Approval Matrix",
        "purchase",
        "approval_matrix.read",
        "View purchase approval matrix and rules",
    ),
    PurchasePermissionDefinition(
        "purchase.approval_matrix.manage",
        "Manage Approval Matrix",
        "purchase",
        "approval_matrix.manage",
        "Configure approval levels, rules, and delegates",
    ),
    # --- Reporting permissions ---
    PurchasePermissionDefinition(
        "purchase.reports.read",
        "View Purchase Reports",
        "purchase",
        "reports.read",
        "View purchase reports, KPIs, and analytics",
    ),
    PurchasePermissionDefinition(
        "purchase.reports.export",
        "Export Purchase Reports",
        "purchase",
        "reports.export",
        "Export purchase reports to CSV/Excel",
    ),
    # --- Settings permissions ---
    PurchasePermissionDefinition(
        "purchase.settings.read",
        "View Purchase Settings",
        "purchase",
        "settings.read",
        "View purchase module configuration and master data",
    ),
    PurchasePermissionDefinition(
        "purchase.settings.update",
        "Edit Purchase Settings",
        "purchase",
        "settings.update",
        "Update purchase policies, feature flags, and master data",
    ),
    PurchasePermissionDefinition(
        "purchase.settings.manage",
        "Manage Purchase Feature Flags",
        "purchase",
        "settings.manage",
        "Enable or disable purchase module feature flags (Epic 9A "
        "security prerequisite, plan.md §14 — a distinct code from the "
        "pre-existing, unenforced 'settings.update' above)",
    ),
)

PURCHASE_PERMISSION_BY_CODE: Final[dict[str, PurchasePermissionDefinition]] = {
    p.code: p for p in PURCHASE_PERMISSIONS
}

# Feature-toggle mutation gate (Epic 9A Phase 10, T140, plan.md §14) — the
# permission code the PUT /feature-flags/{flag_key} handler checks.
PURCHASE_SETTINGS_MANAGE_PERMISSION: Final[str] = "purchase.settings.manage"


# ---------------------------------------------------------------------------
# Feature Flag Keys (spec §29 — Feature Matrix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureFlagDefinition:
    """Immutable definition of a feature flag."""

    key: str
    label: str
    description: str
    default_enabled: bool


PURCHASE_FEATURE_FLAGS: Final[tuple[FeatureFlagDefinition, ...]] = (
    # --- Ready & Enabled (approval-required flags default TRUE for safety) ---
    FeatureFlagDefinition(
        key="purchase.approval_required_pr",
        label="Purchase Request Approval Required",
        description="Require managerial approval for all purchase requests",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.approval_required_po",
        label="Purchase Order Approval Required",
        description="Require managerial approval for all purchase orders",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.approval_required_rma",
        label="Vendor Return Approval Required",
        description="Require managerial approval for vendor returns (RMAs)",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.credit_limit_check",
        label="Supplier Credit Limit Check",
        description="Evaluate supplier credit limit at PO approval (WARN mode by default)",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.over_receipt_warn",
        label="Over-Receipt Warning",
        description="Warn when goods receipt quantity exceeds PO quantity (WARN mode by default)",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.bulk_import_suppliers",
        label="Bulk Import Suppliers",
        description="CSV/Excel bulk supplier import",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.bulk_export_purchase",
        label="Bulk Export Purchase Data",
        description="CSV/Excel bulk export for suppliers and purchase documents",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="purchase.purchase_reporting",
        label="Purchase Reporting",
        description="Purchase reports, KPIs, and supplier performance analytics",
        default_enabled=True,
    ),
    # --- Ready but Disabled (require explicit activation) ---
    FeatureFlagDefinition(
        key="purchase.direct_po_allowed",
        label="Direct PO Without PR",
        description="Allow creating Purchase Orders without a preceding Purchase Request",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="purchase.ppv_alerts",
        label="Purchase Price Variance Alerts",
        description="Send Finance Manager notifications when PPV exceeds configurable threshold",
        default_enabled=False,
    ),
    # --- Integration features (Phase 10) — ready but disabled ---
    FeatureFlagDefinition(
        key="purchase.po_email_supplier",
        label="Email PO to Supplier on Approval",
        description=(
            "When enabled, PO approval triggers an email to the primary supplier contact "
            "with the PO summary. Requires email provider configuration."
        ),
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="purchase.gr_barcode_scan",
        label="Barcode Scan for GR Line Entry",
        description=(
            "When enabled, the barcode lookup endpoint resolves a product from the "
            "Epic 5 Inventory barcode API for Goods Receipt line entry."
        ),
        default_enabled=False,
    ),
    # --- Future (architecture reserved, not yet implemented) ---
    FeatureFlagDefinition(
        key="purchase.supplier_portal",
        label="Supplier Portal",
        description="Self-service supplier portal for PO acknowledgement and invoice submission",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="purchase.ai_procurement_assistant",
        label="AI Procurement Assistant",
        description="AI-powered demand prediction, reorder suggestions, and supplier risk analysis",
        default_enabled=False,
    ),
)

PURCHASE_FLAG_BY_KEY: Final[dict[str, FeatureFlagDefinition]] = {
    f.key: f for f in PURCHASE_FEATURE_FLAGS
}

# Set of keys that default to enabled — used for seeding
PURCHASE_DEFAULT_ENABLED_FLAGS: Final[frozenset[str]] = frozenset(
    f.key for f in PURCHASE_FEATURE_FLAGS if f.default_enabled
)


# ---------------------------------------------------------------------------
# Document type identifiers (used by PurchaseSequenceService)
# ---------------------------------------------------------------------------

DOCUMENT_TYPES: Final[tuple[str, ...]] = ("PR", "PO", "GR", "RMA")

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MODULE_NAME: Final[str] = "purchase"
MODULE_VERSION: Final[str] = "1.0.0"
SPEC_VERSION: Final[str] = "1.0.0"

# Maximum category tree depth (spec data-model.md §SupplierCategory)
SUPPLIER_CATEGORY_MAX_DEPTH: Final[int] = 5

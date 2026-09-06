"""Sales module constants.

Permission codes follow the pattern ``sales.<sub_domain>.<action>``
as defined in spec.md §29 Permission Matrix.

Feature flag keys follow the pattern ``sales.<capability>``
as defined in spec.md §30 Feature Matrix.

All definitions are frozen datastructures to prevent accidental mutation.

Spec ref: specs/007-sales-management/spec.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Permission Definitions (spec §29 — Permission Matrix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SalesPermissionDefinition:
    """Immutable definition of a sales module permission."""

    code: str
    label: str
    module: str
    action: str
    description: str


SALES_PERMISSIONS: Final[tuple[SalesPermissionDefinition, ...]] = (
    # --- Customer Master permissions ---
    SalesPermissionDefinition(
        "sales.customers.create",
        "Create Customers",
        "sales",
        "customers.create",
        "Create new customers in the customer master",
    ),
    SalesPermissionDefinition(
        "sales.customers.read",
        "View Customers",
        "sales",
        "customers.read",
        "View customer details and master catalogue",
    ),
    SalesPermissionDefinition(
        "sales.customers.update",
        "Edit Customers",
        "sales",
        "customers.update",
        "Update customer information and enrichment data",
    ),
    SalesPermissionDefinition(
        "sales.customers.delete",
        "Archive Customers",
        "sales",
        "customers.delete",
        "Archive and soft-delete customers",
    ),
    SalesPermissionDefinition(
        "sales.customers.activate",
        "Activate Customers",
        "sales",
        "customers.activate",
        "Transition customer status to ACTIVE",
    ),
    SalesPermissionDefinition(
        "sales.customers.block",
        "Block Customers",
        "sales",
        "customers.block",
        "Block customer from receiving new sales documents",
    ),
    SalesPermissionDefinition(
        "sales.customers.import",
        "Import Customers",
        "sales",
        "customers.import",
        "Bulk import customers via CSV/Excel",
    ),
    SalesPermissionDefinition(
        "sales.customers.export",
        "Export Customers",
        "sales",
        "customers.export",
        "Bulk export customers to CSV/Excel",
    ),
    SalesPermissionDefinition(
        "sales.customers.credit",
        "Manage Customer Credit",
        "sales",
        "customers.credit",
        "Set credit limits, place/release credit holds",
    ),
    # --- Quotation permissions ---
    SalesPermissionDefinition(
        "sales.quotations.create",
        "Create Quotations",
        "sales",
        "quotations.create",
        "Create new sales quotations",
    ),
    SalesPermissionDefinition(
        "sales.quotations.read",
        "View Quotations",
        "sales",
        "quotations.read",
        "View quotation details and list",
    ),
    SalesPermissionDefinition(
        "sales.quotations.update",
        "Edit Quotations",
        "sales",
        "quotations.update",
        "Update draft quotations",
    ),
    SalesPermissionDefinition(
        "sales.quotations.send",
        "Send Quotations",
        "sales",
        "quotations.send",
        "Send quotation to customer",
    ),
    SalesPermissionDefinition(
        "sales.quotations.convert",
        "Convert Quotations",
        "sales",
        "quotations.convert",
        "Convert accepted quotation to sales order",
    ),
    # --- Sales Order permissions ---
    SalesPermissionDefinition(
        "sales.orders.create",
        "Create Sales Orders",
        "sales",
        "orders.create",
        "Create new sales orders",
    ),
    SalesPermissionDefinition(
        "sales.orders.read",
        "View Sales Orders",
        "sales",
        "orders.read",
        "View sales order details and list",
    ),
    SalesPermissionDefinition(
        "sales.orders.update",
        "Edit Sales Orders",
        "sales",
        "orders.update",
        "Update draft sales orders",
    ),
    SalesPermissionDefinition(
        "sales.orders.approve",
        "Approve Sales Orders",
        "sales",
        "orders.approve",
        "Approve or reject sales orders pending approval",
    ),
    SalesPermissionDefinition(
        "sales.orders.cancel",
        "Cancel Sales Orders",
        "sales",
        "orders.cancel",
        "Cancel approved or draft sales orders",
    ),
    # --- Delivery Note permissions ---
    SalesPermissionDefinition(
        "sales.deliveries.create",
        "Create Delivery Notes",
        "sales",
        "deliveries.create",
        "Create delivery notes against approved sales orders",
    ),
    SalesPermissionDefinition(
        "sales.deliveries.read",
        "View Delivery Notes",
        "sales",
        "deliveries.read",
        "View delivery note details and list",
    ),
    SalesPermissionDefinition(
        "sales.deliveries.dispatch",
        "Dispatch Delivery Notes",
        "sales",
        "deliveries.dispatch",
        "Mark delivery note as dispatched (triggers stock deduction)",
    ),
    # --- Invoice permissions ---
    SalesPermissionDefinition(
        "sales.invoices.create",
        "Create Invoices",
        "sales",
        "invoices.create",
        "Create sales invoices from delivery notes",
    ),
    SalesPermissionDefinition(
        "sales.invoices.read",
        "View Invoices",
        "sales",
        "invoices.read",
        "View invoice details and list",
    ),
    SalesPermissionDefinition(
        "sales.invoices.issue",
        "Issue Invoices",
        "sales",
        "invoices.issue",
        "Issue invoices (assigns gap-free number)",
    ),
    SalesPermissionDefinition(
        "sales.invoices.cancel",
        "Cancel Invoices",
        "sales",
        "invoices.cancel",
        "Cancel draft invoices",
    ),
    # --- Sales Return permissions ---
    SalesPermissionDefinition(
        "sales.returns.create",
        "Create Sales Returns",
        "sales",
        "returns.create",
        "Initiate sales return (RMA) against an invoice",
    ),
    SalesPermissionDefinition(
        "sales.returns.read",
        "View Sales Returns",
        "sales",
        "returns.read",
        "View sales return details and list",
    ),
    SalesPermissionDefinition(
        "sales.returns.approve",
        "Approve Sales Returns",
        "sales",
        "returns.approve",
        "Approve or reject sales return requests",
    ),
    SalesPermissionDefinition(
        "sales.returns.receive",
        "Receive Sales Returns",
        "sales",
        "returns.receive",
        "Confirm receipt of returned goods (triggers stock restock)",
    ),
    # --- Pricing permissions ---
    SalesPermissionDefinition(
        "sales.pricing.read",
        "View Pricing",
        "sales",
        "pricing.read",
        "View price lists, discount rules, and pricing data",
    ),
    SalesPermissionDefinition(
        "sales.pricing.manage",
        "Manage Pricing",
        "sales",
        "pricing.manage",
        "Create and update price lists, discount rules",
    ),
    # --- Approval Matrix permissions ---
    SalesPermissionDefinition(
        "sales.approval_matrix.read",
        "View Sales Approval Matrix",
        "sales",
        "approval_matrix.read",
        "View sales approval matrix and rules",
    ),
    SalesPermissionDefinition(
        "sales.approval_matrix.manage",
        "Manage Sales Approval Matrix",
        "sales",
        "approval_matrix.manage",
        "Configure approval levels, rules, and delegates",
    ),
    # --- Reporting permissions ---
    SalesPermissionDefinition(
        "sales.reports.read",
        "View Sales Reports",
        "sales",
        "reports.read",
        "View sales reports, KPIs, and analytics",
    ),
    SalesPermissionDefinition(
        "sales.reports.export",
        "Export Sales Reports",
        "sales",
        "reports.export",
        "Export sales reports to CSV/Excel",
    ),
    # --- Settings permissions ---
    SalesPermissionDefinition(
        "sales.settings.read",
        "View Sales Settings",
        "sales",
        "settings.read",
        "View sales module configuration and master data",
    ),
    SalesPermissionDefinition(
        "sales.settings.update",
        "Edit Sales Settings",
        "sales",
        "settings.update",
        "Update sales policies, feature flags, and master data",
    ),
    SalesPermissionDefinition(
        "sales.settings.manage",
        "Manage Sales Feature Flags",
        "sales",
        "settings.manage",
        "Enable or disable sales module feature flags (Epic 9A security "
        "prerequisite, plan.md §14 — a distinct code from the "
        "pre-existing, unenforced 'settings.update' above)",
    ),
)

SALES_PERMISSION_BY_CODE: Final[dict[str, SalesPermissionDefinition]] = {
    p.code: p for p in SALES_PERMISSIONS
}

# Feature-toggle mutation gate (Epic 9A Phase 10, T139, plan.md §14) — the
# permission code the PUT /feature-flags/{flag_key} handler checks.
SALES_SETTINGS_MANAGE_PERMISSION: Final[str] = "sales.settings.manage"


# ---------------------------------------------------------------------------
# Feature Flag Keys (spec §30 — Feature Matrix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureFlagDefinition:
    """Immutable definition of a feature flag."""

    key: str
    label: str
    description: str
    default_enabled: bool


SALES_FEATURE_FLAGS: Final[tuple[FeatureFlagDefinition, ...]] = (
    # --- Ready & Enabled ---
    FeatureFlagDefinition(
        key="sales.approval_required_so",
        label="Sales Order Approval Required",
        description="Require managerial approval for all sales orders",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.approval_required_return",
        label="Sales Return Approval Required",
        description="Require managerial approval for sales returns (RMAs)",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.credit_limit_check",
        label="Customer Credit Limit Check",
        description="Evaluate customer credit limit at SO approval",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.inventory_reservation",
        label="Inventory Reservation on SO",
        description="Reserve inventory on sales order approval via Epic 5 integration",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.pricing_engine",
        label="Pricing Engine",
        description="7-level price resolution with discount rules and margin guard",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.gap_free_invoicing",
        label="Gap-Free Invoice Numbering",
        description="Enforce sequential gap-free invoice numbers using advisory locks",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.customer_bulk_import",
        label="Bulk Import Customers",
        description="CSV/Excel bulk customer import",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.bulk_export",
        label="Bulk Export Sales Data",
        description="CSV/Excel bulk export for customers and sales documents",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="sales.sales_reporting",
        label="Sales Reporting",
        description="Sales reports, KPIs, and analytics dashboard",
        default_enabled=True,
    ),
    # --- Ready but Disabled ---
    FeatureFlagDefinition(
        key="sales.quotation_required",
        label="Quotation Required Before Order",
        description="Require a converted quotation before creating a sales order",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="sales.auto_approve_below_threshold",
        label="Auto-Approve Below Threshold",
        description="Automatically approve sales orders below configured threshold",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="sales.margin_guard",
        label="Margin Guard",
        description="Block sales below minimum margin percentage",
        default_enabled=False,
    ),
    # --- Future ---
    FeatureFlagDefinition(
        key="sales.customer_portal",
        label="Customer Portal",
        description="Self-service customer portal for order placement and tracking",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="sales.ai_sales_assistant",
        label="AI Sales Assistant",
        description="AI-powered demand prediction, churn analysis, and pricing suggestions",
        default_enabled=False,
    ),
)

SALES_FLAG_BY_KEY: Final[dict[str, FeatureFlagDefinition]] = {
    f.key: f for f in SALES_FEATURE_FLAGS
}

# Set of keys that default to enabled — used for seeding
SALES_DEFAULT_ENABLED_FLAGS: Final[frozenset[str]] = frozenset(
    f.key for f in SALES_FEATURE_FLAGS if f.default_enabled
)


# ---------------------------------------------------------------------------
# Document type identifiers (used by SalesSequenceService)
# ---------------------------------------------------------------------------

DOCUMENT_TYPES: Final[tuple[str, ...]] = ("SQ", "SO", "DN", "SI", "SR")

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MODULE_NAME: Final[str] = "sales"
MODULE_VERSION: Final[str] = "1.0.0"
SPEC_VERSION: Final[str] = "1.0.0"

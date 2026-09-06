"""Users & Roles module constants.

System role definitions match spec FR-040 exactly.
Initial permission codes match spec Section 6.1.
Role-permission matrix matches data-model.md Section 2.4.

All definitions are frozen datastructures to prevent accidental mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# System Role Definitions (spec FR-040, data-model.md Section 2.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SystemRoleDefinition:
    """Immutable definition of a system-seeded role."""

    name: str
    slug: str
    rank: int
    description: str


SYSTEM_ROLES: Final[tuple[SystemRoleDefinition, ...]] = (
    SystemRoleDefinition(
        name="Owner",
        slug="owner",
        rank=100,
        description="Company owner with full authority",
    ),
    SystemRoleDefinition(
        name="Administrator",
        slug="admin",
        rank=80,
        description="Daily administration and user management",
    ),
    SystemRoleDefinition(
        name="Manager",
        slug="manager",
        rank=60,
        description="Department operations management",
    ),
    SystemRoleDefinition(
        name="Accountant",
        slug="accountant",
        rank=55,
        description="Financial operations",
    ),
    SystemRoleDefinition(
        name="Salesperson",
        slug="salesperson",
        rank=50,
        description="Sales operations",
    ),
    SystemRoleDefinition(
        name="Cashier",
        slug="cashier",
        rank=45,
        description="Point-of-sale operations",
    ),
    SystemRoleDefinition(
        name="Store Keeper",
        slug="store-keeper",
        rank=42,
        description="Inventory/warehouse operations",
    ),
    SystemRoleDefinition(
        name="Viewer",
        slug="viewer",
        rank=20,
        description="Read-only access",
    ),
)

# Lookup helpers
SYSTEM_ROLE_BY_SLUG: Final[dict[str, SystemRoleDefinition]] = {
    r.slug: r for r in SYSTEM_ROLES
}

OWNER_RANK: Final[int] = 100
ADMIN_RANK: Final[int] = 80
MIN_RANK: Final[int] = 1
MAX_RANK: Final[int] = 100


# ---------------------------------------------------------------------------
# Initial Permission Codes (spec Section 6.1, data-model.md Section 2.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PermissionDefinition:
    """Immutable definition of a platform permission."""

    code: str
    label: str
    module: str
    action: str
    description: str


# Epic 10 (Installments) — all 16 installments.* permission codes
# (plan.md §16.1), unioned into INITIAL_PERMISSIONS below so
# RoleSeedService grants them to every NEW company automatically at
# creation time (plan.md §30.1 point 1). Existing companies are backfilled
# separately by migration 071_installments_permission_backfill.py, which
# this tuple's codes/labels/descriptions intentionally match exactly.
INSTALLMENTS_PERMISSIONS: Final[tuple[PermissionDefinition, ...]] = (
    PermissionDefinition(
        "installments.config.manage",
        "Manage Installments Configuration",
        "installments",
        "manage",
        "Configure tenant-level installment policy",
    ),
    PermissionDefinition(
        "installments.plan.manage",
        "Manage Installment Plan Templates",
        "installments",
        "manage",
        "Create/edit/deactivate installment plan templates",
    ),
    PermissionDefinition(
        "installments.contract.view",
        "View Installment Contracts",
        "installments",
        "read",
        "View installment contracts and schedules",
    ),
    PermissionDefinition(
        "installments.contract.create",
        "Create Installment Contracts",
        "installments",
        "create",
        "Create a draft installment contract / quote",
    ),
    PermissionDefinition(
        "installments.contract.approve",
        "Approve Installment Contracts",
        "installments",
        "manage",
        "Approve a submitted installment contract",
    ),
    PermissionDefinition(
        "installments.contract.activate",
        "Activate Installment Contracts",
        "installments",
        "manage",
        "Activate an approved installment contract",
    ),
    PermissionDefinition(
        "installments.collection.create",
        "Record Installment Collections",
        "installments",
        "create",
        "Record an installment collection",
    ),
    PermissionDefinition(
        "installments.collection.reverse",
        "Reverse Installment Collections",
        "installments",
        "manage",
        "Reverse a recorded installment collection",
    ),
    PermissionDefinition(
        "installments.charge.waive",
        "Waive Late Charges",
        "installments",
        "manage",
        "Waive an installment late charge",
    ),
    PermissionDefinition(
        "installments.contract.reschedule",
        "Reschedule Installment Contracts",
        "installments",
        "manage",
        "Controlled due-date amendment of an installment schedule",
    ),
    PermissionDefinition(
        "installments.contract.cancel",
        "Cancel Installment Contracts",
        "installments",
        "manage",
        "Cancel an installment contract",
    ),
    PermissionDefinition(
        "installments.contract.default",
        "Mark Installment Contracts Defaulted",
        "installments",
        "manage",
        "Mark an installment contract as defaulted",
    ),
    PermissionDefinition(
        "installments.contract.cure",
        "Cure Defaulted Installment Contracts",
        "installments",
        "manage",
        "Restore a defaulted installment contract to active",
    ),
    PermissionDefinition(
        "installments.contract.writeoff",
        "Write Off Installment Contracts",
        "installments",
        "manage",
        "Write off a defaulted installment balance",
    ),
    PermissionDefinition(
        "installments.settlement.execute",
        "Execute Installment Settlements",
        "installments",
        "manage",
        "Generate/execute an early installment settlement",
    ),
    PermissionDefinition(
        "installments.report.view",
        "View Installment Reports",
        "installments",
        "read",
        "View installment reports/dashboards",
    ),
)


INITIAL_PERMISSIONS: Final[tuple[PermissionDefinition, ...]] = (
    # Members module
    PermissionDefinition(
        "members.create",
        "Add Members",
        "members",
        "create",
        "Create new company memberships",
    ),
    PermissionDefinition(
        "members.read",
        "View Members",
        "members",
        "read",
        "View member list and details",
    ),
    PermissionDefinition(
        "members.update",
        "Edit Members",
        "members",
        "update",
        "Update member information",
    ),
    PermissionDefinition(
        "members.delete",
        "Remove Members",
        "members",
        "delete",
        "Archive company memberships",
    ),
    PermissionDefinition(
        "members.manage",
        "Manage Member Status",
        "members",
        "manage",
        "Change member lifecycle status",
    ),
    # Roles module
    PermissionDefinition(
        "roles.create", "Create Roles", "roles", "create", "Create custom roles"
    ),
    PermissionDefinition(
        "roles.read", "View Roles", "roles", "read", "View role list and details"
    ),
    PermissionDefinition(
        "roles.update",
        "Edit Roles",
        "roles",
        "update",
        "Update custom role definitions",
    ),
    PermissionDefinition(
        "roles.delete", "Delete Roles", "roles", "delete", "Delete custom roles"
    ),
    # Companies module
    PermissionDefinition(
        "companies.read", "View Company", "companies", "read", "View company details"
    ),
    PermissionDefinition(
        "companies.update",
        "Edit Company",
        "companies",
        "update",
        "Update company settings",
    ),
    PermissionDefinition(
        "companies.manage",
        "Manage Company",
        "companies",
        "manage",
        "Full company management",
    ),
    # Profile module
    PermissionDefinition(
        "profile.read", "View Profiles", "profile", "read", "View member profiles"
    ),
    PermissionDefinition(
        "profile.update",
        "Edit Own Profile",
        "profile",
        "update",
        "Update own profile and preferences",
    ),
    # Accounting module (Epic 8, Phase 14 — spec.md §33 Permission Matrix)
    PermissionDefinition(
        "accounting.gl.view",
        "View General Ledger",
        "accounting",
        "read",
        "View GL entries and balances",
    ),
    PermissionDefinition(
        "accounting.journal.create",
        "Create Journal Entry",
        "accounting",
        "create",
        "Create a manual journal entry",
    ),
    PermissionDefinition(
        "accounting.journal.approve",
        "Approve Journal Entry",
        "accounting",
        "approve",
        "Approve a journal entry submitted for approval",
    ),
    PermissionDefinition(
        "accounting.journal.post",
        "Post Journal Entry",
        "accounting",
        "update",
        "Post a draft/approved journal entry to the GL",
    ),
    PermissionDefinition(
        "accounting.journal.reverse",
        "Reverse Journal Entry",
        "accounting",
        "update",
        "Reverse a posted journal entry",
    ),
    PermissionDefinition(
        "accounting.period.lock",
        "Lock/Unlock Period",
        "accounting",
        "manage",
        "Lock or unlock a fiscal period",
    ),
    PermissionDefinition(
        "accounting.period.close",
        "Close Fiscal Year",
        "accounting",
        "manage",
        "Close a fiscal year",
    ),
    PermissionDefinition(
        "accounting.payment.customer.create",
        "Create Customer Payment",
        "accounting",
        "create",
        "Record a customer payment receipt",
    ),
    PermissionDefinition(
        "accounting.payment.customer.approve",
        "Approve Customer Payment",
        "accounting",
        "approve",
        "Approve a customer payment submitted for approval",
    ),
    PermissionDefinition(
        "accounting.payment.supplier.create",
        "Create Supplier Payment",
        "accounting",
        "create",
        "Record a supplier payment disbursement",
    ),
    PermissionDefinition(
        "accounting.payment.supplier.approve",
        "Approve Supplier Payment",
        "accounting",
        "approve",
        "Approve a supplier payment submitted for approval",
    ),
    PermissionDefinition(
        "accounting.coa.manage",
        "Manage Chart of Accounts",
        "accounting",
        "manage",
        "Create/update/deactivate accounts",
    ),
    PermissionDefinition(
        "accounting.tax.manage",
        "Manage Tax Codes",
        "accounting",
        "manage",
        "Create/update tax codes, rates, and groups",
    ),
    PermissionDefinition(
        "accounting.exchangerate.manage",
        "Manage Exchange Rates",
        "accounting",
        "manage",
        "Record exchange rates and run currency revaluation",
    ),
    PermissionDefinition(
        "accounting.bank.reconcile",
        "Perform Bank Reconciliation",
        "accounting",
        "update",
        "Reconcile bank statements",
    ),
    PermissionDefinition(
        "accounting.reports.view",
        "View Financial Statements",
        "accounting",
        "read",
        "View trial balance, balance sheet, P&L, cash flow, and subsidiary reports",
    ),
    PermissionDefinition(
        "accounting.ar.writeoff",
        "Write-Off AR",
        "accounting",
        "manage",
        "Write off an uncollectible AR balance",
    ),
    PermissionDefinition(
        "accounting.creditlimit.override",
        "Override Credit Limit",
        "accounting",
        "manage",
        "Override a customer's credit hold/limit",
    ),
    PermissionDefinition(
        "accounting.approvalworkflow.manage",
        "Manage Approval Workflows",
        "accounting",
        "manage",
        "Configure journal/payment approval thresholds",
    ),
    PermissionDefinition(
        "accounting.audit.view",
        "View Audit Trail",
        "accounting",
        "read",
        "View the full financial audit trail",
    ),
    # CRM module (Epic 9, Phase 8 — spec.md §31.1 Permission Matrix)
    PermissionDefinition("crm.leads.view", "View Leads", "crm", "read", "View leads"),
    PermissionDefinition(
        "crm.leads.create", "Create Leads", "crm", "create", "Create leads"
    ),
    PermissionDefinition(
        "crm.leads.update",
        "Update Leads",
        "crm",
        "update",
        "Update leads, including qualify/disqualify",
    ),
    PermissionDefinition(
        "crm.leads.delete", "Delete Leads", "crm", "delete", "Soft-delete leads"
    ),
    PermissionDefinition(
        "crm.leads.assign",
        "Assign Leads",
        "crm",
        "manage",
        "Reassign lead ownership",
    ),
    PermissionDefinition(
        "crm.leads.convert",
        "Convert Leads",
        "crm",
        "update",
        "Convert a qualified lead",
    ),
    PermissionDefinition(
        "crm.opportunities.view",
        "View Opportunities",
        "crm",
        "read",
        "View opportunities",
    ),
    PermissionDefinition(
        "crm.opportunities.create",
        "Create Opportunities",
        "crm",
        "create",
        "Create opportunities",
    ),
    PermissionDefinition(
        "crm.opportunities.update",
        "Update Opportunities",
        "crm",
        "update",
        "Update opportunities, including stage changes",
    ),
    PermissionDefinition(
        "crm.opportunities.delete",
        "Delete Opportunities",
        "crm",
        "delete",
        "Soft-delete opportunities",
    ),
    PermissionDefinition(
        "crm.opportunities.assign",
        "Assign Opportunities",
        "crm",
        "manage",
        "Reassign opportunity ownership",
    ),
    PermissionDefinition(
        "crm.opportunities.close",
        "Close Opportunities",
        "crm",
        "manage",
        "Mark an opportunity WON or LOST",
    ),
    PermissionDefinition(
        "crm.activities.view",
        "View Activities",
        "crm",
        "read",
        "View activities",
    ),
    PermissionDefinition(
        "crm.activities.create",
        "Create Activities",
        "crm",
        "create",
        "Create activities",
    ),
    PermissionDefinition(
        "crm.activities.update",
        "Update Activities",
        "crm",
        "update",
        "Update/complete activities",
    ),
    PermissionDefinition(
        "crm.activities.delete",
        "Delete Activities",
        "crm",
        "delete",
        "Soft-delete activities",
    ),
    PermissionDefinition(
        "crm.pipeline.view",
        "View Pipelines",
        "crm",
        "read",
        "View pipelines/stages",
    ),
    PermissionDefinition(
        "crm.pipeline.manage",
        "Manage Pipelines",
        "crm",
        "manage",
        "Create/update/deactivate pipelines and stages",
    ),
    PermissionDefinition(
        "crm.reports.view",
        "View CRM Reports",
        "crm",
        "read",
        "View CRM reports/KPIs/dashboard",
    ),
    # Epic 9A Phase 10 (T138-T141, plan.md §14) — feature-toggle mutation
    # hardening for the three modules confirmed vulnerable during
    # reconnaissance (Inventory, Sales, Purchase had no permission check
    # beyond active tenant membership on PUT .../feature-flags/{key}).
    # Accounting and CRM already had an equivalent code and are untouched.
    PermissionDefinition(
        "inventory.settings.manage",
        "Manage Inventory Feature Flags",
        "inventory",
        "manage",
        "Enable or disable inventory module feature flags",
    ),
    PermissionDefinition(
        "sales.settings.manage",
        "Manage Sales Feature Flags",
        "sales",
        "manage",
        "Enable or disable sales module feature flags",
    ),
    PermissionDefinition(
        "purchase.settings.manage",
        "Manage Purchase Feature Flags",
        "purchase",
        "manage",
        "Enable or disable purchase module feature flags",
    ),
) + INSTALLMENTS_PERMISSIONS

PERMISSION_BY_CODE: Final[dict[str, PermissionDefinition]] = {
    p.code: p for p in INITIAL_PERMISSIONS
}


# ---------------------------------------------------------------------------
# Default Role-Permission Matrix (data-model.md Section 2.4)
# ---------------------------------------------------------------------------

# Accounting (Epic 8) role mapping rationale — spec.md §33 Permission Matrix
# defines its own conceptual roles (CFO, Controller, Accountant, AR Clerk,
# AP Clerk, Cashier, System Admin) that do not 1:1 exist in Epic 4's
# SYSTEM_ROLES. Per spec.md §33's own footnote ("This matrix represents the
# default configuration" — additive/configurable, not a hard requirement),
# each spec-role's "Yes" cells are granted to the closest existing system
# role instead of inventing new roles (out of this phase's scope):
#   CFO           -> owner        (full authority, rank 100)
#   System Admin  -> admin        (rank 80; per the matrix, System Admin
#                                  does NOT get journal/payment create-or-
#                                  approve rights — a deliberate SoD gap)
#   Controller    -> manager      (rank 60; "operational ownership" persona,
#                                  gets everything except Close Fiscal Year
#                                  and Manage Approval Workflows, CFO-only)
#   Accountant    -> accountant   (exact existing role/name match)
#   Cashier       -> cashier      (exact existing role/name match)
#   AR Clerk      -> salesperson  (closest customer-facing analogue)
#   AP Clerk      -> (no existing analogue; intentionally not granted —
#                     under-granting is safer than mis-granting)
#   Auditor       -> viewer       (read-only reports/audit/GL)
_ACCOUNTING_CFO: Final[frozenset[str]] = frozenset(
    {
        "accounting.gl.view",
        "accounting.journal.create",
        "accounting.journal.approve",
        "accounting.journal.post",
        "accounting.journal.reverse",
        "accounting.period.lock",
        "accounting.period.close",
        "accounting.payment.customer.create",
        "accounting.payment.customer.approve",
        "accounting.payment.supplier.create",
        "accounting.payment.supplier.approve",
        "accounting.coa.manage",
        "accounting.tax.manage",
        "accounting.exchangerate.manage",
        "accounting.bank.reconcile",
        "accounting.reports.view",
        "accounting.ar.writeoff",
        "accounting.creditlimit.override",
        "accounting.approvalworkflow.manage",
        "accounting.audit.view",
    }
)
_ACCOUNTING_SYSTEM_ADMIN: Final[frozenset[str]] = frozenset(
    {
        "accounting.gl.view",
        "accounting.period.close",
        "accounting.reports.view",
        "accounting.approvalworkflow.manage",
        "accounting.audit.view",
    }
)
_ACCOUNTING_CONTROLLER: Final[frozenset[str]] = frozenset(
    {
        "accounting.gl.view",
        "accounting.journal.create",
        "accounting.journal.approve",
        "accounting.journal.post",
        "accounting.journal.reverse",
        "accounting.period.lock",
        "accounting.payment.customer.create",
        "accounting.payment.customer.approve",
        "accounting.payment.supplier.create",
        "accounting.payment.supplier.approve",
        "accounting.coa.manage",
        "accounting.tax.manage",
        "accounting.exchangerate.manage",
        "accounting.bank.reconcile",
        "accounting.reports.view",
        "accounting.ar.writeoff",
        "accounting.creditlimit.override",
        "accounting.audit.view",
    }
)
_ACCOUNTING_ACCOUNTANT: Final[frozenset[str]] = frozenset(
    {
        "accounting.gl.view",
        "accounting.journal.create",
        "accounting.journal.post",
        "accounting.coa.manage",
        "accounting.exchangerate.manage",
        "accounting.bank.reconcile",
        "accounting.reports.view",
    }
)
_ACCOUNTING_AR_CLERK: Final[frozenset[str]] = frozenset(
    {
        "accounting.payment.customer.create",
        "accounting.reports.view",
    }
)
_ACCOUNTING_CASHIER: Final[frozenset[str]] = frozenset(
    {
        "accounting.payment.customer.create",
        "accounting.payment.supplier.create",
    }
)
_ACCOUNTING_VIEWER: Final[frozenset[str]] = frozenset(
    {
        "accounting.gl.view",
        "accounting.reports.view",
        "accounting.audit.view",
    }
)

# CRM (Epic 9) role mapping — spec.md §31.2's own Role Access Matrix, whose
# columns are the actual SYSTEM_ROLES slugs directly (no persona-mapping
# step is needed here, unlike Accounting's spec-role -> system-role
# translation above, since CRM's spec was authored directly against
# owner/admin/manager/accountant/salesperson/cashier/store-keeper/viewer).
# cashier and store-keeper are N across every one of the 19 permissions —
# both are intentionally left with zero CRM grants (no new frozenset, no
# union added to either role's entry below).
_CRM_OWNER: Final[frozenset[str]] = frozenset(
    {
        "crm.leads.view",
        "crm.leads.create",
        "crm.leads.update",
        "crm.leads.delete",
        "crm.leads.assign",
        "crm.leads.convert",
        "crm.opportunities.view",
        "crm.opportunities.create",
        "crm.opportunities.update",
        "crm.opportunities.delete",
        "crm.opportunities.assign",
        "crm.opportunities.close",
        "crm.activities.view",
        "crm.activities.create",
        "crm.activities.update",
        "crm.activities.delete",
        "crm.pipeline.view",
        "crm.pipeline.manage",
        "crm.reports.view",
    }
)
# Admin's CRM grants are identical to Owner's per spec.md §31.2's matrix
# (both columns are Y for all 19 rows) — kept as its own named constant,
# not a reused reference, so a future divergence between the two roles'
# CRM grants requires touching only one frozenset, matching the existing
# per-role-constant convention used throughout this file.
_CRM_ADMIN: Final[frozenset[str]] = frozenset(
    {
        "crm.leads.view",
        "crm.leads.create",
        "crm.leads.update",
        "crm.leads.delete",
        "crm.leads.assign",
        "crm.leads.convert",
        "crm.opportunities.view",
        "crm.opportunities.create",
        "crm.opportunities.update",
        "crm.opportunities.delete",
        "crm.opportunities.assign",
        "crm.opportunities.close",
        "crm.activities.view",
        "crm.activities.create",
        "crm.activities.update",
        "crm.activities.delete",
        "crm.pipeline.view",
        "crm.pipeline.manage",
        "crm.reports.view",
    }
)
_CRM_MANAGER: Final[frozenset[str]] = frozenset(
    {
        "crm.leads.view",
        "crm.leads.create",
        "crm.leads.update",
        "crm.leads.delete",
        "crm.leads.assign",
        "crm.leads.convert",
        "crm.opportunities.view",
        "crm.opportunities.create",
        "crm.opportunities.update",
        "crm.opportunities.delete",
        "crm.opportunities.assign",
        "crm.opportunities.close",
        "crm.activities.view",
        "crm.activities.create",
        "crm.activities.update",
        "crm.activities.delete",
        "crm.pipeline.view",
        # crm.pipeline.manage: N for Manager (Owner/Admin-only, spec.md §33)
        "crm.reports.view",
    }
)
_CRM_ACCOUNTANT: Final[frozenset[str]] = frozenset(
    {
        "crm.leads.view",
        "crm.opportunities.view",
        "crm.activities.view",
        "crm.pipeline.view",
        "crm.reports.view",
    }
)
_CRM_SALESPERSON: Final[frozenset[str]] = frozenset(
    {
        "crm.leads.view",
        "crm.leads.create",
        "crm.leads.update",
        "crm.leads.convert",
        "crm.opportunities.view",
        "crm.opportunities.create",
        "crm.opportunities.update",
        "crm.activities.view",
        "crm.activities.create",
        "crm.activities.update",
        "crm.pipeline.view",
    }
)
_CRM_VIEWER: Final[frozenset[str]] = frozenset(
    {
        "crm.leads.view",
        "crm.opportunities.view",
        "crm.activities.view",
        "crm.pipeline.view",
        "crm.reports.view",
    }
)

# Epic 10 (Installments) role mapping — plan.md §30.1's own per-role grant
# table, matching migration 071_installments_permission_backfill.py's
# ``_ROLE_GRANTS`` exactly (that migration backfills existing companies;
# these frozensets cover every NEW company via RoleSeedService). Deliberate
# deviation from CRM's "cashier/store-keeper get zero" precedent:
# Installments' spec explicitly names Cashier/Collector as an actor who
# records collections, so cashier receives two grants below;
# store-keeper remains at zero (no relevance to Installments, matching
# CRM's own precedent for that role — no frozenset, no union added).
_INSTALLMENTS_OWNER: Final[frozenset[str]] = frozenset(
    {
        "installments.config.manage",
        "installments.plan.manage",
        "installments.contract.view",
        "installments.contract.create",
        "installments.contract.approve",
        "installments.contract.activate",
        "installments.collection.create",
        "installments.collection.reverse",
        "installments.charge.waive",
        "installments.contract.reschedule",
        "installments.contract.cancel",
        "installments.contract.default",
        "installments.contract.cure",
        "installments.contract.writeoff",
        "installments.settlement.execute",
        "installments.report.view",
    }
)
# Admin's Installments grants are identical to Owner's per plan.md §30.1's
# table (both get all 16) — kept as its own named constant, not a reused
# reference, matching the existing per-role-constant convention used
# throughout this file (see _CRM_ADMIN's identical rationale above).
_INSTALLMENTS_ADMIN: Final[frozenset[str]] = frozenset(
    {
        "installments.config.manage",
        "installments.plan.manage",
        "installments.contract.view",
        "installments.contract.create",
        "installments.contract.approve",
        "installments.contract.activate",
        "installments.collection.create",
        "installments.collection.reverse",
        "installments.charge.waive",
        "installments.contract.reschedule",
        "installments.contract.cancel",
        "installments.contract.default",
        "installments.contract.cure",
        "installments.contract.writeoff",
        "installments.settlement.execute",
        "installments.report.view",
    }
)
_INSTALLMENTS_MANAGER: Final[frozenset[str]] = frozenset(
    {
        "installments.contract.view",
        "installments.contract.approve",
        "installments.contract.reschedule",
        "installments.contract.cancel",
        "installments.contract.default",
        "installments.contract.writeoff",
        "installments.charge.waive",
        "installments.settlement.execute",
        "installments.contract.cure",
        "installments.report.view",
    }
)
_INSTALLMENTS_ACCOUNTANT: Final[frozenset[str]] = frozenset(
    {
        "installments.contract.view",
        "installments.collection.reverse",
        "installments.settlement.execute",
        "installments.report.view",
    }
)
_INSTALLMENTS_SALESPERSON: Final[frozenset[str]] = frozenset(
    {
        "installments.contract.view",
        "installments.contract.create",
        "installments.plan.manage",
    }
)
_INSTALLMENTS_CASHIER: Final[frozenset[str]] = frozenset(
    {
        "installments.contract.view",
        "installments.collection.create",
    }
)
_INSTALLMENTS_VIEWER: Final[frozenset[str]] = frozenset(
    {
        "installments.contract.view",
        "installments.report.view",
    }
)

# Epic 9A Phase 10 (T141, plan.md §14 risk mitigation) — granted to
# owner/admin only, so existing tenant admins can still manage feature
# toggles immediately after deploy; ordinary members cannot.
_FEATURE_TOGGLE_MANAGE: Final[frozenset[str]] = frozenset(
    {
        "inventory.settings.manage",
        "sales.settings.manage",
        "purchase.settings.manage",
    }
)

# Maps role slug → frozenset of permission codes granted by default
DEFAULT_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "owner": frozenset(
        {
            "members.create",
            "members.read",
            "members.update",
            "members.delete",
            "members.manage",
            "roles.create",
            "roles.read",
            "roles.update",
            "roles.delete",
            "companies.read",
            "companies.update",
            "companies.manage",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_CFO
        | _CRM_OWNER
        | _FEATURE_TOGGLE_MANAGE
        | _INSTALLMENTS_OWNER
    ),
    "admin": frozenset(
        {
            "members.create",
            "members.read",
            "members.update",
            "members.delete",
            "members.manage",
            "roles.create",
            "roles.read",
            "roles.update",
            "roles.delete",
            "companies.read",
            "companies.update",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_SYSTEM_ADMIN
        | _FEATURE_TOGGLE_MANAGE
        | _CRM_ADMIN
        | _INSTALLMENTS_ADMIN
    ),
    "manager": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_CONTROLLER
        | _CRM_MANAGER
        | _INSTALLMENTS_MANAGER
    ),
    "accountant": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_ACCOUNTANT
        | _CRM_ACCOUNTANT
        | _INSTALLMENTS_ACCOUNTANT
    ),
    "salesperson": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_AR_CLERK
        | _CRM_SALESPERSON
        | _INSTALLMENTS_SALESPERSON
    ),
    "cashier": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_CASHIER
        | _INSTALLMENTS_CASHIER
    ),
    "store-keeper": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
    ),
    "viewer": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
        | _ACCOUNTING_VIEWER
        | _CRM_VIEWER
        | _INSTALLMENTS_VIEWER
    ),
}


# ---------------------------------------------------------------------------
# Membership Status Transitions (data-model.md Section 2.1)
# ---------------------------------------------------------------------------

# Maps (from_status, to_status) → True if transition is permitted
VALID_STATUS_TRANSITIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("pending_invitation", "active"),
        ("active", "inactive"),
        ("active", "suspended"),
        ("active", "locked"),
        ("active", "archived"),
        ("inactive", "active"),
        ("inactive", "archived"),
        ("suspended", "active"),
        ("suspended", "archived"),
        ("locked", "active"),
        ("locked", "archived"),
        ("archived", "active"),
    }
)

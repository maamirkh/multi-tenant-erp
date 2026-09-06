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
)

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

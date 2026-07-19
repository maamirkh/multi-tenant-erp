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
)

PERMISSION_BY_CODE: Final[dict[str, PermissionDefinition]] = {
    p.code: p for p in INITIAL_PERMISSIONS
}


# ---------------------------------------------------------------------------
# Default Role-Permission Matrix (data-model.md Section 2.4)
# ---------------------------------------------------------------------------

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
    ),
    "manager": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
    ),
    "accountant": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
    ),
    "salesperson": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
    ),
    "cashier": frozenset(
        {
            "members.read",
            "roles.read",
            "companies.read",
            "profile.read",
            "profile.update",
        }
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

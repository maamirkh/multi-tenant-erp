"""Companies domain enumerations.

All enum values use lowercase string representations matching the spec §2
Terminology and §10.1 Database Design exactly.
"""

from __future__ import annotations

import enum


class CompanyStatus(str, enum.Enum):
    """Lifecycle states for a Company.

    Allowed transitions (spec §5.6):
        pending_setup → active      (Owner completes setup)
        active        → inactive    (Owner deactivates)
        inactive      → active      (Owner reactivates)
        active/inactive → suspended (SuperAdmin only)
        suspended     → active      (SuperAdmin only)
        active/inactive → deleted   (Owner soft-deletes)
        deleted       → inactive    (Owner restores within retention window)
    """

    pending_setup = "pending_setup"
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    deleted = "deleted"


class AddressType(str, enum.Enum):
    """Type classification for a company address record."""

    registered = "registered"
    mailing = "mailing"
    billing = "billing"
    shipping = "shipping"


class BusinessType(str, enum.Enum):
    """Legal structure / business type of a company."""

    sole_proprietor = "sole_proprietor"
    partnership = "partnership"
    llc = "llc"
    corporation = "corporation"
    non_profit = "non_profit"
    other = "other"

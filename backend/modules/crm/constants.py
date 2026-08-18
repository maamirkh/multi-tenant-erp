"""CRM module constants — lifecycle enums and valid-transition maps.

Single source of truth for CRM status/type string constants, avoiding
magic strings scattered across services. Transition maps mirror the exact
``_VALID_TRANSITIONS`` idiom already used in
``modules/sales/services/order_service.py``.

Spec ref: specs/009-crm/spec.md §14.2 (Lead Lifecycle), §17.2 (Opportunity
Lifecycle), §19.1 (Activity types/statuses/priorities).
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

LEAD_STATUSES: Final[frozenset[str]] = frozenset(
    {"NEW", "CONTACTED", "QUALIFIED", "UNQUALIFIED", "CONVERTED", "LOST"}
)

#: Valid Lead status transitions, per spec.md §14.2's lifecycle diagram
#: exactly. ``UNQUALIFIED -> NEW`` is the one explicit reopen exception
#: (manager-only, per §14.2). ``CONVERTED`` and ``LOST`` are terminal —
#: no outgoing transitions.
LEAD_VALID_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "NEW": frozenset({"CONTACTED", "LOST"}),
    "CONTACTED": frozenset({"QUALIFIED", "UNQUALIFIED"}),
    "QUALIFIED": frozenset({"CONVERTED", "UNQUALIFIED"}),
    "UNQUALIFIED": frozenset({"NEW"}),
    "CONVERTED": frozenset(),
    "LOST": frozenset(),
}

LEAD_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"CONVERTED", "LOST"})

# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------

OPPORTUNITY_STATUSES: Final[frozenset[str]] = frozenset({"OPEN", "WON", "LOST"})

#: Valid Opportunity status transitions, per spec.md §17.2. Stage
#: progression while ``status=OPEN`` is not a status transition (it is a
#: change to ``stage_id``, a separate field) and is therefore not modeled
#: here. ``WON``/``LOST`` are terminal.
OPPORTUNITY_VALID_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "OPEN": frozenset({"WON", "LOST"}),
    "WON": frozenset(),
    "LOST": frozenset(),
}

OPPORTUNITY_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"WON", "LOST"})

# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

ACTIVITY_TYPES: Final[frozenset[str]] = frozenset(
    {"CALL", "EMAIL", "MEETING", "TASK", "NOTE", "FOLLOW_UP"}
)

ACTIVITY_STATUSES: Final[frozenset[str]] = frozenset(
    {"PLANNED", "COMPLETED", "CANCELLED"}
)

ACTIVITY_PRIORITIES: Final[frozenset[str]] = frozenset({"LOW", "MEDIUM", "HIGH"})

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

#: The single CRM module feature flag key. Unlike Sales/Accounting/Inventory
#: (each of which gates several independent capabilities behind its own
#: flag registry), CRM has exactly one all-or-nothing module gate — see
#: plan.md §17/§21.5 — so ``CrmFeatureFlagService`` deliberately exposes a
#: simpler ``is_enabled(company_id)`` (no ``flag_key`` argument) rather than
#: mirroring the multi-flag registry pattern used elsewhere.
CRM_ENABLED_FLAG_KEY: Final[str] = "feature.crm.enabled"

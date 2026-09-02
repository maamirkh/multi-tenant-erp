"""Installments module constants.

Permission codes follow the pattern ``installments.<resource>.<action>``
as defined in plan.md §16.1. Lifecycle status/transition constants follow
plan.md §9.1/§9.2. Entitlement operation classification follows plan.md
§15.2.

All definitions are frozen datastructures to prevent accidental mutation.

Spec ref: specs/010-installments/spec.md, specs/010-installments/plan.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

# ---------------------------------------------------------------------------
# Contract Lifecycle (plan.md §9.1/§9.2)
# ---------------------------------------------------------------------------


class InstallmentContractStatus(str, Enum):
    """``InstallmentContract.status`` lifecycle state (data-model.md
    "InstallmentContract"). **No ``REJECTED`` value** — rejection is an
    audited action (``InstallmentAuditLog.action="REJECTED"``) that
    transitions the contract back to ``DRAFT``, never a persisted status
    of its own (FR-INST-102, ADR-INST-11)."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    DEFAULTED = "DEFAULTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    WRITTEN_OFF = "WRITTEN_OFF"


#: Legal state-machine transitions (plan.md §9.2), enforced by
#: ``InstallmentContractService``'s named business-action methods
#: (``submit()``, ``approve()``, ``reject()``, ``activate()``, ``cancel()``,
#: ``mark_defaulted()``, ``cure()``, ``complete()``, ``writeoff()``) —
#: mirrors ``SalesOrder``'s ``_TRANSITIONS``/``_assert_invoice_transition()``
#: guard idiom. There is deliberately no generic ``set_status()``/
#: ``update_status()`` method anywhere in the public service interface
#: (FR-INST-106) — every mutation goes through a transition asserted
#: against this table.
_LEGAL_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "DRAFT": frozenset(
        {"PENDING_APPROVAL", "APPROVED", "CANCELLED"}
    ),  # APPROVED direct = no approval required (FR-INST-101)
    "PENDING_APPROVAL": frozenset(
        {"APPROVED", "DRAFT", "CANCELLED"}
    ),  # DRAFT = reject() outcome, never REJECTED
    "APPROVED": frozenset({"ACTIVE", "CANCELLED"}),
    "ACTIVE": frozenset({"COMPLETED", "CANCELLED", "DEFAULTED"}),
    "DEFAULTED": frozenset({"ACTIVE", "COMPLETED", "WRITTEN_OFF"}),  # ACTIVE = cure()
    "COMPLETED": frozenset(),  # terminal
    "CANCELLED": frozenset(),  # terminal
    "WRITTEN_OFF": frozenset(),  # terminal
}

# ---------------------------------------------------------------------------
# Entitlement / Operation Classification (plan.md §15.2)
# ---------------------------------------------------------------------------


class InstallmentOperationClass(str, Enum):
    """Operation-sensitivity classification consumed by
    ``InstallmentAccessPolicy.authorize()`` (plan.md §15.2, ADR-INST-06).

    Unlike CRM's blanket router-level ``require_crm_enabled`` gate,
    Installments' spec (§22.3/22.4, FR-INST-353-358) requires
    operation-level granularity: origination is blocked while the module
    is disabled for a tenant, but servicing of already-existing
    obligations and reads must continue (FR-INST-356) so a disabled
    entitlement can never make an existing financial obligation
    impossible to service.
    """

    #: New quote, new contract, activation of a NEW contract, plan/template
    #: CRUD, configuration changes, reschedule, cancel, default, writeoff —
    #: all blocked while disabled (FR-INST-353/357).
    ORIGINATION = "ORIGINATION"
    #: View existing contract/schedule/history, collection, allocation,
    #: reversal/correction, ordinary payoff, early settlement of an
    #: EXISTING contract, statements — permitted even while disabled.
    SERVICING = "SERVICING"
    #: Pure read of existing data — always allowed if entitled, or if the
    #: target contract already exists (servicing-adjacent).
    READ = "READ"
    #: Module enable/disable toggle itself — reachable while disabled
    #: (chicken-and-egg, same as CRM's ``admin_router``).
    ADMIN = "ADMIN"


# ---------------------------------------------------------------------------
# Permission Definitions (plan.md §16.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallmentsPermissionDefinition:
    """Immutable definition of an installments module permission."""

    code: str
    label: str
    module: str
    action: str
    description: str


#: All 16 ``installments.*`` permission codes (plan.md §16.1). Each is
#: independently checked via ``user_has_installments_permission()`` inline
#: at the top of each service method — holding one never implies another
#: (FR-INST-320/321). ``installments.contract.cure`` is deliberately
#: distinct from ``installments.collection.create`` (a cashier who can
#: record collections cannot cure a defaulted contract).
INSTALLMENTS_PERMISSIONS: Final[tuple[InstallmentsPermissionDefinition, ...]] = (
    InstallmentsPermissionDefinition(
        "installments.config.manage",
        "Manage Installments Configuration",
        "installments",
        "manage",
        "Configure tenant-level installment policy",
    ),
    InstallmentsPermissionDefinition(
        "installments.plan.manage",
        "Manage Installment Plan Templates",
        "installments",
        "manage",
        "Create/edit/deactivate installment plan templates",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.view",
        "View Installment Contracts",
        "installments",
        "read",
        "View installment contracts and schedules",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.create",
        "Create Installment Contracts",
        "installments",
        "create",
        "Create a draft installment contract / quote",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.approve",
        "Approve Installment Contracts",
        "installments",
        "manage",
        "Approve a submitted installment contract",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.activate",
        "Activate Installment Contracts",
        "installments",
        "manage",
        "Activate an approved installment contract",
    ),
    InstallmentsPermissionDefinition(
        "installments.collection.create",
        "Record Installment Collections",
        "installments",
        "create",
        "Record an installment collection",
    ),
    InstallmentsPermissionDefinition(
        "installments.collection.reverse",
        "Reverse Installment Collections",
        "installments",
        "manage",
        "Reverse a recorded installment collection",
    ),
    InstallmentsPermissionDefinition(
        "installments.charge.waive",
        "Waive Late Charges",
        "installments",
        "manage",
        "Waive an installment late charge",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.reschedule",
        "Reschedule Installment Contracts",
        "installments",
        "manage",
        "Controlled due-date amendment of an installment schedule",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.cancel",
        "Cancel Installment Contracts",
        "installments",
        "manage",
        "Cancel an installment contract",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.default",
        "Mark Installment Contracts Defaulted",
        "installments",
        "manage",
        "Mark an installment contract as defaulted",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.cure",
        "Cure Defaulted Installment Contracts",
        "installments",
        "manage",
        "Restore a defaulted installment contract to active",
    ),
    InstallmentsPermissionDefinition(
        "installments.contract.writeoff",
        "Write Off Installment Contracts",
        "installments",
        "manage",
        "Write off a defaulted installment balance",
    ),
    InstallmentsPermissionDefinition(
        "installments.settlement.execute",
        "Execute Installment Settlements",
        "installments",
        "manage",
        "Generate/execute an early installment settlement",
    ),
    InstallmentsPermissionDefinition(
        "installments.report.view",
        "View Installment Reports",
        "installments",
        "read",
        "View installment reports/dashboards",
    ),
)

#: All 16 ``installments.*`` permission codes, derived from
#: ``INSTALLMENTS_PERMISSIONS`` (the single source of truth) rather than
#: duplicated as a second literal list — used by the ``/my-permissions``
#: endpoint's ``super_admin`` short-circuit, mirroring
#: ``modules.crm.constants.ALL_CRM_PERMISSION_CODES``'s role.
ALL_INSTALLMENTS_PERMISSION_CODES: Final[frozenset[str]] = frozenset(
    definition.code for definition in INSTALLMENTS_PERMISSIONS
)

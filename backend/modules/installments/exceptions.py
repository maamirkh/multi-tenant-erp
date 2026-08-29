"""Installments module domain exceptions.

Each exception subclasses the appropriate ``core/exceptions/base.py``
class (``NotFoundException``, ``ConflictException``, ``ForbiddenException``,
``ValidationException``) so the global FastAPI exception handler converts
it to a typed ``ErrorResponse`` automatically — zero new exception-handler
registration required, matching the Accounting/CRM/Inventory/Sales/
Purchase convention. Where plan.md mandates a specific machine-readable
``code`` distinct from the base class's default (e.g. ``FEATURE_DISABLED``,
``PERIOD_LOCKED``), it is set explicitly after calling ``super().__init__()``
— the base classes' constructors intentionally do not accept a ``code``
override themselves.

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure
Python.

Spec ref: specs/010-installments/plan.md §22 (Failure/Recovery Design).
"""

from __future__ import annotations

from core.exceptions.base import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)

# ── Not Found (404) ─────────────────────────────────────────────────────────


class InstallmentNotFoundError(NotFoundException):
    """Raised when a referenced Installments entity does not exist for this
    company (BR-INST-015) — identical response whether the entity truly
    doesn't exist or belongs to another tenant (cross-tenant lookups must
    be indistinguishable from non-existence, FR-INST-372)."""

    def __init__(self, entity_type: str, entity_id: str | None = None) -> None:
        super().__init__(
            message=f"{entity_type} '{entity_id}' not found.",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


# ── Forbidden (403) ──────────────────────────────────────────────────────────


class InstallmentSelfApprovalNotAllowedError(ForbiddenException):
    """Raised when a contract's submitter attempts to approve or reject
    their own contract (plan.md §16.2) — applied identically to both
    ``approve()`` and ``reject()`` from day one, explicitly avoiding the
    documented Accounting/Payment history of forgetting the mirror
    action."""

    def __init__(self, contract_id: str | None = None) -> None:
        super().__init__(
            message=(
                f"Installment contract '{contract_id or '?'}' cannot be "
                "approved or rejected by its own submitter."
            ),
            details={"contract_id": contract_id},
        )
        self.code = "SELF_APPROVAL_NOT_ALLOWED"


class InstallmentsNotEntitledError(ForbiddenException):
    """Raised when an ``ORIGINATION``-class operation is attempted while
    the Installments module is disabled for this tenant
    (``InstallmentAccessPolicy.authorize()``, plan.md §15.2, FR-INST-353).
    Servicing/read operations on already-existing contracts are never
    blocked by this (FR-INST-356) — this exception is raised only for the
    ORIGINATION operation class.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message
            or "The Installments module is not enabled for this company.",
            details={"feature_key": "feature.installments.enabled"},
        )
        self.code = "FEATURE_DISABLED"


# ── Conflict (409) ───────────────────────────────────────────────────────────


class InstallmentIllegalTransitionError(ConflictException):
    """Raised when a lifecycle transition is not permitted by
    ``_LEGAL_TRANSITIONS`` (plan.md §9.2) — there is no generic
    ``set_status()``/``update_status()`` method anywhere in the public
    service interface (FR-INST-106); every mutation goes through a named
    business-action method that raises this on an illegal transition."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            message=(
                f"Invalid installment contract status transition: "
                f"{current_status!r} -> {target_status!r}."
            ),
            details={"current_status": current_status, "target_status": target_status},
        )


class InstallmentConcurrentModificationError(ConflictException):
    """Raised when an optimistic-lock conditional update
    (``UPDATE ... WHERE version = :expected``) affects zero rows — a
    concurrent writer already changed the contract (plan.md §19). The
    losing request never silently overwrites (FR-INST-382)."""

    def __init__(self, contract_id: str | None = None) -> None:
        super().__init__(
            message=(
                f"Installment contract '{contract_id or '?'}' was modified "
                "concurrently; reload and retry."
            ),
            details={"contract_id": contract_id},
        )


class InstallmentOutstandingBalanceRemainsError(ConflictException):
    """Raised by ``InstallmentOutstandingService.assert_zero_outstanding()``
    (plan.md §9.3) when a contract cannot transition to ``COMPLETED``
    because an authoritative outstanding obligation remains — either
    unpaid schedule lines (``kind="SCHEDULE"``) or an open, unwaived
    late-charge ``ARTransaction`` (``kind="LATE_CHARGE"``, BR-INST-010).
    The triggering collection/settlement itself still succeeds and
    commits; only the contract-level ``COMPLETED`` transition is
    withheld."""

    def __init__(
        self,
        kind: str,
        contract_id: str | None = None,
        ar_transaction_id: str | None = None,
    ) -> None:
        super().__init__(
            message=(
                f"Installment contract '{contract_id or '?'}' has an "
                f"outstanding {kind.lower()} obligation and cannot be "
                "completed."
            ),
            details={
                "kind": kind,
                "contract_id": contract_id,
                "ar_transaction_id": ar_transaction_id,
            },
        )


class InstallmentOverCollectionError(ConflictException):
    """Raised by ``InstallmentCollectionService.record_collection()``
    when the requested amount exceeds the contract's total live
    outstanding balance (BR-INST-011: total allocated amount can never
    exceed the contractual total). Raised *before* any staging occurs —
    computed from the same live schedule-line outstanding figures
    ``InstallmentAllocationPolicy.allocate_oldest_first()`` itself would
    use, under the same ``FOR UPDATE`` lock that makes Scenario J's
    concurrent-collection guarantee hold."""

    def __init__(
        self,
        amount: str,
        total_outstanding: str,
        contract_id: str | None = None,
    ) -> None:
        super().__init__(
            message=(
                f"Collection amount '{amount}' exceeds installment contract "
                f"'{contract_id or '?'}' total outstanding balance "
                f"'{total_outstanding}'."
            ),
            details={
                "amount": amount,
                "total_outstanding": total_outstanding,
                "contract_id": contract_id,
            },
        )
        self.code = "OVER_COLLECTION"


class InstallmentActivationFailedError(ConflictException):
    """Raised by ``InstallmentContractService.activate()`` when the down
    payment posting or the BR-INST-005 schedule-reconciliation check
    fails — no state change is committed anywhere for either failure
    (plan.md §21's frozen commit-ownership sequence)."""

    def __init__(self, message: str, contract_id: str | None = None) -> None:
        super().__init__(
            message=message,
            details={"contract_id": contract_id},
        )
        self.code = "ACTIVATION_FAILED"


class InstallmentReversalNotAllowedError(ConflictException):
    """Raised by ``InstallmentCollectionService.reverse_collection()``
    when the referenced collection does not belong to this contract, or
    has already been fully reversed."""

    def __init__(self, message: str, collection_id: str | None = None) -> None:
        super().__init__(
            message=message,
            details={"collection_id": collection_id},
        )
        self.code = "REVERSAL_NOT_ALLOWED"


class InstallmentLateChargeAlreadyAppliedError(ConflictException):
    """Raised by ``InstallmentDelinquencyService.apply_late_charge()``
    when a late charge already exists for this exact
    ``(schedule_line_id, overdue_occurrence_date)`` pair (FR-INST-171:
    never applied more than once for the same overdue occurrence). The
    service-layer pre-check; the DB unique constraint (migration 066) is
    the real backstop against a concurrent race."""

    def __init__(self, schedule_line_id: str, overdue_occurrence_date: str) -> None:
        super().__init__(
            message=(
                f"A late charge already exists for schedule line "
                f"'{schedule_line_id}' and occurrence date "
                f"'{overdue_occurrence_date}'."
            ),
            details={
                "schedule_line_id": schedule_line_id,
                "overdue_occurrence_date": overdue_occurrence_date,
            },
        )
        self.code = "LATE_CHARGE_ALREADY_APPLIED"


class InstallmentLateChargePolicyDisabledError(ConflictException):
    """Raised by ``InstallmentDelinquencyService.apply_late_charge()``
    when the contract's frozen terms-snapshot late-charge policy
    (FR-INST-172, captured at activation — independent of later tenant
    configuration changes, BR-INST-009) is absent or not enabled
    (FR-INST-170: a tenant that does not enable late charges MUST see no
    late-charge behavior whatsoever)."""

    def __init__(self, contract_id: str | None = None) -> None:
        super().__init__(
            message=(
                f"Installment contract '{contract_id or '?'}' has no "
                "enabled late-charge policy."
            ),
            details={"contract_id": contract_id},
        )
        self.code = "LATE_CHARGE_POLICY_DISABLED"


class InstallmentLateChargeAlreadyWaivedError(ConflictException):
    """Raised by ``InstallmentDelinquencyService.waive_late_charge()``
    when the referenced late charge has already been waived."""

    def __init__(self, late_charge_id: str | None = None) -> None:
        super().__init__(
            message=f"Late charge '{late_charge_id or '?'}' has already been waived.",
            details={"late_charge_id": late_charge_id},
        )
        self.code = "LATE_CHARGE_ALREADY_WAIVED"


class InstallmentSettlementNotAllowedError(ConflictException):
    """Raised by ``InstallmentSettlementService`` when the contract is not
    in a settleable status (``ACTIVE``/``DEFAULTED`` only, FR-INST-356) or
    has no outstanding balance left to settle."""

    def __init__(self, message: str, contract_id: str | None = None) -> None:
        super().__init__(message=message, details={"contract_id": contract_id})
        self.code = "SETTLEMENT_NOT_ALLOWED"


class InstallmentSettlementQuoteStaleError(ConflictException):
    """Raised by ``InstallmentSettlementService.execute()`` when the
    contract's live outstanding balance no longer matches the amount the
    client quoted (spec §28 edge case) — settlement is only realized by
    an authoritative payment against the *current* balance, never
    against a quote whose underlying contract state has since changed
    (FR-INST-190–192); the caller must generate a new quote."""

    def __init__(
        self,
        quoted_amount: str,
        current_amount: str,
        contract_id: str | None = None,
    ) -> None:
        super().__init__(
            message=(
                f"Settlement quote for installment contract '{contract_id or '?'}' "
                f"is stale: quoted amount '{quoted_amount}' no longer matches the "
                f"current outstanding balance '{current_amount}'. Generate a new "
                "settlement quote."
            ),
            details={
                "quoted_amount": quoted_amount,
                "current_amount": current_amount,
                "contract_id": contract_id,
            },
        )
        self.code = "SETTLEMENT_QUOTE_STALE"


class InstallmentIdempotencyConflictError(ConflictException):
    """Raised by ``InstallmentIdempotencyService`` (plan.md §20.2/§20.3)
    when a duplicate request cannot be resolved as a clean replay.
    ``code`` defaults to ``IDEMPOTENCY_PAYLOAD_MISMATCH`` (the normal
    outcome: same key, different request payload); pass
    ``code="IDEMPOTENCY_UNEXPECTED_STATE"`` only for the purely defensive
    branch of observing another session's still-``IN_PROGRESS`` row,
    which is not a documented, expected response under normal
    operation."""

    def __init__(
        self,
        message: str = "Idempotency key reused with a different request payload.",
        code: str = "IDEMPOTENCY_PAYLOAD_MISMATCH",
        idempotency_key: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            details={"idempotency_key": idempotency_key},
        )
        self.code = code


# ── Validation (422) ─────────────────────────────────────────────────────────


class InstallmentFiscalPeriodLockedError(ValidationException):
    """Raised when a ``PostingValidationError`` from Accounting indicates
    the target fiscal period is locked/closed (plan.md §22) — mapped to a
    specific, documented ``PERIOD_LOCKED`` code rather than a generic
    validation error."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message or "The target fiscal period is locked.",
        )
        self.code = "PERIOD_LOCKED"


class DegenerateScheduleError(ValidationException):
    """Raised by ``ScheduleEngine.generate()`` when the final installment
    line would be zero or negative (spec §28 edge case) — raised before
    any persistence; activation never partially proceeds."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message
            or "The generated schedule's final installment would be zero "
            "or negative.",
        )
        self.code = "DEGENERATE_SCHEDULE"


class InstallmentTermsPolicyViolationError(ValidationException):
    """Raised by ``InstallmentTermsPolicyValidator.validate()`` (plan.md
    §10.6) when proposed installment terms fall outside the tenant's
    configured ``InstallmentConfiguration`` policy bounds (FR-INST-011).
    ``details["violations"]`` names every violated field, not just the
    first one encountered."""

    def __init__(self, violations: dict[str, str]) -> None:
        super().__init__(
            message="Proposed installment terms violate configured policy bounds.",
            details={"violations": violations},
        )
        self.code = "TERMS_POLICY_VIOLATION"

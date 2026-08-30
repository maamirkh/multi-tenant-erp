"""InstallmentSettlementService — early settlement quote/execution
(tasks.md T154/T155, plan.md §15.1/§12.3.1's Early Settlement row).

``generate_quote()`` is a pure read+calculation, built on the exact same
``InstallmentOutstandingService.compute_outstanding_breakdown()`` (T108's
Phase 9 extension) that ``complete()``'s own authoritative completion
guard uses — no second, competing "what does this contract still owe"
computation exists anywhere in the module (FR-INST-191's reproducibility
requirement follows directly from this: the same live contract state
always yields the same breakdown, since nothing here depends on
``as_of_date`` beyond echoing it back). It performs zero Accounting
calls and zero contract/schedule mutation (FR-INST-192) — the only
side effect is its own required audit row (FR-INST-341: "settlement
quote generation" is auditable even though non-mutating).

``execute()`` reuses ``InstallmentCollectionService``'s exact atomic
collection sequence (T121, refactored into ``execute_collection_sequence()`` for
this purpose) at the contract's full current outstanding amount —
reserving its own idempotency key (``operation="settlement.execute"``,
distinct from ``collection.create``) rather than a second, separate
reservation for the wrapped collection step: the whole sequence,
including the wrapped Accounting finalize call, is one atomic unit
guarded by the single settlement reservation (plan.md §21's "exactly one
``db.commit()``" invariant — no hidden second commit is introduced here).

Spec ref: specs/010-installments/plan.md §9.3, §12.3.1 Early Settlement
row; specs/010-installments/spec.md §15.1 (FR-INST-190–192).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from modules.installments.exceptions import (
    InstallmentNotFoundError,
    InstallmentSettlementNotAllowedError,
    InstallmentSettlementQuoteStaleError,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.collection_service import (
    InstallmentCollectionService,
)
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from modules.installments.services.outstanding_service import (
    InstallmentOutstandingService,
)

#: Contracts eligible for early settlement — mirrors
#: ``InstallmentCollectionService``'s own ``_REVERSIBLE_STATUSES``
#: exactly (FR-INST-356: settlement remains available against an
#: existing, already-active or defaulted-but-serviceable contract).
_SETTLEABLE_STATUSES = ("ACTIVE", "DEFAULTED")


@dataclass(frozen=True)
class InstallmentSettlementQuote:
    """FR-INST-190's full settlement-quote payload — never persisted as
    its own row (no ``InstallmentSettlementQuote`` table exists in the
    approved data model); reproducible from live contract state alone
    (FR-INST-191)."""

    contract_id: UUID
    as_of_date: date
    schedule_outstanding: Decimal
    late_charge_outstanding: Decimal
    settlement_amount: Decimal
    currency_code: str
    early_settlement_policy: dict[str, Any] | None


class InstallmentSettlementService:
    """Service layer for early-settlement quote generation and execution."""

    def __init__(
        self,
        db: Any,
        contract_repo: InstallmentContractRepository,
        outstanding_service: InstallmentOutstandingService,
        collection_service: InstallmentCollectionService,
        configuration_service: InstallmentConfigurationService,
        idempotency_service: InstallmentIdempotencyService,
        audit_service: InstallmentAuditService,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self.db = db
        self._contracts = contract_repo
        self._outstanding = outstanding_service
        self._collections = collection_service
        self._configuration = configuration_service
        self._access_policy = access_policy
        self._idempotency = idempotency_service
        self._audit = audit_service

    def _get_settleable_contract(
        self, company_id: UUID, contract_id: UUID
    ) -> InstallmentContract:
        contract = self._contracts.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        if contract.status not in _SETTLEABLE_STATUSES:
            raise InstallmentSettlementNotAllowedError(
                f"Installment contract '{contract_id}' is {contract.status!r}; "
                "early settlement is only available for ACTIVE or DEFAULTED "
                "contracts.",
                str(contract_id),
            )
        return contract

    def generate_quote(
        self,
        company_id: UUID,
        contract_id: UUID,
        as_of_date: date,
        actor_id: UUID | None = None,
    ) -> InstallmentSettlementQuote:
        """Generate a reproducible, non-mutating early-settlement quote
        (FR-INST-190/191) — no Accounting call, no financial posting, no
        contract/schedule state change (FR-INST-192). Still audited
        (FR-INST-341): the only durable side effect is the audit row
        itself.

        Raises:
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentSettlementNotAllowedError: contract is not
                ``ACTIVE``/``DEFAULTED``.
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.SERVICING
            )
        contract = self._get_settleable_contract(company_id, contract_id)

        breakdown = self._outstanding.compute_outstanding_breakdown(
            company_id, contract_id
        )
        config = self._configuration.get_effective_config(
            company_id, contract.branch_id
        )

        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="SETTLEMENT_QUOTED",
            actor_id=actor_id,
            after={
                "as_of_date": as_of_date.isoformat(),
                "settlement_amount": str(breakdown.total_outstanding),
            },
        )
        self.db.commit()

        return InstallmentSettlementQuote(
            contract_id=contract.id,
            as_of_date=as_of_date,
            schedule_outstanding=breakdown.schedule_outstanding,
            late_charge_outstanding=breakdown.late_charge_outstanding,
            settlement_amount=breakdown.total_outstanding,
            currency_code=contract.currency_code,
            early_settlement_policy=(
                config.early_settlement_policy if config is not None else None
            ),
        )

    def execute(
        self,
        company_id: UUID,
        contract_id: UUID,
        quoted_amount: Decimal,
        quoted_as_of_date: date,
        idempotency_key: str,
        actor_id: UUID | None,
        *,
        payment_method: str = "BANK_TRANSFER",
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
    ) -> InstallmentContract:
        """Execute an early settlement at the contract's full current
        outstanding amount — the authoritative settlement payment,
        allocation, and (where reached) contract completion all happen
        here, atomically, via the same sequence
        ``InstallmentCollectionService.record_collection()`` uses (T121).

        ``quoted_amount``/``quoted_as_of_date`` must match what
        ``generate_quote()`` would compute *right now*; a mismatch means
        the contract's state changed since the quote was generated (a
        collection, late charge, or waiver posted in between) and the
        quote is stale (spec §28 edge case) — the caller must fetch a
        fresh quote and retry, never silently settle for a different
        amount than the one the user actually saw and confirmed.

        Raises:
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentSettlementNotAllowedError: contract is not
                ``ACTIVE``/``DEFAULTED``, or has nothing left to settle.
            InstallmentSettlementQuoteStaleError: the live outstanding
                balance no longer matches ``quoted_amount`` (409).
            InstallmentIdempotencyConflictError: same key, different
                request (409).
            InstallmentFiscalPeriodLockedError: locked fiscal period (422).
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.SERVICING
            )
        fingerprint = hashlib.sha256(
            f"settlement.execute:{contract_id}:{quoted_amount}:"
            f"{quoted_as_of_date}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "settlement.execute",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return self._get_or_404(company_id, contract_id)

        # FOR UPDATE — taken here (not merely inside the reused collection
        # sequence) so the freshness check below and the amount actually
        # collected are read from the same locked, race-free snapshot.
        contract = self._contracts.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        if contract.status not in _SETTLEABLE_STATUSES:
            raise InstallmentSettlementNotAllowedError(
                f"Installment contract '{contract_id}' is {contract.status!r}; "
                "early settlement is only available for ACTIVE or DEFAULTED "
                "contracts.",
                str(contract_id),
            )

        breakdown = self._outstanding.compute_outstanding_breakdown(
            company_id, contract_id
        )
        current_amount = breakdown.total_outstanding
        if current_amount != quoted_amount:
            raise InstallmentSettlementQuoteStaleError(
                str(quoted_amount), str(current_amount), str(contract_id)
            )
        if current_amount <= 0:
            raise InstallmentSettlementNotAllowedError(
                f"Installment contract '{contract_id}' has no outstanding "
                "balance to settle.",
                str(contract_id),
            )

        self._collections.execute_collection_sequence(
            company_id,
            contract_id,
            current_amount,
            payment_method,
            actor_id,
            reservation=reservation,
            audit_action="SETTLED",
            outbox_event_type="installment.settled",
            pending_approval_audit_action="SETTLEMENT_PENDING_APPROVAL",
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
        )

        return self._get_or_404(company_id, contract_id)

    def _get_or_404(self, company_id: UUID, contract_id: UUID) -> InstallmentContract:
        contract = self._contracts.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

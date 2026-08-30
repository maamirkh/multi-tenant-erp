"""InstallmentReschedulingService — controlled due-date-only amendment
(tasks.md T168, plan.md §10.4 versioning integration, spec FR-INST-201/
202).

Creates a new, immutable ``InstallmentScheduleVersion`` covering only
the contract's currently-*remaining* (unpaid) obligation — the prior
version and its lines are never mutated, only superseded (BR-INST-017):
every ``InstallmentAllocationReference`` row already pointing at the
prior version's lines remains a valid, permanent pointer into history.

Restructuring guard (FR-INST-202): a caller-supplied ``principal_amount``/
``markup_amount``/``installment_count`` that disagrees with the
contract's own recorded values is rejected outright — only
``first_due_date``/``frequency`` (i.e. *when* the remaining obligation
is due, never *how much* is owed) may differ from the current contract.

Maker-checker (FR-INST-201, plan.md §16.2): "the same discipline as
contract approval" — ``requested_by`` (who asked for this reschedule)
must differ from ``actor_id`` (who is executing/approving it).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from core.events.outbox import EventOutboxRepository, OutboxRecord
from core.exceptions.base import ValidationException
from modules.installments.exceptions import (
    InstallmentNotFoundError,
    InstallmentRescheduleNotAllowedError,
    InstallmentRescheduleRestructuringNotAllowedError,
    InstallmentRescheduleSelfApprovalNotAllowedError,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
)
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from modules.installments.services.schedule_engine import ScheduleEngine

_DEFAULT_ROUNDING_POLICY = "ROUND_HALF_UP"


@dataclass(frozen=True)
class RescheduleTerms:
    """Caller-supplied new terms for ``reschedule()``. Only
    ``first_due_date``/``frequency`` may actually differ from the
    contract's current values — ``principal_amount``/``markup_amount``/
    ``installment_count`` are accepted solely so a caller's attempt to
    change them can be explicitly detected and rejected (FR-INST-202),
    not because they are ever applied."""

    first_due_date: date
    frequency: str | None = None
    principal_amount: Decimal | None = None
    markup_amount: Decimal | None = None
    installment_count: int | None = None


class InstallmentReschedulingService:
    """Service layer for controlled due-date rescheduling."""

    def __init__(
        self,
        db: Any,
        contract_repo: InstallmentContractRepository,
        schedule_repo: InstallmentScheduleRepository,
        allocation_ref_repo: InstallmentAllocationReferenceRepository,
        configuration_service: InstallmentConfigurationService,
        idempotency_service: InstallmentIdempotencyService,
        audit_service: InstallmentAuditService,
        outbox_repo: EventOutboxRepository,
    ) -> None:
        self.db = db
        self._contracts = contract_repo
        self._schedule = schedule_repo
        self._allocation_refs = allocation_ref_repo
        self._configuration = configuration_service
        self._idempotency = idempotency_service
        self._audit = audit_service
        self._outbox = outbox_repo

    def _assert_no_restructuring(
        self, contract: InstallmentContract, new_terms: RescheduleTerms
    ) -> None:
        violations: dict[str, str] = {}
        if (
            new_terms.principal_amount is not None
            and new_terms.principal_amount != contract.principal_amount
        ):
            violations["principal_amount"] = (
                f"requested {new_terms.principal_amount}, contract has "
                f"{contract.principal_amount}"
            )
        if (
            new_terms.markup_amount is not None
            and new_terms.markup_amount != contract.markup_amount
        ):
            violations["markup_amount"] = (
                f"requested {new_terms.markup_amount}, contract has "
                f"{contract.markup_amount}"
            )
        if (
            new_terms.installment_count is not None
            and new_terms.installment_count != contract.installment_count
        ):
            violations["installment_count"] = (
                f"requested {new_terms.installment_count}, contract has "
                f"{contract.installment_count}"
            )
        if violations:
            raise InstallmentRescheduleRestructuringNotAllowedError(violations)

    def reschedule(
        self,
        company_id: UUID,
        contract_id: UUID,
        new_terms: RescheduleTerms,
        reason: str,
        idempotency_key: str,
        actor_id: UUID | None,
        *,
        requested_by: UUID | None,
    ) -> InstallmentContract:
        """Regenerate the schedule for the contract's remaining (unpaid)
        obligation only, over new due dates — the contractual total,
        principal, markup, and already-satisfied history are all
        unchanged (FR-INST-202); the prior schedule version is
        superseded, never mutated (BR-INST-017).

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentRescheduleNotAllowedError: ``contract.status`` is
                not ``ACTIVE``.
            InstallmentRescheduleSelfApprovalNotAllowedError:
                ``requested_by == actor_id`` (409/403).
            InstallmentRescheduleRestructuringNotAllowedError:
                ``new_terms`` attempts to change principal/markup/count
                (422).
            InstallmentIdempotencyConflictError: same key, different
                request (409).
        """
        if not reason or not reason.strip():
            raise ValidationException(
                message="A reason is required to reschedule an installment " "contract."
            )

        fingerprint = hashlib.sha256(
            f"contract.reschedule:{contract_id}:{new_terms.first_due_date}:"
            f"{new_terms.frequency}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "contract.reschedule",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return self._get_or_404(company_id, contract_id)

        contract = self._contracts.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        if contract.status != "ACTIVE":
            raise InstallmentRescheduleNotAllowedError(
                contract.status, str(contract_id)
            )

        if (
            requested_by is not None
            and actor_id is not None
            and requested_by == actor_id
        ):
            raise InstallmentRescheduleSelfApprovalNotAllowedError(str(contract_id))

        self._assert_no_restructuring(contract, new_terms)

        current_version = self._schedule.get_active_version(company_id, contract_id)
        if current_version is None:
            raise InstallmentNotFoundError(
                "InstallmentScheduleVersion", str(contract_id)
            )
        current_lines = self._schedule.get_lines(company_id, current_version.id)
        active_lines = [
            line
            for line in current_lines
            if line.waived_at is None and line.voided_at is None
        ]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, [line.id for line in active_lines]
        )
        remaining_lines = [
            line
            for line in active_lines
            if (line.scheduled_amount - net_allocated.get(line.id, Decimal("0"))) > 0
        ]
        remaining_outstanding = sum(
            (
                line.scheduled_amount - net_allocated.get(line.id, Decimal("0"))
                for line in remaining_lines
            ),
            Decimal("0"),
        )
        if not remaining_lines:
            raise InstallmentRescheduleNotAllowedError(
                contract.status, str(contract_id)
            )

        config = self._configuration.get_effective_config(
            company_id, contract.branch_id
        )
        rounding_policy = (
            config.rounding_policy if config is not None else _DEFAULT_ROUNDING_POLICY
        )
        effective_frequency = new_terms.frequency or contract.frequency

        schedule_result = ScheduleEngine.generate(
            principal=remaining_outstanding,
            down_payment=Decimal("0"),
            markup=Decimal("0"),
            installment_count=len(remaining_lines),
            frequency=effective_frequency,
            first_due_date=new_terms.first_due_date,
            rounding_policy=rounding_policy,
        )

        new_version = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract_id,
            version_number=current_version.version_number + 1,
            status="ACTIVE",
            generated_by=actor_id,
            reason=reason,
        )
        new_lines = [
            InstallmentScheduleLine(
                company_id=company_id,
                sequence=line.sequence,
                due_date=line.due_date,
                scheduled_amount=line.scheduled_amount,
            )
            for line in schedule_result.lines
        ]
        self._schedule.create_version_with_lines(new_version, new_lines)

        # Supersede the prior version — a lifecycle/administrative field
        # change, not a rewrite of its contractual content (its lines are
        # never touched); direct attribute mutation on the already-loaded
        # ORM instance, exactly how contract_service.py's complete()/
        # activate() mutate contract.status, since no update method
        # exists on InstallmentScheduleRepository by design (T072).
        current_version.status = "SUPERSEDED"
        self.db.add(current_version)
        self.db.flush()

        before_status = contract.status
        contract.active_schedule_version_id = new_version.id
        contract.version = contract.version + 1
        self.db.add(contract)
        self.db.flush()

        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="RESCHEDULED",
            actor_id=actor_id,
            before={
                "status": before_status,
                "schedule_version": current_version.version_number,
            },
            after={
                "status": contract.status,
                "schedule_version": new_version.version_number,
            },
            reason=reason,
        )
        self._outbox.create(
            OutboxRecord(
                event_type="installment.contract.rescheduled",
                aggregate_id=str(contract.id),
                aggregate_type="InstallmentContract",
                payload={
                    "contract_id": str(contract.id),
                    "company_id": str(company_id),
                    "new_schedule_version": new_version.version_number,
                },
            )
        )
        self._idempotency.complete(
            reservation.reservation_id,
            {
                "contract_id": str(contract.id),
                "schedule_version": new_version.version_number,
            },
        )

        self.db.commit()
        return self._get_or_404(company_id, contract_id)

    def _get_or_404(self, company_id: UUID, contract_id: UUID) -> InstallmentContract:
        contract = self._contracts.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

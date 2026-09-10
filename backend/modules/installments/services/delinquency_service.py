"""InstallmentDelinquencyService — late-charge application and waiver
(tasks.md T142/T143).

Both public methods follow the same staging-order discipline as
``InstallmentCollectionService`` (plan.md §12.2, §21):

    FOR UPDATE lock on InstallmentContract (shared with collection/
    settlement/write-off — this is what makes the collection-vs-late-
    charge race serialize, Concurrency Test D, plan.md §31)
    -> policy/eligibility checks
    -> Accounting staged mutation via AccountingIntegrationGateway
    -> Installments rows (InstallmentLateCharge, audit, outbox) staged
       into the SAME session
    -> Accounting finalize call LAST (the actual commit)

Neither method takes an ``idempotency_key`` — late-charge apply/waive are
not in the idempotency-protected high-risk-command list (plan.md §20);
FR-INST-171's "never applied more than once for the same overdue
occurrence" is enforced instead by the
``(schedule_line_id, overdue_occurrence_date)`` uniqueness check (service
pre-check + DB constraint backstop, migration 066).

Spec ref: specs/010-installments/plan.md §12.1/§12.2, §14.1;
specs/010-installments/data-model.md "InstallmentLateCharge".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from core.events.outbox import EventOutboxRepository, OutboxRecord
from core.exceptions.base import ValidationException
from core.utils.datetime import utcnow
from modules.accounting.exceptions import PostingValidationError
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentFiscalPeriodLockedError,
    InstallmentLateChargeAlreadyAppliedError,
    InstallmentLateChargeAlreadyWaivedError,
    InstallmentLateChargePolicyDisabledError,
    InstallmentNotFoundError,
)
from modules.installments.models.late_charge import InstallmentLateCharge
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.business_date import get_business_date

_SERVICEABLE_STATUSES = ("ACTIVE", "DEFAULTED")


def _raise_for_posting_error(exc: PostingValidationError, contract_id: UUID) -> None:
    if "period" in str(exc).lower() and "lock" in str(exc).lower():
        raise InstallmentFiscalPeriodLockedError(str(exc)) from exc
    raise InstallmentActivationFailedError(str(exc), str(contract_id)) from exc


class InstallmentDelinquencyService:
    """Service layer for late-charge application and waiver."""

    def __init__(
        self,
        db: Any,
        contract_repo: InstallmentContractRepository,
        schedule_repo: InstallmentScheduleRepository,
        allocation_ref_repo: InstallmentAllocationReferenceRepository,
        late_charge_repo: InstallmentLateChargeRepository,
        accounting_gateway: AccountingIntegrationGateway,
        audit_service: InstallmentAuditService,
        outbox_repo: EventOutboxRepository,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self.db = db
        self._contracts = contract_repo
        self._schedule = schedule_repo
        self._allocation_refs = allocation_ref_repo
        self._late_charges = late_charge_repo
        self._accounting = accounting_gateway
        self._audit = audit_service
        self._outbox = outbox_repo
        self._access_policy = access_policy

    def apply_late_charge(
        self,
        company_id: UUID,
        contract_id: UUID,
        schedule_line_id: UUID,
        actor_id: UUID | None,
    ) -> InstallmentLateCharge:
        """Post a policy-driven late charge against ``schedule_line_id``
        (FR-INST-171) — a real, collectible ``DEBIT_NOTE`` AR obligation
        (plan.md §12.1), never a GL-only fee.

        Raises:
            InstallmentNotFoundError: contract or schedule line not found
                for this tenant, or the line does not belong to
                ``contract_id``.
            InstallmentLateChargePolicyDisabledError: the contract's
                frozen terms-snapshot late-charge policy (FR-INST-172) is
                absent or not enabled (FR-INST-170).
            InstallmentLateChargeAlreadyAppliedError: already charged for
                this exact occurrence (FR-INST-171).
            InstallmentFiscalPeriodLockedError: locked fiscal period.
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.SERVICING
            )
        contract = self._contracts.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        if contract.status not in _SERVICEABLE_STATUSES:
            raise InstallmentActivationFailedError(
                f"Installment contract '{contract_id}' is {contract.status!r}; "
                "late charges may only be applied to ACTIVE or DEFAULTED "
                "contracts.",
                str(contract_id),
            )

        line = self._schedule.get_line_by_id(company_id, schedule_line_id)
        if (
            line is None
            or line.schedule_version_id != contract.active_schedule_version_id
        ):
            raise InstallmentNotFoundError(
                "InstallmentScheduleLine", str(schedule_line_id)
            )
        if line.waived_at is not None or line.voided_at is not None:
            raise InstallmentNotFoundError(
                "InstallmentScheduleLine", str(schedule_line_id)
            )

        policy = (contract.terms_snapshot or {}).get("late_charge_policy")
        if not policy or not policy.get("enabled"):
            raise InstallmentLateChargePolicyDisabledError(str(contract_id))

        occurrence_date = line.due_date
        existing = self._late_charges.get_by_line_and_occurrence(
            company_id, schedule_line_id, occurrence_date
        )
        if existing is not None:
            raise InstallmentLateChargeAlreadyAppliedError(
                str(schedule_line_id), occurrence_date.isoformat()
            )

        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, [schedule_line_id]
        ).get(schedule_line_id, Decimal("0"))
        line_outstanding = line.scheduled_amount - net_allocated

        charge_type = policy.get("charge_type", "FIXED")
        if charge_type == "PERCENTAGE":
            amount = line_outstanding * Decimal(str(policy["amount"])) / Decimal("100")
        else:
            amount = Decimal(str(policy["amount"]))
        cap_amount = policy.get("cap_amount")
        if cap_amount is not None:
            amount = min(amount, Decimal(str(cap_amount)))

        late_charge = InstallmentLateCharge(
            id=uuid4(),
            company_id=company_id,
            created_by=actor_id,
            contract_id=contract_id,
            schedule_line_id=schedule_line_id,
            charge_amount=amount,
            overdue_occurrence_date=occurrence_date,
        )

        def _stage_installments_rows(staged: Any) -> None:
            late_charge.accounting_journal_entry_id = staged.journal_entry.id
            late_charge.accounting_ar_transaction_id = staged.ar_transaction.id
            self._late_charges.create(late_charge)
            self._audit.record(
                company_id,
                "InstallmentLateCharge",
                late_charge.id,
                action="LATE_CHARGE_APPLIED",
                actor_id=actor_id,
                after={
                    "contract_id": str(contract_id),
                    "schedule_line_id": str(schedule_line_id),
                    "charge_amount": str(amount),
                    "overdue_occurrence_date": occurrence_date.isoformat(),
                },
            )
            self._outbox.create(
                OutboxRecord(
                    event_type="installment.late_charge_applied",
                    aggregate_id=str(contract_id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract_id),
                        "company_id": str(company_id),
                        "late_charge_id": str(late_charge.id),
                        "charge_amount": str(amount),
                    },
                )
            )

        try:
            self._accounting.post_late_charge(
                company_id=company_id,
                customer_id=contract.customer_id,
                amount=amount,
                contra_account_id=UUID(str(policy["contra_account_id"])),
                reason=f"Late charge for installment due {occurrence_date.isoformat()}",
                posting_date=get_business_date(),
                source_document_id=late_charge.id,
                actor_id=actor_id,
                stage_installments_rows=_stage_installments_rows,
            )
        except PostingValidationError as exc:
            self.db.rollback()
            _raise_for_posting_error(exc, contract_id)

        return late_charge

    def waive_late_charge(
        self,
        company_id: UUID,
        contract_id: UUID,
        late_charge_id: UUID,
        reason: str,
        actor_id: UUID | None,
    ) -> InstallmentLateCharge:
        """Waive a previously-posted late charge (FR-INST-173) — reverses
        the AR/GL effect via ``AccountsReceivableService.reverse_adjustment()``
        (plan.md §12.1 "Waiver" row); the original charge row is never
        deleted, only marked waived (BR-INST-017's reversal-preserves-
        history discipline applied identically here).

        Raises:
            InstallmentNotFoundError: contract or late charge not found
                for this tenant, or the charge does not belong to
                ``contract_id``.
            InstallmentLateChargeAlreadyWaivedError: already waived.
            ValidationException: ``reason`` is empty.
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.SERVICING
            )
        if not reason or not reason.strip():
            raise ValidationException(message="A waiver reason is required.")

        contract = self._contracts.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))

        late_charge = self._late_charges.get_by_id_or_none(company_id, late_charge_id)
        if late_charge is None or late_charge.contract_id != contract_id:
            raise InstallmentNotFoundError("InstallmentLateCharge", str(late_charge_id))
        if late_charge.waived_at is not None:
            raise InstallmentLateChargeAlreadyWaivedError(str(late_charge_id))

        waived_at = utcnow()

        def _stage_waiver_rows() -> None:
            self._late_charges.mark_waived(late_charge, waived_at, actor_id, reason)
            self._audit.record(
                company_id,
                "InstallmentLateCharge",
                late_charge.id,
                action="LATE_CHARGE_WAIVED",
                actor_id=actor_id,
                reason=reason,
                after={"contract_id": str(contract_id)},
            )
            self._outbox.create(
                OutboxRecord(
                    event_type="installment.late_charge_waived",
                    aggregate_id=str(contract_id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract_id),
                        "company_id": str(company_id),
                        "late_charge_id": str(late_charge.id),
                    },
                )
            )

        # accounting_ar_transaction_id/accounting_journal_entry_id are set
        # together, atomically, by apply_late_charge() (model docstring) —
        # the only write site. A committed InstallmentLateCharge row is
        # therefore expected to always carry one; None here would mean the
        # atomic staging invariant was violated, not a normal business state.
        assert late_charge.accounting_ar_transaction_id is not None, (
            f"InstallmentLateCharge {late_charge.id} is missing "
            "accounting_ar_transaction_id despite being committed"
        )
        self._accounting.reverse_late_charge(
            company_id=company_id,
            ar_transaction_id=late_charge.accounting_ar_transaction_id,
            reason=reason,
            actor_id=actor_id,
            stage_installments_rows=_stage_waiver_rows,
        )

        return late_charge

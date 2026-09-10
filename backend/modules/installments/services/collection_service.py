"""InstallmentCollectionService — collection recording and reversal
(tasks.md T121/T123, plan.md §21's Collection/Reversal rows).

Both public methods follow the identical shape every idempotency-
protected, money-mutating Installments command uses (plan.md §21):

    idempotency reservation (first statement, before any business write)
    -> FOR UPDATE lock on InstallmentContract
    -> business computation
    -> Accounting staged mutation via AccountingIntegrationGateway
    -> Installments rows staged into the SAME session
    -> Accounting finalize call LAST (the actual commit)

Spec ref: specs/010-installments/plan.md §12.3.1/§12.3.2/§21;
specs/010-installments/data-model.md "InstallmentAllocationReference".
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from core.events.outbox import EventOutboxRepository, OutboxRecord
from modules.accounting.exceptions import PostingValidationError
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentFiscalPeriodLockedError,
    InstallmentNotFoundError,
    InstallmentOutstandingBalanceRemainsError,
    InstallmentOverCollectionError,
    InstallmentReversalNotAllowedError,
)
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
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
from modules.installments.services.allocation_policy import (
    InstallmentAllocationPolicy,
    OutstandingLine,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
    ReservationResult,
)
from modules.installments.services.outstanding_service import (
    InstallmentOutstandingService,
)

_REVERSIBLE_STATUSES = ("ACTIVE", "DEFAULTED")


def _raise_for_posting_error(exc: PostingValidationError, contract_id: UUID) -> None:
    if "period" in str(exc).lower() and "lock" in str(exc).lower():
        raise InstallmentFiscalPeriodLockedError(str(exc)) from exc
    raise InstallmentActivationFailedError(str(exc), str(contract_id)) from exc


class InstallmentCollectionService:
    """Service layer for recording and reversing installment collections."""

    def __init__(
        self,
        db: Any,
        contract_repo: InstallmentContractRepository,
        schedule_repo: InstallmentScheduleRepository,
        allocation_ref_repo: InstallmentAllocationReferenceRepository,
        accounting_gateway: AccountingIntegrationGateway,
        outstanding_service: InstallmentOutstandingService,
        idempotency_service: InstallmentIdempotencyService,
        audit_service: InstallmentAuditService,
        outbox_repo: EventOutboxRepository,
        contract_service: InstallmentContractService,
        late_charge_repo: InstallmentLateChargeRepository | None = None,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self.db = db
        self._contracts = contract_repo
        self._schedule = schedule_repo
        self._allocation_refs = allocation_ref_repo
        self._accounting = accounting_gateway
        self._outstanding = outstanding_service
        self._idempotency = idempotency_service
        self._audit = audit_service
        self._outbox = outbox_repo
        self._contract_service = contract_service
        self._late_charges = late_charge_repo
        self._access_policy = access_policy

    def _outstanding_lines(
        self, company_id: UUID, contract_id: UUID
    ) -> list[OutstandingLine]:
        version = self._schedule.get_active_version(company_id, contract_id)
        outstanding: list[OutstandingLine] = []
        if version is not None:
            lines = self._schedule.get_lines(company_id, version.id)
            active_lines = [
                line
                for line in lines
                if line.waived_at is None and line.voided_at is None
            ]
            net_allocated = self._allocation_refs.get_net_allocated_by_line(
                company_id, [line.id for line in active_lines]
            )
            outstanding.extend(
                OutstandingLine(
                    schedule_line_id=line.id,
                    due_date=line.due_date,
                    outstanding_amount=line.scheduled_amount
                    - net_allocated.get(line.id, Decimal("0")),
                )
                for line in active_lines
            )

        # Open late-charge AR (Phase 8) is an ordinary, independently-
        # allocatable obligation, collectible via this same oldest-first
        # policy with no special-case branch (plan.md §11.3) — each
        # charge's own DEBIT_NOTE ARTransaction id is carried through so
        # the resulting allocation targets it directly, not the
        # originating invoice's transaction.
        if self._late_charges is not None:
            for charge in self._late_charges.list_for_contract(company_id, contract_id):
                if (
                    charge.waived_at is not None
                    or charge.accounting_ar_transaction_id is None
                ):
                    continue
                ar_transaction = self._accounting.get_ar_transaction(
                    company_id, charge.accounting_ar_transaction_id
                )
                if ar_transaction is None or ar_transaction.status == "WRITTEN_OFF":
                    continue
                outstanding.append(
                    OutstandingLine(
                        schedule_line_id=charge.schedule_line_id,
                        due_date=charge.overdue_occurrence_date,
                        outstanding_amount=ar_transaction.outstanding_amount,
                        ar_transaction_id=charge.accounting_ar_transaction_id,
                    )
                )

        return [line for line in outstanding if line.outstanding_amount > 0]

    def record_collection(
        self,
        company_id: UUID,
        contract_id: UUID,
        amount: Decimal,
        payment_method: str,
        idempotency_key: str,
        actor_id: UUID | None,
        *,
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Record a collection (exact/partial/multi-installment/advance,
        FR-INST-130) against ``contract_id``, allocated oldest-due-first
        (FR-INST-140). Auto-completes the contract at zero outstanding
        (FR-INST-104).

        Raises:
            InstallmentNotFoundError: contract or active schedule not
                found for this tenant.
            InstallmentOverCollectionError: ``amount`` exceeds the
                contract's total live outstanding balance (BR-INST-011).
            InstallmentIdempotencyConflictError: same key, different
                request (409).
            InstallmentFiscalPeriodLockedError: locked fiscal period (422).
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.SERVICING
            )
        fingerprint = hashlib.sha256(
            f"collection.create:{contract_id}:{amount}:{payment_method}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "collection.create",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return reservation.result_payload or {}

        return self.execute_collection_sequence(
            company_id,
            contract_id,
            amount,
            payment_method,
            actor_id,
            reservation=reservation,
            audit_action="COLLECTED",
            outbox_event_type="installment.collected",
            pending_approval_audit_action="COLLECTION_PENDING_APPROVAL",
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
        )

    def execute_collection_sequence(
        self,
        company_id: UUID,
        contract_id: UUID,
        amount: Decimal,
        payment_method: str,
        actor_id: UUID | None,
        *,
        reservation: ReservationResult,
        audit_action: str,
        outbox_event_type: str,
        pending_approval_audit_action: str = "COLLECTION_PENDING_APPROVAL",
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
    ) -> dict[str, Any]:
        """The atomic collection sequence shared by ``record_collection()``
        (``audit_action="COLLECTED"``) and, since Phase 9,
        ``InstallmentSettlementService.execute()``
        (``audit_action="SETTLED"``) — FOR UPDATE lock -> outstanding
        calculation -> oldest-first allocation -> Accounting staged
        write -> Installments rows staged -> completion guard -> Accounting
        finalize LAST. The caller has already reserved its own
        idempotency key (``reservation``) before calling this — this
        method only *completes* that reservation, in the same commit as
        everything else, never reserves one of its own (plan.md §21;
        tasks.md T155's "reuses the exact atomic sequence" requirement).
        """
        contract = self._contracts.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        if contract.status not in _REVERSIBLE_STATUSES:
            raise InstallmentActivationFailedError(
                f"Installment contract '{contract_id}' is {contract.status!r}; "
                "this operation may only be performed against ACTIVE or "
                "DEFAULTED contracts.",
                str(contract_id),
            )

        outstanding_lines = self._outstanding_lines(company_id, contract_id)
        total_outstanding = sum(
            (line.outstanding_amount for line in outstanding_lines), Decimal("0")
        )
        if amount > total_outstanding:
            raise InstallmentOverCollectionError(
                str(amount), str(total_outstanding), str(contract_id)
            )

        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            amount, outstanding_lines
        )

        invoice_ar_transaction_id = self._accounting.get_invoice_ar_transaction_id(
            company_id, contract.sales_invoice_id
        )
        if invoice_ar_transaction_id is None:
            raise InstallmentActivationFailedError(
                "No Accounting AR transaction found for the originating "
                "sales invoice; cannot record the collection.",
                str(contract_id),
            )

        # Each instruction targets its own AR transaction — an ordinary
        # schedule-line instruction targets the originating invoice's
        # transaction (ar_transaction_id is None, resolved here); a
        # late-charge instruction (Phase 8) already carries its own
        # DEBIT_NOTE transaction id from _outstanding_lines() above.
        allocation_lines_payload = [
            {
                "transaction_id": instr.ar_transaction_id or invoice_ar_transaction_id,
                "amount_foreign": instr.amount,
            }
            for instr in instructions
        ]

        result_holder: dict[str, Any] = {}

        def _stage_installments_rows(
            staged_payment: Any, staged_allocation: Any
        ) -> None:
            for instr, alloc_line in zip(
                instructions, staged_allocation.results, strict=True
            ):
                self._allocation_refs.create(
                    InstallmentAllocationReference(
                        company_id=company_id,
                        contract_id=contract_id,
                        schedule_line_id=instr.schedule_line_id,
                        accounting_payment_id=staged_payment.payment.id,
                        accounting_payment_allocation_line_id=alloc_line.id,
                        allocated_amount=instr.amount,
                        allocation_order=instr.allocation_order,
                        is_reversal=False,
                    )
                )
            self._audit.record(
                company_id,
                "InstallmentContract",
                contract.id,
                action=audit_action,
                actor_id=actor_id,
                after={"amount": str(amount), "payment_method": payment_method},
            )
            self._outbox.create(
                OutboxRecord(
                    event_type=outbox_event_type,
                    aggregate_id=str(contract.id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract.id),
                        "company_id": str(company_id),
                        "amount": str(amount),
                        "accounting_payment_id": str(staged_payment.payment.id),
                    },
                )
            )

            remaining_after = total_outstanding - amount
            contract_status_after = contract.status
            if remaining_after == 0:
                try:
                    self._outstanding.assert_zero_outstanding(company_id, contract_id)
                except InstallmentOutstandingBalanceRemainsError:
                    # An authoritative obligation remains (e.g. an open
                    # late-charge AR, Phase 8) — this collection still
                    # succeeds and commits; only the contract-level
                    # COMPLETED transition is withheld (per that
                    # exception's own documented contract).
                    pass
                else:
                    completed = self._contract_service.complete(
                        company_id, contract, actor_id
                    )
                    contract_status_after = completed.status

            result_holder["payload"] = {
                "contract_id": str(contract.id),
                "amount": str(amount),
                "accounting_payment_id": str(staged_payment.payment.id),
                "contract_status": contract_status_after,
                "status": "COMPLETED",
            }
            self._idempotency.complete(
                reservation.reservation_id, result_holder["payload"]
            )

        try:
            gateway_result = self._accounting.record_collection(
                company_id=company_id,
                customer_id=contract.customer_id,
                payment_method=payment_method,
                payment_date=date.today(),
                amount=amount,
                currency_code=contract.currency_code,
                allocation_lines=allocation_lines_payload,
                actor_id=actor_id,
                stage_installments_rows=_stage_installments_rows,
                bank_account_id=bank_account_id,
                cash_account_id=cash_account_id,
            )
        except PostingValidationError as exc:
            self.db.rollback()
            _raise_for_posting_error(exc, contract_id)

        from modules.accounting.services.payment_service import DraftPaymentResult

        if isinstance(gateway_result, DraftPaymentResult):
            # Above the tenant's payment_approval_threshold with the
            # approval-workflow feature flag enabled — no GL/AR truth
            # exists yet, so there is nothing to allocate. Record that
            # this collection is pending Accounting approval; the actual
            # allocation/completion flow for an approved DRAFT payment is
            # an existing, pre-Installments Accounting workflow, not
            # covered by this phase (plan.md §12.3.1).
            self._audit.record(
                company_id,
                "InstallmentContract",
                contract.id,
                action=pending_approval_audit_action,
                actor_id=actor_id,
                after={
                    "amount": str(amount),
                    "accounting_payment_id": str(gateway_result.payment.id),
                },
            )
            payload = {
                "contract_id": str(contract.id),
                "amount": str(amount),
                "accounting_payment_id": str(gateway_result.payment.id),
                "contract_status": contract.status,
                "status": "PENDING_APPROVAL",
            }
            self._idempotency.complete(reservation.reservation_id, payload)
            self.db.commit()
            return payload

        payload_result: dict[str, Any] = result_holder["payload"]
        return payload_result

    def reverse_collection(
        self,
        company_id: UUID,
        collection_id: UUID,
        reason: str,
        idempotency_key: str,
        actor_id: UUID | None,
    ) -> dict[str, Any]:
        """Reverse a previously recorded collection (``collection_id`` is
        the Accounting ``Payment.id`` the original collection created —
        matches the OpenAPI contract's single-path-parameter
        ``/collections/{collectionId}/reverse`` exactly; the owning
        contract is derived from the collection's own
        ``InstallmentAllocationReference`` rows, never a second,
        undeclared request parameter). Reversal-reference rows correctly
        reference the original; the original rows are never mutated
        (BR-INST-017).

        No Accounting-side code change — reversal-reference rows are
        staged *before* calling
        ``AccountingIntegrationGateway.reverse_payment()`` (plan.md
        §12.3.2's staging-order discipline), so its first internal
        commit sweeps them in.

        Raises:
            InstallmentReversalNotAllowedError: ``collection_id`` does not
                exist for this tenant, has already been reversed, or its
                contract is not in a reversible status.
            InstallmentIdempotencyConflictError: same key, different
                request (409).
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.SERVICING
            )
        original_refs = self._allocation_refs.get_by_payment_id(
            company_id, collection_id
        )
        if not original_refs:
            raise InstallmentReversalNotAllowedError(
                f"No collection '{collection_id}' found for this company.",
                str(collection_id),
            )
        contract_id = original_refs[0].contract_id

        fingerprint = hashlib.sha256(
            f"collection.reverse:{collection_id}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "collection.reverse",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return reservation.result_payload or {}

        contract = self._contracts.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentReversalNotAllowedError(
                f"No collection '{collection_id}' found for this company.",
                str(collection_id),
            )
        if contract.status not in _REVERSIBLE_STATUSES:
            raise InstallmentReversalNotAllowedError(
                f"Installment contract '{contract_id}' is {contract.status!r}; "
                "collections against it can no longer be reversed in this phase.",
                str(collection_id),
            )

        already_reversed_ids = {
            ref.reverses_allocation_reference_id
            for ref in self._allocation_refs.list_for_contract(company_id, contract_id)
            if ref.is_reversal and ref.reverses_allocation_reference_id is not None
        }
        if any(ref.id in already_reversed_ids for ref in original_refs):
            raise InstallmentReversalNotAllowedError(
                f"Collection '{collection_id}' has already been reversed.",
                str(collection_id),
            )

        def _stage_reversal_rows() -> None:
            for order, original in enumerate(original_refs, start=1):
                self._allocation_refs.create(
                    InstallmentAllocationReference(
                        company_id=company_id,
                        contract_id=contract_id,
                        schedule_line_id=original.schedule_line_id,
                        accounting_payment_id=original.accounting_payment_id,
                        accounting_payment_allocation_line_id=(
                            original.accounting_payment_allocation_line_id
                        ),
                        allocated_amount=original.allocated_amount,
                        allocation_order=order,
                        is_reversal=True,
                        reverses_allocation_reference_id=original.id,
                    )
                )
            self._audit.record(
                company_id,
                "InstallmentContract",
                contract.id,
                action="COLLECTION_REVERSED",
                actor_id=actor_id,
                reason=reason,
                after={"collection_id": str(collection_id)},
            )
            self._outbox.create(
                OutboxRecord(
                    event_type="installment.collection_reversed",
                    aggregate_id=str(contract.id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract.id),
                        "company_id": str(company_id),
                        "collection_id": str(collection_id),
                    },
                )
            )
            self._idempotency.complete(
                reservation.reservation_id,
                {
                    "contract_id": str(contract.id),
                    "collection_id": str(collection_id),
                    "status": "REVERSED",
                },
            )

        self._accounting.reverse_payment(
            company_id=company_id,
            payment_id=collection_id,
            full_cancellation=False,
            reason=reason,
            actor_id=actor_id,
            stage_installments_rows=_stage_reversal_rows,
        )

        return {
            "contract_id": str(contract.id),
            "collection_id": str(collection_id),
            "status": "REVERSED",
        }

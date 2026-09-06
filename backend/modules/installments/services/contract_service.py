"""InstallmentContractService — the Installments aggregate-root service.

Phase 3 implements ``create_draft()`` — the DRAFT-creation path. Phase 5
adds the named lifecycle-transition methods (``submit()``, ``approve()``,
``reject()``, ``cancel()``, ``mark_defaulted()``) — each asserts
``_LEGAL_TRANSITIONS`` before mutating and audits the mutation; there is
no generic ``set_status()``/``update_status()`` anywhere (FR-INST-106).

Phase 7 adds ``activate()``/``complete()``. Phase 10 completes
``cancel()``'s financial-activity branch and adds ``default_command()``
(the idempotency-protected external wrapper around ``mark_defaulted()``),
``cure()``, and ``writeoff()``.

Spec ref: specs/010-installments/plan.md §9 (Lifecycle), §13 (Sales
Integration).
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from core.events.outbox import EventOutboxRepository, OutboxRecord
from core.exceptions.base import ConflictException, ValidationException
from core.utils.datetime import utcnow
from modules.accounting.exceptions import PostingValidationError
from modules.installments.constants import _LEGAL_TRANSITIONS
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentCancellationNotAllowedError,
    InstallmentCancellationPaymentReferenceRequiredError,
    InstallmentCureNotAllowedError,
    InstallmentFiscalPeriodLockedError,
    InstallmentIllegalTransitionError,
    InstallmentNotFoundError,
    InstallmentSelfApprovalNotAllowedError,
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
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from modules.installments.services.schedule_engine import ScheduleEngine
from modules.installments.services.terms_policy_validator import (
    InstallmentTermsPolicyValidator,
)

_DEFAULT_ROUNDING_POLICY = "ROUND_HALF_UP"


def _raise_for_posting_error(exc: PostingValidationError, contract_id: UUID) -> None:
    """Translate a raw Accounting ``PostingValidationError`` into the
    correct Installments-typed exception (plan.md §22): a locked fiscal
    period maps to the documented ``PERIOD_LOCKED`` 422; every other
    posting failure maps to ``InstallmentActivationFailedError`` (409,
    per the OpenAPI contract's "insufficient down payment, or
    reconciliation check failed" response)."""
    if "period" in str(exc).lower() and "lock" in str(exc).lower():
        raise InstallmentFiscalPeriodLockedError(str(exc)) from exc
    raise InstallmentActivationFailedError(str(exc), str(contract_id)) from exc


def _assert_transition(current_status: str, target_status: str) -> None:
    """Raises ``InstallmentIllegalTransitionError`` unless ``target_status``
    is a legal successor of ``current_status`` per ``_LEGAL_TRANSITIONS``
    (plan.md §9.2). Mirrors ``SalesOrder``'s ``_assert_invoice_transition()``
    idiom — the only place transition legality is decided."""
    if target_status not in _LEGAL_TRANSITIONS.get(current_status, frozenset()):
        raise InstallmentIllegalTransitionError(current_status, target_status)


def build_terms_snapshot(
    *,
    sales_invoice_id: UUID,
    customer_id: UUID,
    plan_template_id: UUID | None,
    contract_date: date,
    principal_amount: Decimal,
    down_payment_amount: Decimal,
    markup_amount: Decimal,
    contractual_total: Decimal,
    installment_count: int,
    frequency: str,
    first_due_date: date,
    maturity_date: date,
    currency_code: str,
    grace_period_days: int = 0,
    late_charge_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure function — a self-sufficient JSONB explanation of the full
    obligation (FR-INST-041), readable independently of whatever the
    originating Sales invoice, plan template, or tenant configuration
    look like later (those may change or be deleted; this snapshot never
    does).

    ``grace_period_days``/``late_charge_policy`` capture the effective
    ``InstallmentConfiguration`` policy in force at contract creation
    (FR-INST-172, BR-INST-009) — Phase 8's due-state/late-charge
    calculations read these frozen values, never live configuration, so
    a later tenant policy change can never retroactively alter an
    already-created contract's overdue/late-charge behavior.
    """
    return {
        "sales_invoice_id": str(sales_invoice_id),
        "customer_id": str(customer_id),
        "plan_template_id": str(plan_template_id) if plan_template_id else None,
        "contract_date": contract_date.isoformat(),
        "principal_amount": str(principal_amount),
        "down_payment_amount": str(down_payment_amount),
        "markup_amount": str(markup_amount),
        "contractual_total": str(contractual_total),
        "installment_count": installment_count,
        "frequency": frequency,
        "first_due_date": first_due_date.isoformat(),
        "maturity_date": maturity_date.isoformat(),
        "currency_code": currency_code,
        "grace_period_days": grace_period_days,
        "late_charge_policy": late_charge_policy,
    }


class InstallmentContractService:
    """Service layer for the InstallmentContract aggregate root."""

    def __init__(
        self,
        repo: InstallmentContractRepository,
        sequence_repo: InstallmentSequenceRepository,
        eligibility_service: InstallmentEligibilityService,
        accounting_gateway: AccountingIntegrationGateway,
        configuration_service: InstallmentConfigurationService,
        audit_service: InstallmentAuditService,
        schedule_repo: InstallmentScheduleRepository | None = None,
        idempotency_service: InstallmentIdempotencyService | None = None,
        outbox_repo: EventOutboxRepository | None = None,
        allocation_ref_repo: InstallmentAllocationReferenceRepository | None = None,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self._repo = repo
        self._sequences = sequence_repo
        self._eligibility = eligibility_service
        self._accounting = accounting_gateway
        self._configuration = configuration_service
        self._audit = audit_service
        self._schedule = schedule_repo
        self._idempotency = idempotency_service
        self._outbox = outbox_repo
        self._allocation_refs = allocation_ref_repo
        self._access_policy = access_policy

    def _authorize(
        self, company_id: UUID, operation: InstallmentOperationClass
    ) -> None:
        if self._access_policy is not None:
            self._access_policy.authorize(company_id=company_id, operation=operation)

    def create_draft(
        self,
        company_id: UUID,
        actor_id: UUID | None,
        *,
        sales_invoice_id: UUID,
        down_payment_amount: Decimal,
        installment_count: int,
        frequency: str,
        first_due_date: date,
        maturity_date: date,
        markup_amount: Decimal = Decimal("0"),
        plan_template_id: UUID | None = None,
        branch_id: UUID | None = None,
        contract_date: date | None = None,
    ) -> InstallmentContract:
        """Create a DRAFT installment contract against an eligible Sales
        invoice.

        ``financed_principal`` is computed from the invoice's LIVE
        outstanding amount (never a stale/duplicated field, FR-INST-261)
        minus the down payment — correctly excluding any pre-existing
        partial payments already applied to the invoice.

        Raises:
            InstallmentNotFoundError: invoice/customer not found for this
                tenant (BR-INST-015).
            ValidationException: invoice/customer ineligible (see
                ``InstallmentEligibilityService``).
            ConflictException: an existing non-terminal contract already
                covers this invoice (BR-INST-042) — the service-layer
                pre-check; the DB partial unique index is the real
                backstop against a concurrent race (T053).
            InstallmentTermsPolicyViolationError: proposed terms fall
                outside the effective ``InstallmentConfiguration``'s
                policy bounds (FR-INST-011, plan.md §10.6) — the same
                check ``InstallmentQuoteService.preview()`` applies, so a
                caller cannot bypass it by skipping ``/quotes``.
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        eligibility = self._eligibility.check_invoice_eligibility(
            company_id, sales_invoice_id
        )

        existing = self._repo.find_active_by_sales_invoice(company_id, sales_invoice_id)
        if existing is not None:
            raise ConflictException(
                message=(
                    f"Installment contract '{existing.contract_number}' already "
                    f"covers sales invoice '{sales_invoice_id}'."
                ),
                details={
                    "sales_invoice_id": str(sales_invoice_id),
                    "existing_contract_id": str(existing.id),
                },
            )

        financed_principal = eligibility.outstanding_amount - down_payment_amount
        contractual_total = financed_principal + markup_amount
        effective_contract_date = contract_date or date.today()

        config = self._configuration.get_effective_config(company_id, branch_id)
        InstallmentTermsPolicyValidator.validate(
            config,
            frequency=frequency,
            installment_count=installment_count,
            principal_amount=eligibility.outstanding_amount,
            down_payment_amount=down_payment_amount,
            financed_amount=financed_principal,
        )

        contract_number = self._sequences.generate_next_number(company_id)

        terms_snapshot = build_terms_snapshot(
            sales_invoice_id=sales_invoice_id,
            customer_id=eligibility.customer_id,
            plan_template_id=plan_template_id,
            contract_date=effective_contract_date,
            principal_amount=financed_principal,
            down_payment_amount=down_payment_amount,
            markup_amount=markup_amount,
            contractual_total=contractual_total,
            installment_count=installment_count,
            frequency=frequency,
            first_due_date=first_due_date,
            maturity_date=maturity_date,
            currency_code=eligibility.currency_code,
            grace_period_days=config.grace_period_days if config else 0,
            late_charge_policy=config.late_charge_policy if config else None,
        )

        contract = InstallmentContract(
            company_id=company_id,
            created_by=actor_id,
            contract_number=contract_number,
            branch_id=branch_id,
            customer_id=eligibility.customer_id,
            sales_invoice_id=sales_invoice_id,
            plan_template_id=plan_template_id,
            contract_date=effective_contract_date,
            principal_amount=financed_principal,
            down_payment_amount=down_payment_amount,
            markup_amount=markup_amount,
            contractual_total=contractual_total,
            installment_count=installment_count,
            frequency=frequency,
            first_due_date=first_due_date,
            maturity_date=maturity_date,
            currency_code=eligibility.currency_code,
            status="DRAFT",
            terms_snapshot=terms_snapshot,
        )
        try:
            return self._repo.create(contract)
        except IntegrityError as exc:
            self._repo.db.rollback()
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", None)
            if (
                constraint_name
                == "uq_installment_contracts_one_nonterminal_per_obligation"
            ):
                raise ConflictException(
                    message=(
                        "An existing non-terminal contract already covers "
                        f"sales invoice '{sales_invoice_id}'."
                    ),
                    details={"sales_invoice_id": str(sales_invoice_id)},
                ) from exc
            raise

    def get(self, company_id: UUID, contract_id: UUID) -> InstallmentContract:
        self._authorize(company_id, InstallmentOperationClass.READ)
        contract = self._repo.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

    def list(
        self,
        company_id: UUID,
        skip: int = 0,
        limit: int = 20,
        *,
        status: str | None = None,
    ) -> tuple[list[InstallmentContract], int]:
        self._authorize(company_id, InstallmentOperationClass.READ)
        if status is not None:
            return self._repo.list_filtered(
                company_id, status=status, skip=skip, limit=limit
            )
        return self._repo.list(company_id, skip=skip, limit=limit)

    def get_active_schedule(
        self, company_id: UUID, contract_id: UUID
    ) -> tuple[InstallmentContract, Any, list[InstallmentScheduleLine]]:
        """``GET /contracts/{id}/schedule`` (tasks.md T129) — the current
        ``ACTIVE`` schedule version and its lines. Raises
        ``InstallmentNotFoundError`` if the contract has never been
        activated (no active version exists yet)."""
        self._authorize(company_id, InstallmentOperationClass.READ)
        assert self._schedule is not None, (
            "get_active_schedule() requires schedule_repo"
        )
        contract = self._get_or_404(company_id, contract_id)
        version = self._schedule.get_active_version(company_id, contract_id)
        if version is None:
            raise InstallmentNotFoundError(
                "InstallmentScheduleVersion", str(contract_id)
            )
        lines = self._schedule.get_lines(company_id, version.id)
        return contract, version, lines

    def get_schedule_version(
        self, company_id: UUID, contract_id: UUID, version_number: int
    ) -> tuple[InstallmentContract, Any, list[InstallmentScheduleLine]]:
        """``GET /contracts/{id}/schedule/versions/{v}`` (tasks.md T129) —
        a specific (possibly superseded) schedule version, for historical
        explanation."""
        self._authorize(company_id, InstallmentOperationClass.READ)
        assert self._schedule is not None, (
            "get_schedule_version() requires schedule_repo"
        )
        contract = self._get_or_404(company_id, contract_id)
        version = self._schedule.get_version(company_id, contract_id, version_number)
        if version is None:
            raise InstallmentNotFoundError(
                "InstallmentScheduleVersion", f"{contract_id}/v{version_number}"
            )
        lines = self._schedule.get_lines(company_id, version.id)
        return contract, version, lines

    def _get_or_404(self, company_id: UUID, contract_id: UUID) -> InstallmentContract:
        contract = self._repo.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

    def submit(
        self, company_id: UUID, contract_id: UUID, actor_id: UUID | None
    ) -> InstallmentContract:
        """``DRAFT → PENDING_APPROVAL``, or directly ``DRAFT → APPROVED``
        if the effective configuration has no ``approval_threshold_amount``
        or the contract's ``contractual_total`` is below it (FR-INST-101).

        Raises:
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``DRAFT``.
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        contract = self._get_or_404(company_id, contract_id)

        # "APPROVED" is reachable in _LEGAL_TRANSITIONS from BOTH "DRAFT"
        # (this method's own no-threshold fast path) and "PENDING_APPROVAL"
        # (approve()'s target) — a bare graph-membership check would let
        # submit() be called a second time on an already-submitted
        # contract and silently fast-track it to APPROVED. submit() owns
        # exactly one edge: DRAFT -> {PENDING_APPROVAL, APPROVED}; require
        # the current status explicitly rather than relying on reachability
        # alone.
        if contract.status != "DRAFT":
            raise InstallmentIllegalTransitionError(contract.status, "PENDING_APPROVAL")

        config = self._configuration.get_effective_config(
            company_id, contract.branch_id
        )
        threshold = config.approval_threshold_amount if config is not None else None
        requires_approval = (
            threshold is not None and contract.contractual_total >= threshold
        )
        target_status = "PENDING_APPROVAL" if requires_approval else "APPROVED"

        now = utcnow()
        fields: dict[str, Any] = {
            "status": target_status,
            "submitted_by": actor_id,
            "submitted_at": now,
        }
        if not requires_approval:
            fields["approved_at"] = now

        updated = self._repo.update_with_version_check(
            contract_id=contract.id,
            company_id=company_id,
            expected_version=contract.version,
            **fields,
        )
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="SUBMITTED",
            actor_id=actor_id,
            before={"status": contract.status},
            after={"status": target_status},
            reason=(
                None
                if requires_approval
                else "Auto-approved: contractual_total below the configured "
                "approval threshold"
            ),
        )
        self._repo.db.commit()
        return updated

    def approve(
        self, company_id: UUID, contract_id: UUID, approver_id: UUID | None
    ) -> InstallmentContract:
        """``PENDING_APPROVAL → APPROVED``. The approver must be distinct
        from the submitter (FR-INST-102, plan.md §16.2).

        Raises:
            InstallmentSelfApprovalNotAllowedError: ``approver_id`` is the
                same actor who submitted the contract.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``PENDING_APPROVAL``.
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        contract = self._get_or_404(company_id, contract_id)

        # "APPROVED" is also reachable from "DRAFT" in _LEGAL_TRANSITIONS
        # (submit()'s own no-threshold fast path) — approve() owns exactly
        # the PENDING_APPROVAL -> APPROVED edge; a bare graph-membership
        # check would let approve() be called directly on a still-DRAFT
        # contract, where submitted_by is None and the self-approval check
        # below would be silently meaningless. Require the specific
        # predecessor status explicitly.
        if contract.status != "PENDING_APPROVAL":
            raise InstallmentIllegalTransitionError(contract.status, "APPROVED")

        if (
            contract.submitted_by is not None
            and approver_id is not None
            and contract.submitted_by == approver_id
        ):
            raise InstallmentSelfApprovalNotAllowedError(str(contract_id))

        updated = self._repo.update_with_version_check(
            contract_id=contract.id,
            company_id=company_id,
            expected_version=contract.version,
            status="APPROVED",
            approved_by=approver_id,
            approved_at=utcnow(),
        )
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="APPROVED",
            actor_id=approver_id,
            before={"status": contract.status},
            after={"status": "APPROVED"},
        )
        self._repo.db.commit()
        return updated

    def reject(
        self,
        company_id: UUID,
        contract_id: UUID,
        reason: str,
        rejecter_id: UUID | None,
    ) -> InstallmentContract:
        """``PENDING_APPROVAL → DRAFT``. ``REJECTED`` is never a persisted
        status — this is recorded only as an ``InstallmentAuditLog(action=
        "REJECTED")`` row (FR-INST-102, ADR-INST-11), which remains
        permanently visible even after the contract is resubmitted. Same
        distinct-approver check as ``approve()``, applied symmetrically
        from day one (plan.md §16.2).

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentSelfApprovalNotAllowedError: ``rejecter_id`` is the
                same actor who submitted the contract.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``PENDING_APPROVAL``.
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        if not reason or not reason.strip():
            raise ValidationException(
                message="A reason is required to reject an installment contract."
            )

        contract = self._get_or_404(company_id, contract_id)

        if (
            contract.submitted_by is not None
            and rejecter_id is not None
            and contract.submitted_by == rejecter_id
        ):
            raise InstallmentSelfApprovalNotAllowedError(str(contract_id))

        _assert_transition(contract.status, "DRAFT")

        updated = self._repo.update_with_version_check(
            contract_id=contract.id,
            company_id=company_id,
            expected_version=contract.version,
            status="DRAFT",
        )
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="REJECTED",
            actor_id=rejecter_id,
            before={"status": contract.status},
            after={"status": "DRAFT"},
            reason=reason,
        )
        self._repo.db.commit()
        return updated

    def cancel(
        self,
        company_id: UUID,
        contract_id: UUID,
        reason: str,
        idempotency_key: str,
        actor_id: UUID | None,
        *,
        payment_id: UUID | None = None,
    ) -> InstallmentContract:
        """Cancel a contract. Legality varies by stage (spec FR-INST-210):
        ``DRAFT``/``PENDING_APPROVAL``/``APPROVED``/``ACTIVE`` may all
        transition to ``CANCELLED`` per ``_LEGAL_TRANSITIONS``.

        Two paths, both idempotency-protected (``cancel`` is one of the 8
        approved high-risk commands, plan.md §20):

        - **Free path** (``DRAFT``/``PENDING_APPROVAL``/``APPROVED``, or
          ``ACTIVE`` with zero recorded activity — no down payment and no
          collections): status transition + audit + outbox + idempotency
          completion, single commit.
        - **Financial-activity path** (``ACTIVE`` with a recorded down
          payment and no further ordinary collections): the caller-
          supplied ``payment_id`` (the down payment's Accounting
          ``Payment`` id — Installments has no stored reference to it,
          since down-payment recording creates no
          ``InstallmentAllocationReference`` row, unlike ordinary
          collections) is un-allocated via
          ``AccountingIntegrationGateway.reverse_payment(full_cancellation=
          False)`` — the identical shape and staging-order discipline as
          ``InstallmentCollectionService.reverse_collection()`` (T123),
          including its choice of ``full_cancellation=False``: fully
          cancelling the payment itself would additionally require the
          calling actor to hold Accounting's own
          ``accounting.journal.reverse`` permission (``cancel_payment()``'s
          own SoD gate) — an Installments-side actor cannot be assumed to
          hold it, and plan.md §12.3.2 explicitly notes an unallocated
          ``Payment`` left in ``POSTED`` status is itself a valid,
          already-existing Accounting concept, not a corrupt one; any
          further refund/reallocation of that freed credit is Accounting's
          own, separate concern. Installments' own rows are staged and
          flushed *first*, so the first commit inside ``reverse_payment()``
          sweeps them in.

        An ``ACTIVE`` contract with any *ordinary* collection recorded
        (beyond the down payment) cannot be cancelled via this path at
        all — ``InstallmentCancellationNotAllowedError`` — those must be
        reversed individually first, or the contract settled/defaulted.

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentIllegalTransitionError: the current status has no
                legal path to ``CANCELLED``.
            InstallmentCancellationNotAllowedError: ordinary collections
                exist beyond the down payment (409).
            InstallmentCancellationPaymentReferenceRequiredError: a down
                payment exists but ``payment_id`` was not supplied (422).
            InstallmentIdempotencyConflictError: same key, different
                request (409).
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        if not reason or not reason.strip():
            raise ValidationException(
                message="A reason is required to cancel an installment contract."
            )
        assert self._idempotency is not None, "cancel() requires idempotency_service"
        assert self._outbox is not None, "cancel() requires outbox_repo"

        fingerprint = hashlib.sha256(
            f"contract.cancel:{contract_id}:{reason}:{payment_id}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "contract.cancel",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return self._get_or_404(company_id, contract_id)

        contract = self._repo.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        _assert_transition(contract.status, "CANCELLED")

        has_ordinary_collections = False
        if contract.status == "ACTIVE" and self._allocation_refs is not None:
            refs = self._allocation_refs.list_for_contract(company_id, contract_id)
            has_ordinary_collections = any(not ref.is_reversal for ref in refs)
        if has_ordinary_collections:
            raise InstallmentCancellationNotAllowedError(str(contract_id))

        has_down_payment = (
            contract.status == "ACTIVE" and contract.down_payment_amount > 0
        )
        if has_down_payment and payment_id is None:
            raise InstallmentCancellationPaymentReferenceRequiredError(str(contract_id))

        def _stage_cancellation_rows() -> None:
            before_status = contract.status
            contract.status = "CANCELLED"
            contract.cancelled_at = utcnow()
            contract.version = contract.version + 1
            self._repo.db.add(contract)
            self._repo.db.flush()
            self._audit.record(
                company_id,
                "InstallmentContract",
                contract.id,
                action="CANCELLED",
                actor_id=actor_id,
                before={"status": before_status},
                after={"status": "CANCELLED"},
                reason=reason,
            )
            assert self._outbox is not None
            self._outbox.create(
                OutboxRecord(
                    event_type="installment.contract.cancelled",
                    aggregate_id=str(contract.id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract.id),
                        "company_id": str(company_id),
                    },
                )
            )
            assert self._idempotency is not None
            self._idempotency.complete(
                reservation.reservation_id,
                {"contract_id": str(contract.id), "status": "CANCELLED"},
            )

        if has_down_payment:
            assert payment_id is not None
            self._accounting.reverse_payment(
                company_id=company_id,
                payment_id=payment_id,
                full_cancellation=False,
                reason=reason,
                actor_id=actor_id,
                stage_installments_rows=_stage_cancellation_rows,
            )
        else:
            _stage_cancellation_rows()
            self._repo.db.commit()

        return self._get_or_404(company_id, contract_id)

    def mark_defaulted(
        self,
        company_id: UUID,
        contract_id: UUID,
        reason: str,
        actor_id: UUID | None,
    ) -> InstallmentContract:
        """``ACTIVE → DEFAULTED`` — the pure internal state-machine
        primitive only (plan.md §9, tasks.md T078).

        **Internal only**: this method is not idempotency-protected, is
        not reachable via any router endpoint, and MUST NOT be called
        from ``router.py``. It performs zero Accounting calls and does
        **not** commit — it stages the transition and audit row (flush
        only) and returns; the externally-callable, idempotency-protected
        "default" command that calls this and then commits is Phase 10's
        ``default_command()`` (cannot exist before Phase 5.5's idempotency
        primitive).

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``ACTIVE``.
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        if not reason or not reason.strip():
            raise ValidationException(
                message="A reason is required to mark an installment "
                "contract defaulted."
            )

        contract = self._get_or_404(company_id, contract_id)

        _assert_transition(contract.status, "DEFAULTED")

        updated = self._repo.update_with_version_check(
            contract_id=contract.id,
            company_id=company_id,
            expected_version=contract.version,
            status="DEFAULTED",
            defaulted_at=utcnow(),
        )
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="DEFAULTED",
            actor_id=actor_id,
            before={"status": contract.status},
            after={"status": "DEFAULTED"},
            reason=reason,
        )
        # No commit — internal primitive only; the idempotency-protected
        # orchestration wrapper (Phase 10) commits as its own final step.
        return updated

    def default_command(
        self,
        company_id: UUID,
        contract_id: UUID,
        reason: str,
        idempotency_key: str,
        actor_id: UUID | None,
    ) -> InstallmentContract:
        """The externally-callable, idempotency-protected "default"
        command (tasks.md T166) — distinct from ``mark_defaulted()``'s
        internal transition primitive (T078). Structurally cannot exist
        before Phase 5.5's idempotency primitive, which is why it is a
        Phase 10 wrapper rather than part of ``mark_defaulted()`` itself.

        Idempotency reservation -> ``FOR UPDATE`` lock -> the internal
        ``mark_defaulted()`` primitive (stages the transition + audit,
        flush only) -> outbox staged -> idempotency completion staged ->
        single commit **last**. Zero Accounting calls anywhere in this
        sequence (BR-INST-013: reaching ``DEFAULTED`` never implies a
        posting).

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``ACTIVE``.
            InstallmentIdempotencyConflictError: same key, different
                request (409).
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        assert self._idempotency is not None, (
            "default_command() requires idempotency_service"
        )
        assert self._outbox is not None, "default_command() requires outbox_repo"

        fingerprint = hashlib.sha256(
            f"contract.default:{contract_id}:{reason}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "contract.default",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return self._get_or_404(company_id, contract_id)

        locked = self._repo.get_by_id_locked(contract_id, company_id)
        if locked is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))

        updated = self.mark_defaulted(company_id, contract_id, reason, actor_id)

        self._outbox.create(
            OutboxRecord(
                event_type="installment.contract.defaulted",
                aggregate_id=str(updated.id),
                aggregate_type="InstallmentContract",
                payload={
                    "contract_id": str(updated.id),
                    "company_id": str(company_id),
                },
            )
        )
        self._idempotency.complete(
            reservation.reservation_id,
            {"contract_id": str(updated.id), "status": "DEFAULTED"},
        )
        self._repo.db.commit()
        return updated

    def cure(
        self,
        company_id: UUID,
        contract_id: UUID,
        reason: str | None,
        actor_id: UUID | None,
    ) -> InstallmentContract:
        """``DEFAULTED -> ACTIVE`` (tasks.md T170) — policy-gated
        (``InstallmentConfiguration.cure_enabled``, a true kill switch
        per ADR-INST-12: holding ``installments.contract.cure`` alone is
        never sufficient). Never creates a new contract, never deletes
        default/delinquency history (the ``DEFAULTED`` audit event and
        every ``InstallmentLateCharge``/``InstallmentAllocationReference``
        row remain permanently visible), never touches Accounting, never
        rewrites the original terms snapshot.

        Discrete state transition — optimistic ``version`` check, no
        idempotency reservation (not one of the 8 approved high-risk
        idempotency-protected commands: no financial posting occurs).

        Raises:
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``DEFAULTED``.
            InstallmentCureNotAllowedError: the effective configuration
                has ``cure_enabled=False`` (422).
        """
        self._authorize(company_id, InstallmentOperationClass.SERVICING)
        contract = self._get_or_404(company_id, contract_id)
        _assert_transition(contract.status, "ACTIVE")

        config = self._configuration.get_effective_config(
            company_id, contract.branch_id
        )
        if config is None or not config.cure_enabled:
            raise InstallmentCureNotAllowedError(str(contract_id))

        updated = self._repo.update_with_version_check(
            contract_id=contract.id,
            company_id=company_id,
            expected_version=contract.version,
            status="ACTIVE",
        )
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="CURED",
            actor_id=actor_id,
            before={"status": "DEFAULTED"},
            after={"status": "ACTIVE"},
            reason=reason,
        )
        assert self._outbox is not None, "cure() requires outbox_repo"
        self._outbox.create(
            OutboxRecord(
                event_type="installment.contract.cured",
                aggregate_id=str(updated.id),
                aggregate_type="InstallmentContract",
                payload={
                    "contract_id": str(updated.id),
                    "company_id": str(company_id),
                },
            )
        )
        self._repo.db.commit()
        return updated

    def writeoff(
        self,
        company_id: UUID,
        contract_id: UUID,
        reason: str,
        idempotency_key: str,
        actor_id: UUID | None,
    ) -> InstallmentContract:
        """``DEFAULTED -> WRITTEN_OFF`` (tasks.md T171) — writes off the
        contract's originating invoice ``ARTransaction`` (the single
        authoritative remaining balance; Accounting has no per-schedule-
        line concept of its own) via
        ``AccountingIntegrationGateway.writeoff()``'s staged/finalize
        pair: ``stage_write_off()`` (flush only) -> Installments' own
        status transition + audit + outbox + idempotency completion
        staged -> ``finalize_write_off()`` called **last**, by
        Installments (plan.md §12.3.3) — the single commit for GL +
        ``ARTransaction`` status/outstanding + ``CustomerLedger``
        recompute + contract status + audit + outbox together.

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentNotFoundError: contract not found for this tenant,
                or no Accounting ``ARTransaction`` exists for its
                originating invoice.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``DEFAULTED``.
            InstallmentIdempotencyConflictError: same key, different
                request (409).
            InstallmentFiscalPeriodLockedError: locked fiscal period (422).
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        if not reason or not reason.strip():
            raise ValidationException(
                message="A reason is required to write off an installment contract."
            )
        assert self._idempotency is not None, "writeoff() requires idempotency_service"
        assert self._outbox is not None, "writeoff() requires outbox_repo"

        fingerprint = hashlib.sha256(
            f"contract.writeoff:{contract_id}:{reason}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "contract.writeoff",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return self._get_or_404(company_id, contract_id)

        contract = self._repo.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        _assert_transition(contract.status, "WRITTEN_OFF")

        ar_transaction_id = self._accounting.get_invoice_ar_transaction_id(
            company_id, contract.sales_invoice_id
        )
        if ar_transaction_id is None:
            raise InstallmentNotFoundError(
                "ARTransaction", str(contract.sales_invoice_id)
            )

        def _stage_writeoff_rows(_staged: Any) -> None:
            before_status = contract.status
            contract.status = "WRITTEN_OFF"
            contract.written_off_at = utcnow()
            contract.version = contract.version + 1
            self._repo.db.add(contract)
            self._repo.db.flush()
            self._audit.record(
                company_id,
                "InstallmentContract",
                contract.id,
                action="WRITTEN_OFF",
                actor_id=actor_id,
                before={"status": before_status},
                after={"status": "WRITTEN_OFF"},
                reason=reason,
            )
            assert self._outbox is not None
            self._outbox.create(
                OutboxRecord(
                    event_type="installment.contract.written_off",
                    aggregate_id=str(contract.id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract.id),
                        "company_id": str(company_id),
                    },
                )
            )
            assert self._idempotency is not None
            self._idempotency.complete(
                reservation.reservation_id,
                {"contract_id": str(contract.id), "status": "WRITTEN_OFF"},
            )

        try:
            self._accounting.writeoff(
                company_id=company_id,
                ar_transaction_id=ar_transaction_id,
                reason=reason,
                actor_id=actor_id,
                stage_installments_rows=_stage_writeoff_rows,
            )
        except PostingValidationError as exc:
            self._repo.db.rollback()
            _raise_for_posting_error(exc, contract_id)

        return self._get_or_404(company_id, contract_id)

    def activate(
        self,
        company_id: UUID,
        contract_id: UUID,
        idempotency_key: str,
        actor_id: UUID | None,
        *,
        payment_method: str = "BANK_TRANSFER",
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
    ) -> InstallmentContract:
        """``APPROVED -> ACTIVE`` (tasks.md T124, plan.md §21's Activation
        row): validates live eligibility, collects the down payment (if
        ``down_payment_amount > 0``) via
        ``AccountingIntegrationGateway.record_down_payment()``,
        generates and persists the authoritative schedule
        (``ScheduleEngine.generate()``), verifies the BR-INST-005
        reconciliation invariant, and transitions the contract — all
        staged into one atomic unit, committed once.

        Idempotency-protected (plan.md §20) — a replay of an
        already-``COMPLETED`` key with a matching fingerprint returns the
        current contract state without repeating any of the above.

        Raises:
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentIllegalTransitionError: ``contract.status`` is not
                ``APPROVED``.
            InstallmentIdempotencyConflictError: same key, different
                request (409).
            InstallmentFiscalPeriodLockedError: the down payment's
                posting date falls in a locked/closed fiscal period (422).
            InstallmentActivationFailedError: the down payment posting or
                the BR-INST-005 reconciliation check failed (409).
        """
        self._authorize(company_id, InstallmentOperationClass.ORIGINATION)
        assert self._schedule is not None, "activate() requires schedule_repo"
        assert self._idempotency is not None, "activate() requires idempotency_service"
        assert self._outbox is not None, "activate() requires outbox_repo"

        fingerprint = hashlib.sha256(
            f"contract.activate:{contract_id}".encode()
        ).hexdigest()
        reservation = self._idempotency.reserve(
            company_id,
            "contract.activate",
            idempotency_key,
            fingerprint,
            contract_id=contract_id,
        )
        if reservation.outcome == "REPLAY":
            return self._get_or_404(company_id, contract_id)

        contract = self._repo.get_by_id_locked(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        _assert_transition(contract.status, "ACTIVE")

        # Live re-validation (BR-INST-015/eligibility may have changed
        # since DRAFT creation — e.g. the customer was deactivated).
        self._eligibility.check_invoice_eligibility(
            company_id, contract.sales_invoice_id
        )

        config = self._configuration.get_effective_config(
            company_id, contract.branch_id
        )
        rounding_policy = (
            config.rounding_policy if config is not None else _DEFAULT_ROUNDING_POLICY
        )
        raw_principal = contract.principal_amount + contract.down_payment_amount
        schedule_result = ScheduleEngine.generate(
            principal=raw_principal,
            down_payment=contract.down_payment_amount,
            markup=contract.markup_amount,
            installment_count=contract.installment_count,
            frequency=contract.frequency,
            first_due_date=contract.first_due_date,
            rounding_policy=rounding_policy,
        )
        # BR-INST-005: the schedule's total MUST reconcile exactly with
        # the contract's own contractual_total — defensive re-verification
        # of a guarantee ScheduleEngine already provides by construction.
        schedule_sum = sum(
            (line.scheduled_amount for line in schedule_result.lines), Decimal("0")
        )
        if schedule_sum != contract.contractual_total:
            raise InstallmentActivationFailedError(
                "Generated schedule total "
                f"({schedule_sum}) does not reconcile with the contract's "
                f"contractual_total ({contract.contractual_total}).",
                str(contract_id),
            )

        version = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract_id,
            version_number=1,
            status="ACTIVE",
            generated_by=actor_id,
            reason="Initial activation schedule",
        )
        lines = [
            InstallmentScheduleLine(
                company_id=company_id,
                sequence=line.sequence,
                due_date=line.due_date,
                scheduled_amount=line.scheduled_amount,
            )
            for line in schedule_result.lines
        ]
        self._schedule.create_version_with_lines(version, lines)

        def _stage_installments_rows(
            _staged_payment: Any, _staged_allocation: Any
        ) -> None:
            contract.status = "ACTIVE"
            contract.activated_at = utcnow()
            contract.active_schedule_version_id = version.id
            contract.version = contract.version + 1
            self._repo.db.add(contract)
            self._repo.db.flush()
            self._audit.record(
                company_id,
                "InstallmentContract",
                contract.id,
                action="ACTIVATED",
                actor_id=actor_id,
                before={"status": "APPROVED"},
                after={"status": "ACTIVE"},
            )
            assert self._outbox is not None
            self._outbox.create(
                OutboxRecord(
                    event_type="installment.contract.activated",
                    aggregate_id=str(contract.id),
                    aggregate_type="InstallmentContract",
                    payload={
                        "contract_id": str(contract.id),
                        "company_id": str(company_id),
                        "down_payment_amount": str(contract.down_payment_amount),
                    },
                )
            )
            assert self._idempotency is not None
            self._idempotency.complete(
                reservation.reservation_id,
                {"contract_id": str(contract.id), "status": "ACTIVE"},
            )

        if contract.down_payment_amount > 0:
            ar_transaction_id = self._accounting.get_invoice_ar_transaction_id(
                company_id, contract.sales_invoice_id
            )
            if ar_transaction_id is None:
                raise InstallmentActivationFailedError(
                    "No Accounting AR transaction found for the originating "
                    "sales invoice; cannot record the down payment.",
                    str(contract_id),
                )
            try:
                self._accounting.record_down_payment(
                    company_id=company_id,
                    customer_id=contract.customer_id,
                    payment_method=payment_method,
                    payment_date=date.today(),
                    amount=contract.down_payment_amount,
                    currency_code=contract.currency_code,
                    allocation_lines=[
                        {
                            "transaction_id": ar_transaction_id,
                            "amount_foreign": contract.down_payment_amount,
                        }
                    ],
                    actor_id=actor_id,
                    stage_installments_rows=_stage_installments_rows,
                    bank_account_id=bank_account_id,
                    cash_account_id=cash_account_id,
                )
            except PostingValidationError as exc:
                self._repo.db.rollback()
                _raise_for_posting_error(exc, contract_id)
        else:
            _stage_installments_rows(None, None)
            self._repo.db.commit()

        return self._get_or_404(company_id, contract_id)

    def complete(
        self,
        company_id: UUID,
        contract: InstallmentContract,
        actor_id: UUID | None,
    ) -> InstallmentContract:
        """``ACTIVE -> COMPLETED`` / ``DEFAULTED -> COMPLETED`` (tasks.md
        T122) — the internal completion primitive. Requires the caller
        (``InstallmentCollectionService.record_collection()``, and later
        Phase 9's settlement execution) to have already called
        ``InstallmentOutstandingService.assert_zero_outstanding()``
        successfully; this method performs no outstanding check of its
        own (FR-INST-104, plan.md §9.3's completion guard).

        Flush only — never commits. ``contract`` must already be the
        caller's own locked (``FOR UPDATE``) row, mutated in place; the
        caller's own final commit covers this together with everything
        else it staged.
        """
        self._authorize(company_id, InstallmentOperationClass.SERVICING)
        _assert_transition(contract.status, "COMPLETED")
        before_status = contract.status
        contract.status = "COMPLETED"
        contract.closed_at = utcnow()
        contract.version = contract.version + 1
        self._repo.db.add(contract)
        self._repo.db.flush()
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="COMPLETED",
            actor_id=actor_id,
            before={"status": before_status},
            after={"status": "COMPLETED"},
        )
        return contract

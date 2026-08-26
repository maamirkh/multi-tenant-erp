"""InstallmentContractService — the Installments aggregate-root service.

Phase 3 implements ``create_draft()`` — the DRAFT-creation path. Phase 5
adds the named lifecycle-transition methods (``submit()``, ``approve()``,
``reject()``, ``cancel()``, ``mark_defaulted()``) — each asserts
``_LEGAL_TRANSITIONS`` before mutating and audits the mutation; there is
no generic ``set_status()``/``update_status()`` anywhere (FR-INST-106).

``activate()``, ``complete()``, ``cure()``, ``writeoff()``, and the
idempotency-protected external "default"/"cancel-with-financial-activity"
commands are later phases' scope (Phase 7/Phase 10) and are not
pre-created here.

Spec ref: specs/010-installments/plan.md §9 (Lifecycle), §13 (Sales
Integration).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from core.exceptions.base import ConflictException, ValidationException
from core.utils.datetime import utcnow
from modules.installments.constants import _LEGAL_TRANSITIONS
from modules.installments.exceptions import (
    InstallmentIllegalTransitionError,
    InstallmentNotFoundError,
    InstallmentSelfApprovalNotAllowedError,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
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
from modules.installments.services.terms_policy_validator import (
    InstallmentTermsPolicyValidator,
)


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
) -> dict[str, Any]:
    """Pure function — a self-sufficient JSONB explanation of the full
    obligation (FR-INST-041), readable independently of whatever the
    originating Sales invoice, plan template, or tenant configuration
    look like later (those may change or be deleted; this snapshot never
    does)."""
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
    ) -> None:
        self._repo = repo
        self._sequences = sequence_repo
        self._eligibility = eligibility_service
        self._accounting = accounting_gateway
        self._configuration = configuration_service
        self._audit = audit_service

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
        contract = self._repo.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

    def list(
        self, company_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[InstallmentContract], int]:
        return self._repo.list(company_id, skip=skip, limit=limit)

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
        actor_id: UUID | None,
    ) -> InstallmentContract:
        """Cancel a contract. Legality varies by stage (plan.md §15.3):
        ``DRAFT``/``PENDING_APPROVAL``/``APPROVED``/``ACTIVE`` may all
        transition to ``CANCELLED`` per ``_LEGAL_TRANSITIONS``.

        This phase implements only the free (no-financial-activity) path.
        An ``ACTIVE`` contract with financial activity must delegate to a
        reversal workflow that cannot exist before collections/allocations
        do (Phase 7) or before the idempotency primitive does (Phase 5.5)
        — that branch, and this method's ``idempotency_key`` parameter,
        are completed by Phase 10's T169. No contract can reach ``ACTIVE``
        at all yet (``activate()`` is Phase 7's T124), so every path
        reachable today is necessarily the free path.

        Raises:
            ValidationException: ``reason`` is empty.
            InstallmentNotFoundError: contract not found for this tenant.
            InstallmentIllegalTransitionError: the current status has no
                legal path to ``CANCELLED``.
        """
        if not reason or not reason.strip():
            raise ValidationException(
                message="A reason is required to cancel an installment contract."
            )

        contract = self._get_or_404(company_id, contract_id)

        _assert_transition(contract.status, "CANCELLED")

        updated = self._repo.update_with_version_check(
            contract_id=contract.id,
            company_id=company_id,
            expected_version=contract.version,
            status="CANCELLED",
            cancelled_at=utcnow(),
        )
        self._audit.record(
            company_id,
            "InstallmentContract",
            contract.id,
            action="CANCELLED",
            actor_id=actor_id,
            before={"status": contract.status},
            after={"status": "CANCELLED"},
            reason=reason,
        )
        self._repo.db.commit()
        return updated

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

"""AccountingIntegrationGateway — the single controlled Installments ->
Accounting module boundary.

**[Correction 3, plan.md §12.3.4/§13]** Created here in Phase 3 (not
deferred to Phase 6) specifically so no earlier or later task is ever
tempted to import ``modules.accounting.models``/``.repositories``
directly. Phase 3 added only the **read-only** live-read operations
eligibility/draft-creation genuinely need. Phase 6 (T107) extends this
same class with the money-mutating staged/finalize methods below — one
gateway, not two competing abstractions.

Imports only ``modules.accounting.services`` classes, **never**
``.models`` or ``.repositories`` — enforced by a structural/import-lint
test (mirrors the Platform-Admin structural-boundary test convention).

No Accounting balance is cached or duplicated inside Installments —
every read call here is a live pass-through against Accounting's own
authoritative state. Every money-mutating call below follows the exact
stage -> Installments-rows -> finalize-last sequence from plan.md
§12.3.1-§12.3.3: this gateway calls an Accounting ``stage_*`` method
(flush only, no commit), then invokes the caller-supplied
``stage_installments_rows`` callback so the caller's own rows (audit,
outbox, idempotency completion, domain rows) land in the *same*
uncommitted session, and only then calls the paired Accounting
``finalize_*``/``reallocate_payment``/``reverse_adjustment`` method,
whose commit is the single atomicity boundary for everything staged
since the ``stage_*`` call. The callback exists because this gateway
must never import Installments' own models (only
``modules.accounting.services`` classes) — it lets the Installments
caller (which owns those models) build and stage its own rows without
the gateway ever seeing their concrete types.

Spec ref: specs/010-installments/plan.md §12.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from modules.accounting.services.allocation_engine import (
    AllocationEngine,
    StagedAllocation,
)
from modules.accounting.services.ar_service import (
    AccountsReceivableService,
    StagedAdjustment,
    StagedWriteOff,
)
from modules.accounting.services.payment_service import (
    DraftPaymentResult,
    PaymentService,
    StagedCustomerPayment,
)


class AccountingIntegrationGateway:
    """The single controlled module boundary between Installments and
    Accounting. Read-only operations from Phase 3; money-mutating
    staged/finalize operations added in Phase 6 (T107)."""

    def __init__(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        allocation_engine: AllocationEngine,
    ) -> None:
        self._ar_service = ar_service
        self._payment_service = payment_service
        self._allocation_engine = allocation_engine

    def get_invoice_outstanding_amount(
        self, company_id: UUID, sales_invoice_id: UUID
    ) -> Decimal:
        """Live read of the outstanding amount owed against a Sales
        invoice, sourced from Accounting's own ``ARTransaction`` (never a
        Sales field — Sales has no outstanding-amount column, plan.md
        §2/§13). Returns ``Decimal("0")`` if no AR transaction exists yet
        for this invoice (nothing posted, nothing outstanding)."""
        transaction = self._ar_service.find_transaction_by_source_document(
            company_id, "SalesInvoice", sales_invoice_id
        )
        if transaction is None:
            return Decimal("0")
        return transaction.outstanding_amount

    def get_ar_transaction(self, company_id: UUID, ar_transaction_id: UUID):
        """Live read of a single ``ARTransaction`` by id, or ``None`` if
        it does not exist for this company. Used starting Phase 6/9
        (late-charge tracking, ``InstallmentOutstandingService.assert_zero_outstanding()``,
        plan.md §9.3) — not consumed by Phase 3 itself."""
        return self._ar_service.get_transaction_by_id(company_id, ar_transaction_id)

    # ------------------------------------------------------------------
    # Money-mutating staged/finalize operations (Phase 6, T107)
    # ------------------------------------------------------------------

    def _record_payment_and_allocate(
        self,
        *,
        company_id: UUID,
        customer_id: UUID,
        payment_method: str,
        payment_date: date,
        amount: Decimal,
        currency_code: str,
        allocation_lines: list[dict[str, Any]],
        bank_account_id: UUID | None,
        cash_account_id: UUID | None,
        actor_id: UUID | None,
        stage_installments_rows: Callable[
            [StagedCustomerPayment, StagedAllocation], None
        ],
    ):
        """Shared mechanics for down payment / collection / settlement
        payment (plan.md §12.3.1 — "the only difference between the
        three is which ``ARTransaction`` (s) the ``allocation_lines``
        argument targets, never the commit-ownership mechanics").

        Stages the customer payment, then the allocation against it,
        then invokes ``stage_installments_rows`` with both staged
        results so the caller can build its own
        ``InstallmentAllocationReference`` rows before either Accounting
        call is finalized. Both Accounting finalize calls happen last,
        in the order the plan's sequence diagram requires.

        If the payment amount is above the tenant's configured approval
        threshold, no GL/AR truth is created yet — ``stage_customer_payment()``
        returns a ``DraftPaymentResult`` and this method returns it
        unchanged without invoking the callback or any allocation, since
        there is nothing yet to allocate or bundle (plan.md §12.3.1).
        """
        staged_payment = self._payment_service.stage_customer_payment(
            company_id=company_id,
            customer_id=customer_id,
            payment_method=payment_method,
            payment_date=payment_date,
            amount=amount,
            currency_code=currency_code,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            actor_id=actor_id,
        )
        if isinstance(staged_payment, DraftPaymentResult):
            return staged_payment

        staged_allocation = self._allocation_engine.stage_allocation(
            company_id=company_id,
            payment_id=staged_payment.payment.id,
            allocation_lines=allocation_lines,
            actor_id=actor_id,
        )

        stage_installments_rows(staged_payment, staged_allocation)

        payment, _ = self._payment_service.finalize_customer_payment(
            staged_payment, actor_id
        )
        allocation_result = self._allocation_engine.finalize_allocation(
            staged_allocation, actor_id
        )
        return payment, allocation_result

    def record_down_payment(
        self,
        *,
        company_id: UUID,
        customer_id: UUID,
        payment_method: str,
        payment_date: date,
        amount: Decimal,
        currency_code: str,
        allocation_lines: list[dict[str, Any]],
        actor_id: UUID | None,
        stage_installments_rows: Callable[
            [StagedCustomerPayment, StagedAllocation], None
        ],
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
    ):
        """Down payment (plan.md §12 "Down payment" row / §12.3.1) — a
        customer payment staged and allocated against the originating
        invoice's ``ARTransaction``, with the caller's own rows bundled
        into the same commit."""
        return self._record_payment_and_allocate(
            company_id=company_id,
            customer_id=customer_id,
            payment_method=payment_method,
            payment_date=payment_date,
            amount=amount,
            currency_code=currency_code,
            allocation_lines=allocation_lines,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            actor_id=actor_id,
            stage_installments_rows=stage_installments_rows,
        )

    def record_collection(
        self,
        *,
        company_id: UUID,
        customer_id: UUID,
        payment_method: str,
        payment_date: date,
        amount: Decimal,
        currency_code: str,
        allocation_lines: list[dict[str, Any]],
        actor_id: UUID | None,
        stage_installments_rows: Callable[
            [StagedCustomerPayment, StagedAllocation], None
        ],
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
    ):
        """Ordinary collection / settlement payment (plan.md §12
        "Collection" row / §12.3.1) — identical mechanics to
        ``record_down_payment()``; only the schedule-line obligation(s)
        targeted by ``allocation_lines`` differ."""
        return self._record_payment_and_allocate(
            company_id=company_id,
            customer_id=customer_id,
            payment_method=payment_method,
            payment_date=payment_date,
            amount=amount,
            currency_code=currency_code,
            allocation_lines=allocation_lines,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            actor_id=actor_id,
            stage_installments_rows=stage_installments_rows,
        )

    def reverse_payment(
        self,
        *,
        company_id: UUID,
        payment_id: UUID,
        full_cancellation: bool,
        reason: str,
        actor_id: UUID | None,
        stage_installments_rows: Callable[[], None],
    ) -> None:
        """Collection reversal / cancellation-with-financial-reversal
        (plan.md §12.3.2). No Accounting-side staged/finalize pair
        exists for ``reallocate_payment()``/``cancel_payment()`` (their
        own internal multi-commit loop is unmodified, per the plan's
        explicit "no Accounting-side code change" resolution) — instead
        ``stage_installments_rows`` is invoked *first*, so the caller's
        own reversal rows (``InstallmentAllocationReference(is_reversal=True,
        ...)``, audit, outbox, idempotency completion) are already
        flushed into this session before ``reallocate_payment()``'s
        first internal commit sweeps them in. If ``full_cancellation``
        is requested, ``cancel_payment()`` runs afterward as a separate
        call — the honestly-flagged intermediate-state limitation
        documented in plan.md §12.3.2 (resumable via idempotency key).
        """
        stage_installments_rows()

        self._payment_service.reallocate_payment(
            company_id=company_id,
            payment_id=payment_id,
            new_allocation_lines=[],
            actor_id=actor_id,
        )
        if full_cancellation:
            self._payment_service.cancel_payment(
                company_id=company_id,
                payment_id=payment_id,
                reason=reason,
                actor_id=actor_id,
            )

    def post_late_charge(
        self,
        *,
        company_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        contra_account_id: UUID,
        reason: str,
        posting_date: date,
        source_document_id: UUID,
        actor_id: UUID | None,
        stage_installments_rows: Callable[[StagedAdjustment], None],
    ):
        """Late charge (plan.md §12 "Late charge" row / §12.1/§12.2) —
        stages a ``DEBIT_NOTE`` AR adjustment linked back to the
        ``InstallmentLateCharge`` via ``source_document_type``/
        ``source_document_id``, lets the caller stage its own
        ``InstallmentLateCharge``/audit/outbox rows into the same
        session, then finalizes last."""
        staged = self._ar_service.stage_adjustment(
            company_id=company_id,
            customer_id=customer_id,
            amount=amount,
            contra_account_id=contra_account_id,
            reason=reason,
            posting_date=posting_date,
            actor_id=actor_id,
            transaction_type="DEBIT_NOTE",
            source_document_type="InstallmentLateCharge",
            source_document_id=source_document_id,
        )

        stage_installments_rows(staged)

        return self._ar_service.finalize_adjustment(staged, actor_id)

    def reverse_late_charge(
        self,
        *,
        company_id: UUID,
        ar_transaction_id: UUID,
        reason: str,
        actor_id: UUID | None,
        stage_installments_rows: Callable[[], None],
    ):
        """Late-charge waiver of an already-posted charge (plan.md §12
        "Waiver" row) — ``reverse_adjustment()`` is single-phase (its
        own sole commit is ``PostingEngine.reverse()``), so the caller's
        own rows (``installment_late_charges.waived_at/by/reason``,
        audit, outbox) are staged *first*, into the same session, before
        this method is called — mirroring the reversal/cancellation
        staging-before-calling discipline."""
        stage_installments_rows()

        return self._ar_service.reverse_adjustment(
            company_id=company_id,
            ar_transaction_id=ar_transaction_id,
            reason=reason,
            actor_id=actor_id,
        )

    def writeoff(
        self,
        *,
        company_id: UUID,
        ar_transaction_id: UUID,
        reason: str,
        actor_id: UUID | None,
        stage_installments_rows: Callable[[StagedWriteOff], None],
    ):
        """Write-off (plan.md §12 "Write-off" row / §12.3.3) — stages
        the GL write-off posting and AR status change, lets the caller
        stage its own contract-status/audit/outbox rows into the same
        session, then finalizes last."""
        staged = self._ar_service.stage_write_off(
            company_id=company_id,
            ar_transaction_id=ar_transaction_id,
            reason=reason,
            actor_id=actor_id,
        )

        stage_installments_rows(staged)

        return self._ar_service.finalize_write_off(staged, actor_id)

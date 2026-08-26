"""AllocationEngine — Payment Processing — Phase 10.

Manages payment-to-invoice (AR) and payment-to-bill (AP) allocation.
Spec ref: specs/008-accounting-finance/data-model.md §4.3 AllocationEngine
Tasks ref: specs/008-accounting-finance/tasks.md T207

Design — every Payment gets a paired "credit" transaction:
``PaymentService.create_customer_payment()``/``create_supplier_payment()``
creates, atomically with the payment's own DR Bank/CR AR-control (or
DR AP-control/CR Bank) entry, a companion AR/APTransaction of type PAYMENT
(or ADVANCE) with a NEGATIVE ``outstanding_amount`` — i.e. a credit —
tagged ``source_document_type="Payment"``/``source_document_id=payment.id``.
``allocate()`` locks and decrements BOTH sides symmetrically: the target
invoice/bill's outstanding decreases toward zero, and the payment's own
credit transaction's outstanding increases toward zero (both are simply
"transactions" to this engine — a credit is just one with a negative
outstanding). This single mechanism gives three spec requirements for free:
  - Partial payment: allocate less than the full credit — both sides end
    PARTIALLY_PAID, aging stays accurate.
  - Overpayment (spec.md §22.5): allocate less than the payment's full
    amount — the credit transaction keeps a negative outstanding, visible
    in the customer/supplier ledger as a credit balance, exactly like any
    other open AR/AP row.
  - Advance payment (spec.md §22.4): same mechanism — an ADVANCE-type
    credit is "applied to invoices when they are subsequently raised" via
    an ordinary ``allocate()`` call whenever the invoice exists, no special
    machinery required beyond the ``release_account_id`` GL adjustment
    (below) to move the advance liability into AR/AP-control.

GL entries posted per allocation line (at most ONE combined "adjustment"
entry, referenced by ``PaymentAllocationLine.gain_loss_journal_entry_id`` —
the base cash/AR/AP movement was already posted in full when the payment
itself was created; this entry only carries the DELTA needed to reconcile
that bulk posting against this specific line's booked-rate value):
  - Early payment discount (if discount_amount > 0)
  - Realized FX gain/loss (if the transaction's booking rate differs from
    the payment's settlement rate — research.md Decision 8)
  - Advance/credit release (if the payment is ADVANCE_RECEIPT/ADVANCE_PAYMENT)
All three, when present, net into a single balanced journal entry rather
than three separate ones (derivation in the module's PHR).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import (
    ARTransactionStatus,
    PaymentPartyType,
    PaymentType,
)
from modules.accounting.exceptions import (
    AllocationExceedsOutstandingError,
    APTransactionNotFoundError,
    ARTransactionNotFoundError,
    PaymentNotFoundError,
    PostingValidationError,
)
from modules.accounting.models.ap import APTransaction
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.payments import Payment, PaymentAllocationLine
from modules.accounting.repositories.ap import APTransactionRepository
from modules.accounting.repositories.ar import ARTransactionRepository
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.payments import (
    PaymentAllocationLineRepository,
    PaymentRepository,
)
from modules.accounting.services.posting_engine import PostingEngine

_ADVANCE_TYPES = frozenset(
    {PaymentType.ADVANCE_RECEIPT.value, PaymentType.ADVANCE_PAYMENT.value}
)


@dataclass
class StagedAllocation:
    """Flush-only result of ``stage_allocation()`` (plan.md §12.3.1).
    Every write (``PaymentAllocationLine``, target-transaction outstanding/
    status, credit-transaction outstanding/status, ``payment.status=
    "ALLOCATED"``) is already flushed into the session; any staged FX-
    adjustment journal entries are held, uncommitted, in
    ``staged_entries``. Pass to ``finalize_allocation()`` to commit."""

    results: list[PaymentAllocationLine]
    staged_entries: list[tuple[Any, str, datetime]] = field(default_factory=list)


class AllocationEngine:
    """Domain service allocating a Payment's balance against AR/AP transactions."""

    def __init__(
        self,
        db: Session,
        payment_repo: PaymentRepository,
        allocation_line_repo: PaymentAllocationLineRepository,
        ar_transaction_repo: ARTransactionRepository,
        ap_transaction_repo: APTransactionRepository,
        config_repo: AccountingConfigurationRepository,
        posting_engine: PostingEngine,
    ) -> None:
        self.db = db
        self._payments = payment_repo
        self._allocation_lines = allocation_line_repo
        self._ar_transactions = ar_transaction_repo
        self._ap_transactions = ap_transaction_repo
        self._config_repo = config_repo
        self._engine = posting_engine

    def allocate(
        self,
        company_id: UUID,
        payment_id: UUID,
        allocation_lines: list[dict[str, Any]],
        actor_id: UUID | None,
    ) -> list[PaymentAllocationLine]:
        """Allocate a payment's available balance against one or more AR/AP
        transactions.

        Thin, backward-compatible wrapper of ``stage_allocation()`` +
        ``finalize_allocation()`` (plan.md §12.3.1) — identical behavior/
        return type for every existing standalone caller.

        Args:
            allocation_lines: each dict has ``transaction_id`` (UUID),
                ``amount_foreign`` (Decimal, > 0, in the transaction's own
                currency), optional ``discount_amount`` (Decimal, default 0)
                + ``discount_account_id`` (required if discount_amount > 0),
                and optional ``release_account_id`` (required when the
                payment's ``payment_type`` is ADVANCE_RECEIPT/ADVANCE_PAYMENT).
        """
        staged = self.stage_allocation(
            company_id, payment_id, allocation_lines, actor_id
        )
        return self.finalize_allocation(staged, actor_id)

    def stage_allocation(
        self,
        company_id: UUID,
        payment_id: UUID,
        allocation_lines: list[dict[str, Any]],
        actor_id: UUID | None,
    ) -> StagedAllocation:
        """Stage an allocation — flush only, no commit (plan.md §12.3.1).
        Replicates ``allocate()``'s per-line loop; every write already
        uses ``db.add()``/``db.flush()`` directly (no hidden repository
        ``.update()`` commits). Stops before the final
        ``finalize_and_publish()``/bare-commit block — call
        ``finalize_allocation()`` to commit.
        """
        payment = self._payments.get_by_id_or_none(id=payment_id, company_id=company_id)
        if payment is None:
            raise PaymentNotFoundError(payment_id=str(payment_id))
        if payment.status == "CANCELLED":
            raise PostingValidationError(
                f"Payment '{payment_id}' is cancelled and cannot be allocated."
            )

        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None:
            raise PostingValidationError(
                "Cannot allocate payment: accounting configuration is not set up for this company."
            )
        is_customer = payment.party_type == PaymentPartyType.CUSTOMER.value
        control_account_id = (
            config.default_ar_account_id
            if is_customer
            else config.default_ap_account_id
        )
        if control_account_id is None:
            raise PostingValidationError(
                "Cannot allocate payment: default AR/AP control account is not configured for this company."
            )

        credit_transaction = self._get_credit_transaction(
            company_id, is_customer, payment
        )
        is_advance = payment.payment_type in _ADVANCE_TYPES

        results: list[PaymentAllocationLine] = []
        staged_entries: list[tuple[Any, str, datetime]] = []

        for line_input in allocation_lines:
            transaction_id: UUID = line_input["transaction_id"]
            amount_foreign: Decimal = line_input["amount_foreign"]
            discount_amount: Decimal = line_input.get("discount_amount", Decimal("0"))
            discount_account_id: UUID | None = line_input.get("discount_account_id")
            release_account_id: UUID | None = line_input.get("release_account_id")

            if amount_foreign <= 0:
                raise PostingValidationError("Allocation amount must be positive.")
            if discount_amount > 0 and discount_account_id is None:
                raise PostingValidationError(
                    "discount_account_id is required when discount_amount > 0."
                )
            if is_advance and release_account_id is None:
                raise PostingValidationError(
                    "release_account_id is required when allocating an advance payment."
                )

            transaction = self._get_locked_transaction(
                company_id, is_customer, transaction_id
            )
            if transaction.currency_code != payment.currency_code:
                raise PostingValidationError(
                    "Cannot allocate: payment and transaction currencies differ "
                    f"({payment.currency_code} vs {transaction.currency_code})."
                )

            amount_base_at_booking = amount_foreign * transaction.exchange_rate
            amount_base_at_settlement = amount_foreign * payment.exchange_rate
            total_reduction = amount_base_at_booking + discount_amount

            if total_reduction > transaction.outstanding_amount:
                raise AllocationExceedsOutstandingError(
                    f"Allocation ({total_reduction}) exceeds outstanding balance "
                    f"({transaction.outstanding_amount}) on transaction '{transaction_id}'."
                )
            if amount_base_at_settlement > abs(credit_transaction.outstanding_amount):
                raise AllocationExceedsOutstandingError(
                    f"Allocation ({amount_base_at_settlement}) exceeds the payment's "
                    f"remaining available balance ({abs(credit_transaction.outstanding_amount)})."
                )

            if is_customer:
                gain_loss_amount = amount_foreign * (
                    payment.exchange_rate - transaction.exchange_rate
                )
            else:
                gain_loss_amount = amount_foreign * (
                    transaction.exchange_rate - payment.exchange_rate
                )

            entry = self._post_allocation_adjustment(
                company_id=company_id,
                payment=payment,
                is_customer=is_customer,
                control_account_id=control_account_id,
                config=config,
                discount_amount=discount_amount,
                discount_account_id=discount_account_id,
                gain_loss_amount=gain_loss_amount,
                release_amount=amount_base_at_booking if is_advance else Decimal("0"),
                release_account_id=release_account_id,
                actor_id=actor_id,
            )
            if entry is not None:
                staged_entries.append(entry)

            allocation_line = PaymentAllocationLine(
                company_id=company_id,
                payment_id=payment.id,
                ar_transaction_id=transaction_id if is_customer else None,
                ap_transaction_id=None if is_customer else transaction_id,
                allocated_amount_foreign=amount_foreign,
                allocated_amount_base=amount_base_at_settlement,
                discount_amount=discount_amount,
                gain_loss_amount=gain_loss_amount,
                gain_loss_journal_entry_id=entry[0].id if entry is not None else None,
                allocated_at=utcnow(),
                created_by=actor_id,
            )
            self.db.add(allocation_line)
            self.db.flush()

            transaction.outstanding_amount = (
                transaction.outstanding_amount - total_reduction
            )
            transaction.status = (
                ARTransactionStatus.PAID.value
                if transaction.outstanding_amount == 0
                else ARTransactionStatus.PARTIALLY_PAID.value
            )
            self.db.add(transaction)

            credit_transaction.outstanding_amount = (
                credit_transaction.outstanding_amount + amount_base_at_settlement
            )
            credit_transaction.status = (
                ARTransactionStatus.PAID.value
                if credit_transaction.outstanding_amount == 0
                else ARTransactionStatus.PARTIALLY_PAID.value
            )
            self.db.add(credit_transaction)

            results.append(allocation_line)

        payment.status = "ALLOCATED"
        self.db.add(payment)

        return StagedAllocation(results=results, staged_entries=staged_entries)

    def finalize_allocation(
        self, staged: StagedAllocation, actor_id: UUID | None
    ) -> list[PaymentAllocationLine]:
        """The sole commit point(s) for ``stage_allocation()`` — replicates
        the pre-extraction final block exactly: one ``finalize_and_publish()``
        per staged FX-adjustment entry, or a bare ``db.commit()`` if none
        were staged (plan.md §12.3.1). Every business-relevant write
        (Accounting's and the caller's) is already flushed before the
        *first* of these calls, so that first call is the true atomicity
        boundary — documented honestly, not oversimplified, per plan.md
        §12.3.1: any further calls in this loop commit an already-durable
        state and only add their own FX-adjustment entry's journal-
        numbering/event-publish bookkeeping.
        """
        if staged.staged_entries:
            for entry, journal_number, posted_at in staged.staged_entries:
                self._engine.finalize_and_publish(
                    entry, journal_number, posted_at, actor_id
                )
        else:
            self.db.commit()

        for line in staged.results:
            self.db.refresh(line)
        return staged.results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_credit_transaction(
        self, company_id: UUID, is_customer: bool, payment: Payment
    ) -> ARTransaction | APTransaction:
        repo = self._ar_transactions if is_customer else self._ap_transactions
        transaction = repo.find_by_source_document(
            company_id=company_id,
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        if transaction is None:
            raise PostingValidationError(
                f"Payment '{payment.id}' has no associated ledger credit transaction; "
                "it may not have been created via PaymentService."
            )
        locked = repo.get_by_id_locked(id=transaction.id, company_id=company_id)
        if locked is None:
            raise PostingValidationError(
                f"Payment '{payment.id}' credit transaction disappeared between lookup and lock."
            )
        return locked

    def _get_locked_transaction(
        self, company_id: UUID, is_customer: bool, transaction_id: UUID
    ) -> ARTransaction | APTransaction:
        transaction: ARTransaction | APTransaction | None
        if is_customer:
            transaction = self._ar_transactions.get_by_id_locked(
                id=transaction_id, company_id=company_id
            )
            if transaction is None:
                raise ARTransactionNotFoundError(ar_transaction_id=str(transaction_id))
        else:
            transaction = self._ap_transactions.get_by_id_locked(
                id=transaction_id, company_id=company_id
            )
            if transaction is None:
                raise APTransactionNotFoundError(ap_transaction_id=str(transaction_id))
        return transaction

    def _post_allocation_adjustment(
        self,
        company_id: UUID,
        payment: Payment,
        is_customer: bool,
        control_account_id: UUID,
        config: Any,
        discount_amount: Decimal,
        discount_account_id: UUID | None,
        gain_loss_amount: Decimal,
        release_amount: Decimal,
        release_account_id: UUID | None,
        actor_id: UUID | None,
    ) -> tuple[Any, str, datetime] | None:
        """Build and stage the single combined discount/gain-loss/advance-
        release adjustment entry for one allocation line, netting all three
        into the control account's single DR or CR leg. Returns ``None``
        (nothing to post) when discount, gain/loss, and release are all zero.

        Sign convention (DR-positive contribution to the control account),
        derived and verified against concrete examples in the module PHR:
          AR: net = -discount_amount + gain_loss_amount - release_amount
          AP: net = +discount_amount + gain_loss_amount + release_amount
        """
        if discount_amount == 0 and gain_loss_amount == 0 and release_amount == 0:
            return None

        if gain_loss_amount != 0 and (
            config.default_exchange_gain_account_id is None
            or config.default_exchange_loss_account_id is None
        ):
            raise PostingValidationError(
                "Cannot post realized FX gain/loss: default exchange gain/loss "
                "accounts are not configured for this company."
            )

        lines: list[dict[str, Decimal | UUID]] = []
        if is_customer:
            net = -discount_amount + gain_loss_amount - release_amount
        else:
            net = discount_amount + gain_loss_amount + release_amount

        if net > 0:
            lines.append(
                {
                    "account_id": control_account_id,
                    "debit_amount": net,
                    "credit_amount": Decimal("0"),
                }
            )
        elif net < 0:
            lines.append(
                {
                    "account_id": control_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": -net,
                }
            )

        if discount_amount > 0:
            assert (
                discount_account_id is not None
            )  # validated by caller — narrows type for mypy
            if is_customer:
                lines.append(
                    {
                        "account_id": discount_account_id,
                        "debit_amount": discount_amount,
                        "credit_amount": Decimal("0"),
                    }
                )
            else:
                lines.append(
                    {
                        "account_id": discount_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": discount_amount,
                    }
                )

        if gain_loss_amount > 0:
            lines.append(
                {
                    "account_id": config.default_exchange_gain_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": gain_loss_amount,
                }
            )
        elif gain_loss_amount < 0:
            lines.append(
                {
                    "account_id": config.default_exchange_loss_account_id,
                    "debit_amount": -gain_loss_amount,
                    "credit_amount": Decimal("0"),
                }
            )

        if release_amount > 0:
            assert (
                release_account_id is not None
            )  # validated by caller — narrows type for mypy
            if is_customer:
                lines.append(
                    {
                        "account_id": release_account_id,
                        "debit_amount": release_amount,
                        "credit_amount": Decimal("0"),
                    }
                )
            else:
                lines.append(
                    {
                        "account_id": release_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": release_amount,
                    }
                )

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PAYMENT",
            posting_date=payment.payment_date,
            lines=lines,
            currency_code=config.base_currency_code,
            description="Payment allocation adjustment (discount/FX/advance release)",
            source_document_type="PaymentAllocation",
            source_document_id=payment.id,
            actor_id=actor_id,
        )
        return entry, journal_number, posted_at

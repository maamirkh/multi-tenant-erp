"""AccountsReceivableService — AR subsidiary ledger management — Phase 6.

Research ref: research.md Decision 3 — no incrementing running-balance
column; ``CustomerLedger.total_outstanding_base`` is a materialized cache
recomputed from ``SUM(ar_transactions.outstanding_amount)`` on every write
in this service, never incremented/decremented in place.

Cross-module credit hold sync: ``place_credit_hold()``/``release_credit_hold()``
optionally call Sales' own ``CustomerService.update_credit()`` (Epic 7,
already-existing method: it already supports overriding ``credit_status``
directly to ``HOLD`` and already publishes Sales' own
``CustomerCreditHoldPlaced``/``Released`` events when it does — and
``CreditCheckService.evaluate_credit()`` already reads this field live to
block order approval. This is a direct cross-module service call, not a
speculative new event/subscriber — verified precedent for direct
cross-module service imports exists elsewhere in this codebase, e.g.
``modules/companies`` <-> ``modules/users_roles``). The dependency is
optional (``sales_customer_service: CustomerService | None``) so unit
tests can exercise Accounting's own ledger behavior without needing a
full Sales customer fixture; the router wires the real Sales service.

Spec ref: specs/008-accounting-finance/spec.md §18 Accounts Receivable
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import (
    ARTransactionStatus,
    CustomerCreditHistoryEventType,
)
from modules.accounting.events import get_event_bus
from modules.accounting.events.ar_events import (
    CreditHoldPlacedEvent,
    CreditHoldReleasedEvent,
    CreditLimitWarningEvent,
    InvoiceOverdueEvent,
)
from modules.accounting.exceptions import (
    ARReconciliationError,
    ARTransactionNotFoundError,
    CustomerLedgerNotFoundError,
    WriteOffNotAllowedError,
)
from modules.accounting.models.ar import (
    ARTransaction,
    CustomerCreditHistory,
    CustomerLedger,
)
from modules.accounting.models.gl import JournalEntry
from modules.accounting.repositories.ar import (
    ARPaymentAllocationRepository,
    ARTransactionRepository,
    CustomerCreditHistoryRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.posting_engine import PostingEngine, PostingResult

if TYPE_CHECKING:
    from modules.accounting.services.aging_calculator import AgingReport, AgingRow
    from modules.sales.services.customer_service import CustomerService

logger = logging.getLogger(__name__)

#: GOOD/WARNING boundary — matches Sales' own default (customer_service.py).
DEFAULT_WARNING_THRESHOLD_PCT = Decimal("80")


@dataclass
class StagedAdjustment:
    """Flush-only result of ``stage_adjustment()`` — plan.md §12.1. The
    GL entry and ``ARTransaction`` exist in the session, fully built, but
    not committed; ``CustomerLedger`` has already been recomputed
    in-session too. Pass to ``finalize_adjustment()`` to commit."""

    ar_transaction: ARTransaction
    journal_entry: JournalEntry
    journal_number: str
    posted_at: datetime


@dataclass
class StagedWriteOff:
    """Flush-only result of ``stage_write_off()`` — plan.md §12.3.3."""

    ar_transaction: ARTransaction
    journal_entry: JournalEntry
    journal_number: str
    posted_at: datetime


class AccountsReceivableService:
    """Application service for the AR subsidiary ledger."""

    def __init__(
        self,
        db: Session,
        ledger_repo: CustomerLedgerRepository,
        transaction_repo: ARTransactionRepository,
        allocation_repo: ARPaymentAllocationRepository,
        credit_history_repo: CustomerCreditHistoryRepository,
        config_repo: AccountingConfigurationRepository,
        posting_engine: PostingEngine,
        audit_service: AuditLogService,
        sales_customer_service: CustomerService | None = None,
    ) -> None:
        self.db = db
        self._ledgers = ledger_repo
        self._transactions = transaction_repo
        self._allocations = allocation_repo
        self._credit_history = credit_history_repo
        self._config_repo = config_repo
        self._engine = posting_engine
        self._audit = audit_service
        self._sales_customer_service = sales_customer_service

    @staticmethod
    def _ar_transaction_snapshot(transaction: ARTransaction) -> dict[str, Any]:
        return {
            "status": transaction.status,
            "transaction_type": transaction.transaction_type,
            "amount_base": str(transaction.amount_base),
            "outstanding_amount": str(transaction.outstanding_amount),
        }

    @staticmethod
    def _ledger_snapshot(ledger: CustomerLedger) -> dict[str, Any]:
        return {
            "credit_limit": str(ledger.credit_limit),
            "credit_status": ledger.credit_status,
            "total_outstanding_base": str(ledger.total_outstanding_base),
        }

    # ------------------------------------------------------------------
    # Ledger access
    # ------------------------------------------------------------------

    def get_or_create_ledger(
        self, company_id: UUID, customer_id: UUID
    ) -> CustomerLedger:
        """Flush only — never commits (fixed post-Phase-6-verification: the
        previous ``self._ledgers.create(...)`` call inherited
        ``BaseRepository.create()``'s internal ``db.commit()``, which
        committed a new ledger — and anything else already flushed in the
        same session — before any caller-side validation could run,
        breaking every staged/finalize method that calls this as its
        first step. Mirrors ``PaymentService._get_or_create_customer_ledger()``'s
        already-correct flush-only pattern). The caller commits together
        with the rest of its own unit of work.
        """
        ledger = self._ledgers.find_by_customer(company_id, customer_id)
        if ledger is not None:
            return ledger
        new_ledger = CustomerLedger(company_id=company_id, customer_id=customer_id)
        self.db.add(new_ledger)
        self.db.flush()
        return new_ledger

    def get_customer_ledger(
        self, company_id: UUID, customer_id: UUID
    ) -> CustomerLedger:
        ledger = self._ledgers.find_by_customer(company_id, customer_id)
        if ledger is None:
            raise CustomerLedgerNotFoundError(customer_id=str(customer_id))
        return ledger

    def get_open_transactions(
        self, company_id: UUID, customer_id: UUID
    ) -> list[ARTransaction]:
        ledger = self.get_customer_ledger(company_id, customer_id)
        return self._ledgers.get_open_transactions(company_id, ledger.id)

    def find_transaction_by_source_document(
        self, company_id: UUID, source_document_type: str, source_document_id: UUID
    ) -> ARTransaction | None:
        """Read-only lookup by originating source document — the public
        counterpart to ``ARTransactionRepository.find_by_source_document()``,
        added for external module integration gateways (e.g. Installments'
        ``AccountingIntegrationGateway``, plan.md §12) that need a live
        outstanding-amount read for a specific document without importing
        Accounting's repository layer directly."""
        return self._transactions.find_by_source_document(
            company_id, source_document_type, source_document_id
        )

    def get_transaction_by_id(
        self, company_id: UUID, ar_transaction_id: UUID
    ) -> ARTransaction | None:
        """Read-only lookup by id, returning ``None`` rather than raising —
        the public counterpart to ``_get_transaction()`` for external module
        integration gateways (e.g. Installments' ``AccountingIntegrationGateway``)
        that need to distinguish "not found" from an exception."""
        return self._transactions.get_by_id_or_none(
            id=ar_transaction_id, company_id=company_id
        )

    def sum_outstanding_by_ids(
        self, company_id: UUID, ar_transaction_ids: list[UUID]
    ) -> Decimal:
        """Bounded batch counterpart to calling ``get_transaction_by_id()``
        once per id and summing ``outstanding_amount`` for the non-
        ``WRITTEN_OFF``, positive-outstanding ones — one aggregate query
        regardless of how many ids are passed. Read-only, no commit."""
        return self._transactions.sum_outstanding_excluding_written_off(
            company_id, ar_transaction_ids
        )

    # ------------------------------------------------------------------
    # Sales integration (T141/T142) — GL posting + ARTransaction creation
    # in ONE atomic transaction, via PostingEngine's staging primitives.
    # ------------------------------------------------------------------

    def record_sales_invoice(
        self,
        company_id: UUID,
        customer_id: UUID,
        invoice_id: UUID,
        invoice_number: str,
        total_amount: Decimal,
        currency_code: str,
        transaction_date: date,
        due_date: date | None,
        actor_id: UUID | None,
    ) -> tuple[ARTransaction, PostingResult]:
        """DR AR / CR Revenue, plus a new OPEN ``ARTransaction`` — atomically.

        Raises:
            PostingValidationError: Default AR/Revenue control accounts are
                not configured for this company (see /accounting/system-accounts).
        """
        from modules.accounting.exceptions import PostingValidationError

        config = self._config_repo.get_for_company(company_id=company_id)
        if (
            config is None
            or config.default_ar_account_id is None
            or config.default_revenue_account_id is None
        ):
            raise PostingValidationError(
                "Cannot post Sales invoice to AR: default AR/Revenue control "
                "accounts are not configured for this company."
            )

        ledger = self.get_or_create_ledger(company_id, customer_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="SALES",
            posting_date=transaction_date,
            lines=[
                {
                    "account_id": config.default_ar_account_id,
                    "debit_amount": total_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": config.default_revenue_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": total_amount,
                },
            ],
            currency_code=currency_code or config.base_currency_code,
            reference=invoice_number,
            description=f"Sales invoice {invoice_number}",
            source_document_type="SalesInvoice",
            source_document_id=invoice_id,
            actor_id=actor_id,
        )

        ar_transaction = ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=transaction_date,
            due_date=due_date,
            currency_code=currency_code or config.base_currency_code,
            amount_foreign=total_amount,
            amount_base=total_amount,
            outstanding_amount=total_amount,
            status=ARTransactionStatus.OPEN.value,
            source_document_type="SalesInvoice",
            source_document_id=invoice_id,
            journal_entry_id=entry.id,
            invoice_number=invoice_number,
            created_by=actor_id,
        )
        self.db.add(ar_transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="ARTransaction",
            entity_id=ar_transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._ar_transaction_snapshot(ar_transaction),
        )

        ledger.total_outstanding_base = ledger.total_outstanding_base + total_amount
        if ledger.credit_status != "HOLD":
            ledger.credit_status = self.compute_credit_status(
                ledger.total_outstanding_base, ledger.credit_limit
            )
        self.db.add(ledger)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(ar_transaction)
        return ar_transaction, result

    def record_sales_credit_note(
        self,
        company_id: UUID,
        customer_id: UUID,
        invoice_id: UUID,
        invoice_number: str,
        credit_amount: Decimal,
        transaction_date: date,
        actor_id: UUID | None,
    ) -> tuple[ARTransaction, PostingResult]:
        """DR Revenue / CR AR, plus a new OPEN credit-note ``ARTransaction`` — atomically."""
        from modules.accounting.exceptions import PostingValidationError

        config = self._config_repo.get_for_company(company_id=company_id)
        if (
            config is None
            or config.default_ar_account_id is None
            or config.default_revenue_account_id is None
        ):
            raise PostingValidationError(
                "Cannot post Sales credit note to AR: default AR/Revenue "
                "control accounts are not configured for this company."
            )

        ledger = self.get_or_create_ledger(company_id, customer_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="SALES",
            posting_date=transaction_date,
            lines=[
                {
                    "account_id": config.default_revenue_account_id,
                    "debit_amount": credit_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": config.default_ar_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": credit_amount,
                },
            ],
            currency_code=config.base_currency_code,
            reference=invoice_number,
            description=f"Credit note against invoice {invoice_number}",
            source_document_type="SalesInvoice",
            source_document_id=invoice_id,
            actor_id=actor_id,
        )

        ar_transaction = ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type="CREDIT_NOTE",
            transaction_date=transaction_date,
            currency_code=config.base_currency_code,
            amount_foreign=credit_amount,
            amount_base=credit_amount,
            outstanding_amount=-credit_amount,
            status=ARTransactionStatus.OPEN.value,
            source_document_type="SalesInvoice",
            source_document_id=invoice_id,
            journal_entry_id=entry.id,
            invoice_number=invoice_number,
            created_by=actor_id,
        )
        self.db.add(ar_transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="ARTransaction",
            entity_id=ar_transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._ar_transaction_snapshot(ar_transaction),
        )

        ledger.total_outstanding_base = ledger.total_outstanding_base - credit_amount
        if ledger.credit_status != "HOLD":
            ledger.credit_status = self.compute_credit_status(
                ledger.total_outstanding_base, ledger.credit_limit
            )
        self.db.add(ledger)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(ar_transaction)
        return ar_transaction, result

    def get_customer_statement(
        self, company_id: UUID, customer_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        ledger = self.get_customer_ledger(company_id, customer_id)
        opening_balance = self._ledgers.get_opening_balance(
            company_id, ledger.id, from_date
        )
        transactions = self._ledgers.get_statement_data(
            company_id, ledger.id, from_date, to_date
        )
        period_movement = sum(
            (
                (
                    t.amount_base
                    if t.transaction_type in ("INVOICE", "DEBIT_NOTE")
                    else -t.amount_base
                )
                for t in transactions
            ),
            Decimal("0"),
        )
        return {
            "customer_id": customer_id,
            "from_date": from_date,
            "to_date": to_date,
            "opening_balance": opening_balance,
            "transactions": transactions,
            "closing_balance": opening_balance + period_movement,
        }

    # ------------------------------------------------------------------
    # Aging (delegates bucket math to AgingCalculator; see router wiring)
    # ------------------------------------------------------------------

    def get_customer_aging(
        self, company_id: UUID, customer_id: UUID, as_of_date: date
    ) -> AgingRow | None:
        ledger = self.get_customer_ledger(company_id, customer_id)
        report = self.get_aging_report(company_id, as_of_date)
        row = next((r for r in report.rows if r.customer_ledger_id == ledger.id), None)
        return row

    def get_aging_report(self, company_id: UUID, as_of_date: date) -> AgingReport:
        from modules.accounting.services.aging_calculator import AgingCalculator

        return AgingCalculator(self._ledgers).calculate_ar_aging(company_id, as_of_date)

    # ------------------------------------------------------------------
    # Credit management
    # ------------------------------------------------------------------

    @staticmethod
    def compute_credit_status(
        total_outstanding_base: Decimal,
        credit_limit: Decimal,
        warning_threshold_pct: Decimal = DEFAULT_WARNING_THRESHOLD_PCT,
    ) -> str:
        """GOOD (<80%) / WARNING (80-<100%) / EXCEEDED (>=100%). Never returns
        HOLD — that is always a manual override via ``place_credit_hold()``.
        """
        if credit_limit == Decimal("0"):
            return "GOOD"
        pct = (total_outstanding_base / credit_limit) * Decimal("100")
        if pct >= Decimal("100"):
            return "EXCEEDED"
        if pct >= warning_threshold_pct:
            return "WARNING"
        return "GOOD"

    def set_credit_limit(
        self,
        company_id: UUID,
        customer_id: UUID,
        credit_limit: Decimal,
        actor_id: UUID | None,
    ) -> CustomerLedger:
        ledger = self.get_or_create_ledger(company_id, customer_id)
        before = self._ledger_snapshot(ledger)
        old_limit = ledger.credit_limit
        ledger.credit_limit = credit_limit
        if ledger.credit_status != "HOLD":
            ledger.credit_status = self.compute_credit_status(
                ledger.total_outstanding_base, credit_limit
            )
        self._audit.record(
            company_id=company_id,
            entity_type="CustomerLedger",
            entity_id=ledger.id,
            action=CustomerCreditHistoryEventType.LIMIT_CHANGED.value,
            actor_id=actor_id,
            before=before,
            after=self._ledger_snapshot(ledger),
        )
        ledger = self._ledgers.update(ledger)
        self._credit_history.create(
            CustomerCreditHistory(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                event_type=CustomerCreditHistoryEventType.LIMIT_CHANGED.value,
                old_value=str(old_limit),
                new_value=str(credit_limit),
                actor_user_id=actor_id,
                occurred_at=utcnow(),
            )
        )
        return ledger

    def place_credit_hold(
        self, company_id: UUID, customer_id: UUID, reason: str, actor_id: UUID | None
    ) -> CustomerLedger:
        """Place a customer on credit hold. Idempotent if already on hold.

        Syncs to Sales' own ``Customer.credit_status`` when a Sales
        ``CustomerService`` is wired — this is what makes the hold actually
        block new sales order approvals (``CreditCheckService.evaluate_credit``
        already reads this field live; Epic 7 code, unmodified).
        """
        ledger = self.get_or_create_ledger(company_id, customer_id)
        if ledger.credit_status == "HOLD":
            return ledger

        before = self._ledger_snapshot(ledger)
        old_status = ledger.credit_status
        ledger.credit_status = "HOLD"
        ledger.credit_hold_at = utcnow()
        ledger.credit_hold_reason = reason
        ledger.credit_hold_by = actor_id
        self._audit.record(
            company_id=company_id,
            entity_type="CustomerLedger",
            entity_id=ledger.id,
            action=CustomerCreditHistoryEventType.HOLD_PLACED.value,
            actor_id=actor_id,
            before=before,
            after=self._ledger_snapshot(ledger),
            reason=reason,
        )
        ledger = self._ledgers.update(ledger)

        self._credit_history.create(
            CustomerCreditHistory(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                event_type=CustomerCreditHistoryEventType.HOLD_PLACED.value,
                old_value=old_status,
                new_value="HOLD",
                reason=reason,
                actor_user_id=actor_id,
                occurred_at=utcnow(),
            )
        )

        self._sync_credit_status_to_sales(company_id, customer_id, "HOLD", actor_id)

        get_event_bus().publish(
            CreditHoldPlacedEvent(
                event_type="accounting.ar.customer.credithold",
                aggregate_type="CustomerLedger",
                aggregate_id=ledger.id,
                company_id=company_id,
                actor_id=actor_id,
                customer_id=customer_id,
                customer_ledger_id=ledger.id,
                reason=reason,
                placed_by=actor_id,
            )
        )
        return ledger

    def release_credit_hold(
        self,
        company_id: UUID,
        customer_id: UUID,
        actor_id: UUID | None,
        reason: str | None = None,
    ) -> CustomerLedger:
        ledger = self.get_customer_ledger(company_id, customer_id)
        if ledger.credit_status != "HOLD":
            return ledger

        before = self._ledger_snapshot(ledger)
        new_status = self.compute_credit_status(
            ledger.total_outstanding_base, ledger.credit_limit
        )
        ledger.credit_status = new_status
        ledger.credit_hold_at = None
        ledger.credit_hold_reason = None
        ledger.credit_hold_by = None
        self._audit.record(
            company_id=company_id,
            entity_type="CustomerLedger",
            entity_id=ledger.id,
            action=CustomerCreditHistoryEventType.HOLD_RELEASED.value,
            actor_id=actor_id,
            before=before,
            after=self._ledger_snapshot(ledger),
            reason=reason,
        )
        ledger = self._ledgers.update(ledger)

        self._credit_history.create(
            CustomerCreditHistory(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                event_type=CustomerCreditHistoryEventType.HOLD_RELEASED.value,
                old_value="HOLD",
                new_value=new_status,
                reason=reason,
                actor_user_id=actor_id,
                occurred_at=utcnow(),
            )
        )

        self._sync_credit_status_to_sales(company_id, customer_id, new_status, actor_id)

        get_event_bus().publish(
            CreditHoldReleasedEvent(
                event_type="accounting.ar.customer.credithold.released",
                aggregate_type="CustomerLedger",
                aggregate_id=ledger.id,
                company_id=company_id,
                actor_id=actor_id,
                customer_id=customer_id,
                customer_ledger_id=ledger.id,
                new_credit_status=new_status,
                released_by=actor_id,
            )
        )
        return ledger

    def _sync_credit_status_to_sales(
        self,
        company_id: UUID,
        customer_id: UUID,
        credit_status: str,
        actor_id: UUID | None,
    ) -> None:
        if self._sales_customer_service is None:
            logger.debug(
                "AccountsReceivableService: no Sales CustomerService wired, skipping sync "
                "(customer_id=%s, credit_status=%s)",
                customer_id,
                credit_status,
            )
            return
        try:
            sales_customer = self._sales_customer_service.get_by_id(
                company_id=company_id, customer_id=customer_id
            )
            self._sales_customer_service.update_credit(
                company_id=company_id,
                customer_id=customer_id,
                credit_limit=sales_customer.credit_limit,
                credit_status=credit_status,
                actor_id=actor_id,
            )
        except Exception:  # noqa: BLE001 — sync failure must not break the Accounting-side hold
            logger.exception(
                "AccountsReceivableService: failed to sync credit_status to Sales "
                "(customer_id=%s, credit_status=%s)",
                customer_id,
                credit_status,
            )

    # ------------------------------------------------------------------
    # Adjustments
    # ------------------------------------------------------------------

    def stage_adjustment(
        self,
        company_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        contra_account_id: UUID,
        reason: str,
        posting_date: date,
        actor_id: UUID | None,
        transaction_type: str = "ADJUSTMENT",
        source_document_type: str | None = None,
        source_document_id: UUID | None = None,
    ) -> StagedAdjustment:
        """Stage an AR adjustment (dispute, discount, rounding, or — with
        ``transaction_type="DEBIT_NOTE"`` — an Installments late charge,
        plan.md §12.1) to the ledger and GL — flush only, no commit.

        ``amount`` > 0 increases the receivable (DR AR / CR contra);
        ``amount`` < 0 decreases it (DR contra / CR AR).

        The caller may stage further writes into the same session (e.g.
        an ``InstallmentLateCharge`` row) before calling
        ``finalize_adjustment()``, which performs the sole commit for
        everything staged since this call (plan.md §12.2's general
        commit-ownership contract for cross-module Accounting calls).
        """
        ledger = self.get_or_create_ledger(company_id, customer_id)
        config = self._config_repo.get_for_company(company_id=company_id)
        ar_account_id = config.default_ar_account_id if config else None
        if ar_account_id is None:
            from modules.accounting.exceptions import PostingValidationError

            raise PostingValidationError(
                "Cannot post AR adjustment: default AR control account is not "
                "configured for this company."
            )

        abs_amount = abs(amount)
        if amount >= 0:
            lines = [
                {
                    "account_id": ar_account_id,
                    "debit_amount": abs_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": contra_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": abs_amount,
                },
            ]
        else:
            lines = [
                {
                    "account_id": contra_account_id,
                    "debit_amount": abs_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ar_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": abs_amount,
                },
            ]

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="ADJUSTING",
            posting_source="MANUAL",
            posting_date=posting_date,
            lines=lines,
            currency_code=config.base_currency_code if config else "USD",
            description=f"AR adjustment: {reason}",
            source_document_type=source_document_type or "ARAdjustment",
            source_document_id=source_document_id or ledger.id,
            actor_id=actor_id,
        )

        transaction = ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type=transaction_type,
            transaction_date=posting_date,
            currency_code=config.base_currency_code if config else "USD",
            amount_foreign=amount,
            amount_base=amount,
            outstanding_amount=amount,
            status=ARTransactionStatus.OPEN.value,
            journal_entry_id=entry.id,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="ARTransaction",
            entity_id=transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._ar_transaction_snapshot(transaction),
            reason=reason,
        )
        self._recompute_ledger_balance_staged(company_id, ledger.id)
        return StagedAdjustment(
            ar_transaction=transaction,
            journal_entry=entry,
            journal_number=journal_number,
            posted_at=posted_at,
        )

    def finalize_adjustment(
        self, staged: StagedAdjustment, actor_id: UUID | None
    ) -> ARTransaction:
        """The sole commit point for ``stage_adjustment()`` — thin
        wrapper over ``PostingEngine.finalize_and_publish()`` (plan.md
        §12.1). No new business logic."""
        self._engine.finalize_and_publish(
            staged.journal_entry, staged.journal_number, staged.posted_at, actor_id
        )
        self.db.refresh(staged.ar_transaction)
        return staged.ar_transaction

    def adjust_receivable(
        self,
        company_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        contra_account_id: UUID,
        reason: str,
        posting_date: date,
        actor_id: UUID | None,
    ) -> ARTransaction:
        """Post an AR adjustment (dispute, discount, rounding) to the ledger and GL.

        Thin, 100%-backward-compatible wrapper of ``stage_adjustment()``
        + ``finalize_adjustment()`` (plan.md §12.1) — identical behavior,
        return type, and single-call ergonomics as before this change.
        """
        staged = self.stage_adjustment(
            company_id=company_id,
            customer_id=customer_id,
            amount=amount,
            contra_account_id=contra_account_id,
            reason=reason,
            posting_date=posting_date,
            actor_id=actor_id,
        )
        return self.finalize_adjustment(staged, actor_id)

    def reverse_adjustment(
        self,
        company_id: UUID,
        ar_transaction_id: UUID,
        reason: str,
        actor_id: UUID | None,
    ) -> ARTransaction:
        """Reverse a previously-posted AR adjustment (plan.md §12.1) —
        modeled directly on ``PaymentService.cancel_payment()``'s
        stage-then-``PostingEngine.reverse()`` pattern.

        Zeroes ``outstanding_amount`` and recomputes the ledger (both
        flush-only), then calls ``PostingEngine.reverse()``, whose single
        commit covers both the reversal journal and everything staged
        above it in this same session — including anything the caller
        staged before calling this method (e.g. an Installments late-
        charge waiver row, plan.md §12.2's Waiver row).
        """
        transaction = self._get_transaction(company_id, ar_transaction_id)
        ledger = self._ledgers.get_by_id(
            id=transaction.customer_ledger_id, company_id=company_id
        )
        if transaction.journal_entry_id is None:
            from modules.accounting.exceptions import PostingValidationError

            raise PostingValidationError(
                f"AR transaction '{ar_transaction_id}' has no associated "
                "journal entry to reverse."
            )

        before = self._ar_transaction_snapshot(transaction)
        transaction.outstanding_amount = Decimal("0")
        transaction.status = ARTransactionStatus.PAID.value
        self.db.add(transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="ARTransaction",
            entity_id=transaction.id,
            action="REVERSED",
            actor_id=actor_id,
            before=before,
            after=self._ar_transaction_snapshot(transaction),
            reason=reason,
        )
        self._recompute_ledger_balance_staged(company_id, ledger.id)

        self._engine.reverse(
            company_id=company_id,
            journal_id=transaction.journal_entry_id,
            actor_id=actor_id,
            reason=reason,
        )
        self.db.refresh(transaction)
        return transaction

    # ------------------------------------------------------------------
    # Write-off (spec.md §18.9)
    # ------------------------------------------------------------------

    def initiate_write_off(
        self,
        company_id: UUID,
        ar_transaction_id: UUID,
        reason: str,
        actor_id: UUID | None,
    ) -> ARTransaction:
        """Validate a write-off request. Pure validation — no state change.

        The single ``POST /ar/transactions/{id}/write-off`` endpoint (T145)
        calls ``confirm_write_off()`` directly; this method exists as the
        service-layer capability T137 names, ready for a future two-step
        API (separate initiate/confirm HTTP calls) if that becomes required.
        """
        transaction = self._get_transaction(company_id, ar_transaction_id)
        if transaction.status in (
            ARTransactionStatus.PAID.value,
            ARTransactionStatus.WRITTEN_OFF.value,
        ):
            raise WriteOffNotAllowedError(str(ar_transaction_id), transaction.status)
        return transaction

    def confirm_write_off(
        self,
        company_id: UUID,
        ar_transaction_id: UUID,
        reason: str,
        actor_id: UUID | None,
    ) -> ARTransaction:
        """Execute the write-off: zero the outstanding balance, mark WRITTEN_OFF,
        and post DR Bad Debt Expense / CR AR to the GL.

        Thin, 100%-backward-compatible wrapper of ``stage_write_off()`` +
        ``finalize_write_off()`` (plan.md §12.3.3) — identical behavior,
        return type, and single-call ergonomics as before this change.

        Reversible in principle via the standard journal-reversal mechanism
        (Phase 4/5 ``PostingEngine.reverse()``) on the write-off's own
        journal entry — restoring the ARTransaction's OPEN status on
        recovery is a manual follow-up step, not automated in this phase.
        """
        staged = self.stage_write_off(company_id, ar_transaction_id, reason, actor_id)
        return self.finalize_write_off(staged, actor_id)

    def stage_write_off(
        self,
        company_id: UUID,
        ar_transaction_id: UUID,
        reason: str,
        actor_id: UUID | None,
    ) -> StagedWriteOff:
        """Stage a write-off — flush only, no commit (plan.md §12.3.3).

        Fixes the pre-existing three-separate-commit defect: the original
        ``confirm_write_off()`` called ``post_direct()`` (commits
        immediately), then ``self._transactions.update()`` (a **second**
        commit — ``BaseRepository.update()`` commits internally), then
        ``self._recompute_ledger_balance()`` → ``self._ledgers.update()``
        (a **third** commit). This method performs the equivalent work
        entirely via ``flush()``: ``stage_direct_posting()`` for the GL
        entry, ``db.add()``+``db.flush()`` directly for the transaction's
        status/outstanding-amount change (never ``self._transactions.
        update()``), and the ledger recompute inlined the same way (never
        ``self._ledgers.update()``).
        """
        transaction = self.initiate_write_off(
            company_id, ar_transaction_id, reason, actor_id
        )
        ledger = self._ledgers.get_by_id(
            id=transaction.customer_ledger_id, company_id=company_id
        )

        config = self._config_repo.get_for_company(company_id=company_id)
        ar_account_id = config.default_ar_account_id if config else None
        bad_debt_account_id = config.default_bad_debt_account_id if config else None
        if ar_account_id is None or bad_debt_account_id is None:
            from modules.accounting.exceptions import PostingValidationError

            raise PostingValidationError(
                "Cannot post write-off: default AR/Bad Debt control accounts "
                "are not configured for this company."
            )

        write_off_amount = transaction.outstanding_amount
        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=utcnow().date(),
            lines=[
                {
                    "account_id": bad_debt_account_id,
                    "debit_amount": write_off_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ar_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": write_off_amount,
                },
            ],
            currency_code=transaction.currency_code,
            description=f"Write-off: {reason}",
            source_document_type="ARTransaction",
            source_document_id=transaction.id,
            actor_id=actor_id,
        )

        before = self._ar_transaction_snapshot(transaction)
        transaction.status = ARTransactionStatus.WRITTEN_OFF.value
        transaction.outstanding_amount = Decimal("0")
        self.db.add(transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="ARTransaction",
            entity_id=transaction.id,
            action="WRITTEN_OFF",
            actor_id=actor_id,
            before=before,
            after=self._ar_transaction_snapshot(transaction),
            reason=reason,
        )
        self._recompute_ledger_balance_staged(company_id, ledger.id)

        return StagedWriteOff(
            ar_transaction=transaction,
            journal_entry=entry,
            journal_number=journal_number,
            posted_at=posted_at,
        )

    def finalize_write_off(
        self, staged: StagedWriteOff, actor_id: UUID | None
    ) -> ARTransaction:
        """The sole commit point for ``stage_write_off()`` — thin wrapper
        over ``PostingEngine.finalize_and_publish()``, committing the GL
        entry, the transaction status/outstanding change, and the ledger
        recompute together (plan.md §12.3.3)."""
        self._engine.finalize_and_publish(
            staged.journal_entry, staged.journal_number, staged.posted_at, actor_id
        )
        self.db.refresh(staged.ar_transaction)
        return staged.ar_transaction

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_transaction(
        self, company_id: UUID, ar_transaction_id: UUID
    ) -> ARTransaction:
        transaction = self._transactions.get_by_id_or_none(
            id=ar_transaction_id, company_id=company_id
        )
        if transaction is None:
            raise ARTransactionNotFoundError(ar_transaction_id=str(ar_transaction_id))
        return transaction

    def _recompute_ledger_balance_staged(
        self, company_id: UUID, customer_ledger_id: UUID
    ) -> CustomerLedger:
        """Recompute ``total_outstanding_base`` from the transactions table
        (never incremented/decremented in place — research.md Decision 3)
        and re-derive ``credit_status`` (unless manually on HOLD) —
        flush only, never ``self._ledgers.update()`` (which commits
        internally, ``core/repositories/base.py:92-106`` — exactly the
        extra commit plan.md §12.3.3 requires eliminating).
        """
        ledger = self._ledgers.get_by_id(id=customer_ledger_id, company_id=company_id)
        open_transactions = self._ledgers.get_open_transactions(company_id, ledger.id)
        ledger.total_outstanding_base = sum(
            (t.outstanding_amount for t in open_transactions), Decimal("0")
        )
        if ledger.credit_status != "HOLD":
            ledger.credit_status = self.compute_credit_status(
                ledger.total_outstanding_base, ledger.credit_limit
            )
        self.db.add(ledger)
        self.db.flush()
        return ledger

    # ------------------------------------------------------------------
    # Reconciliation (T140) — financial-integrity backstop
    # ------------------------------------------------------------------

    def reconcile_ar_control_account(self, company_id: UUID) -> Decimal:
        """Assert ``SUM(open ARTransaction.outstanding_amount) == GL AR control
        account balance`` for this company. Returns the (equal) balance on
        success; raises :class:`ARReconciliationError` on mismatch.

        Called from integration tests after every AR posting (T140) — a
        deliberately loud financial-integrity backstop, not swallowed or
        logged-and-continued, since a mismatch here means the AR subsidiary
        ledger and the GL have diverged.
        """
        from modules.accounting.exceptions import PostingValidationError
        from modules.accounting.repositories.gl import GLReportRepository

        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None or config.default_ar_account_id is None:
            raise PostingValidationError(
                "Cannot reconcile AR: default AR control account is not "
                "configured for this company."
            )

        ar_sum = Decimal("0")
        for ledger in self._ledgers.list_all(company_id):
            open_transactions = self._ledgers.get_open_transactions(
                company_id, ledger.id
            )
            ar_sum += sum(
                (t.outstanding_amount for t in open_transactions), Decimal("0")
            )

        gl_report_repo = GLReportRepository(self.db)
        balances = gl_report_repo.account_balance_query(
            company_id=company_id, account_id=config.default_ar_account_id
        )
        gl_balance = balances["total_debit"] - balances["total_credit"]

        if ar_sum != gl_balance:
            raise ARReconciliationError(
                ar_ledger_sum=str(ar_sum), gl_balance=str(gl_balance)
            )
        return ar_sum

    # ------------------------------------------------------------------
    # Overdue check (T143) — daily APScheduler job's AR half
    # ------------------------------------------------------------------

    def run_overdue_check(
        self,
        as_of_date: date,
        warning_threshold_pct: Decimal = DEFAULT_WARNING_THRESHOLD_PCT,
    ) -> dict[str, int]:
        """Cross-tenant daily job: mark past-due transactions OVERDUE and
        publish warning events. Mirrors ``RecurringJournalService.
        execute_due_templates()``'s cross-tenant scan pattern (Phase 5).

        Returns a summary count dict for logging by the scheduler wrapper.
        """
        bus = get_event_bus()
        overdue_count = 0
        warning_count = 0

        overdue_transactions = self._transactions.find_overdue_across_companies(
            as_of_date
        )
        for transaction in overdue_transactions:
            transaction.status = ARTransactionStatus.OVERDUE.value
            self._transactions.update(transaction)
            overdue_count += 1

            ledger = self._ledgers.get_by_id(
                id=transaction.customer_ledger_id, company_id=transaction.company_id
            )
            bus.publish(
                InvoiceOverdueEvent(
                    event_type="accounting.ar.invoice.overdue",
                    aggregate_type="ARTransaction",
                    aggregate_id=transaction.id,
                    company_id=transaction.company_id,
                    actor_id=None,
                    ar_transaction_id=transaction.id,
                    customer_id=ledger.customer_id,
                    invoice_number=transaction.invoice_number,
                    due_date=(
                        transaction.due_date.isoformat()
                        if transaction.due_date
                        else None
                    ),
                    outstanding_amount=transaction.outstanding_amount,
                )
            )

        ledgers_to_check = self._ledgers.find_all_not_on_hold_across_companies()
        for ledger in ledgers_to_check:
            pct = (ledger.total_outstanding_base / ledger.credit_limit) * Decimal("100")
            if pct >= warning_threshold_pct:
                warning_count += 1
                bus.publish(
                    CreditLimitWarningEvent(
                        event_type="accounting.ar.customer.creditlimit.warning",
                        aggregate_type="CustomerLedger",
                        aggregate_id=ledger.id,
                        company_id=ledger.company_id,
                        actor_id=None,
                        customer_id=ledger.customer_id,
                        customer_ledger_id=ledger.id,
                        credit_limit=ledger.credit_limit,
                        total_outstanding_base=ledger.total_outstanding_base,
                        utilization_pct=pct,
                    )
                )

        return {"overdue_count": overdue_count, "warning_count": warning_count}

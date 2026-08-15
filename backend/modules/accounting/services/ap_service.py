"""AccountsPayableService — AP subsidiary ledger management — Phase 7.

Mirrors ``ar_service.py``'s design (research.md Decision 3 — no incrementing
running-balance column; ``SupplierLedger.total_outstanding_base`` is a
materialized cache recomputed from ``SUM(ap_transactions.outstanding_amount)``
on every write, never incremented/decremented in place).

Bill capture — no live Purchase event to wire:
    Phase 0 verification (quickstart.md "Phase 0 Verification Findings")
    confirmed Purchase (Epic 6) has no Bill/Invoice/AP entity or event at
    all — spec 006 §60.2 explicitly defers Invoice Processing/Three-Way
    Matching/Accounts Payable to Epic 8's own future scope. Unlike Phase 6's
    AR integration (where Sales' real ``sales.invoice.issued`` event exists
    and is wired directly), there is no ``purchase.bill.posted`` producer to
    subscribe to — the already-resolved plan (ADR-0004 / quickstart.md) is
    that "Accounts Payable bill capture [is] built inside Accounting itself"
    (i.e. this service, called directly — by a manual-entry API endpoint
    today, and by a real Purchase event once/if Epic 6 ever adds a Bill
    concept). ``record_supplier_bill()``/``record_supplier_credit_note()``
    below are that capture point — structurally identical to ``ar_service.
    py``'s ``record_sales_invoice()``/``record_sales_credit_note()``, using
    the same ``PostingEngine.stage_direct_posting()`` + ``finalize_and_
    publish()`` atomicity between the GL entry and the APTransaction/
    SupplierLedger write.

Spec ref: specs/008-accounting-finance/spec.md §19 Accounts Payable
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.constants import APTransactionStatus, ReconciliationMatchStatus
from modules.accounting.events import get_event_bus
from modules.accounting.events.ap_events import BillDueEvent
from modules.accounting.exceptions import (
    APReconciliationError,
    APTransactionNotFoundError,
    SupplierLedgerNotFoundError,
    SupplierReconciliationNotFoundError,
)
from modules.accounting.models.ap import (
    APTransaction,
    SupplierLedger,
    SupplierStatementReconciliation,
    SupplierStatementReconciliationItem,
)
from modules.accounting.repositories.ap import (
    APPaymentAllocationRepository,
    APTransactionRepository,
    SupplierLedgerRepository,
    SupplierStatementReconciliationItemRepository,
    SupplierStatementReconciliationRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.posting_engine import PostingEngine, PostingResult

if TYPE_CHECKING:
    from modules.accounting.services.aging_calculator import APAgingReport, APAgingRow

#: Default lookahead window for the bill-due-reminder job (T166).
DEFAULT_BILL_DUE_REMINDER_DAYS = 7


class AccountsPayableService:
    """Application service for the AP subsidiary ledger."""

    def __init__(
        self,
        db: Session,
        ledger_repo: SupplierLedgerRepository,
        transaction_repo: APTransactionRepository,
        allocation_repo: APPaymentAllocationRepository,
        reconciliation_repo: SupplierStatementReconciliationRepository,
        reconciliation_item_repo: SupplierStatementReconciliationItemRepository,
        config_repo: AccountingConfigurationRepository,
        posting_engine: PostingEngine,
        audit_service: AuditLogService,
    ) -> None:
        self.db = db
        self._ledgers = ledger_repo
        self._transactions = transaction_repo
        self._allocations = allocation_repo
        self._reconciliations = reconciliation_repo
        self._reconciliation_items = reconciliation_item_repo
        self._config_repo = config_repo
        self._engine = posting_engine
        self._audit = audit_service

    @staticmethod
    def _ap_transaction_snapshot(transaction: APTransaction) -> dict[str, Any]:
        return {
            "status": transaction.status,
            "transaction_type": transaction.transaction_type,
            "amount_base": str(transaction.amount_base),
            "outstanding_amount": str(transaction.outstanding_amount),
        }

    @staticmethod
    def _reconciliation_snapshot(
        reconciliation: SupplierStatementReconciliation,
    ) -> dict[str, Any]:
        return {
            "status": reconciliation.status,
            "statement_total": str(reconciliation.statement_total),
        }

    # ------------------------------------------------------------------
    # Ledger access
    # ------------------------------------------------------------------

    def get_or_create_ledger(
        self, company_id: UUID, supplier_id: UUID
    ) -> SupplierLedger:
        ledger = self._ledgers.find_by_supplier(company_id, supplier_id)
        if ledger is not None:
            return ledger
        return self._ledgers.create(
            SupplierLedger(company_id=company_id, supplier_id=supplier_id)
        )

    def get_supplier_ledger(
        self, company_id: UUID, supplier_id: UUID
    ) -> SupplierLedger:
        ledger = self._ledgers.find_by_supplier(company_id, supplier_id)
        if ledger is None:
            raise SupplierLedgerNotFoundError(supplier_id=str(supplier_id))
        return ledger

    def get_open_transactions(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[APTransaction]:
        ledger = self.get_supplier_ledger(company_id, supplier_id)
        return self._ledgers.get_open_transactions(company_id, ledger.id)

    # ------------------------------------------------------------------
    # Bill / credit note capture (T162 extension) — GL posting +
    # APTransaction creation in ONE atomic transaction, via PostingEngine's
    # staging primitives. See module docstring for why this is manual-entry
    # rather than an inbound event handler.
    # ------------------------------------------------------------------

    def record_supplier_bill(
        self,
        company_id: UUID,
        supplier_id: UUID,
        bill_id: UUID,
        bill_number: str,
        total_amount: Decimal,
        currency_code: str,
        transaction_date: date,
        due_date: date | None,
        actor_id: UUID | None,
    ) -> tuple[APTransaction, PostingResult]:
        """DR Expense / CR AP, plus a new OPEN ``APTransaction`` — atomically.

        No tax-line split — same limitation as AR's ``record_sales_invoice()``
        (no tax breakdown available in this phase's inputs); full net amount
        posts to the default expense control account.

        Raises:
            PostingValidationError: Default AP/Expense control accounts are
                not configured for this company (see /accounting/system-accounts).
        """
        from modules.accounting.exceptions import PostingValidationError

        config = self._config_repo.get_for_company(company_id=company_id)
        if (
            config is None
            or config.default_ap_account_id is None
            or config.default_expense_account_id is None
        ):
            raise PostingValidationError(
                "Cannot post supplier bill to AP: default AP/Expense control "
                "accounts are not configured for this company."
            )

        ledger = self.get_or_create_ledger(company_id, supplier_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PURCHASE",
            posting_date=transaction_date,
            lines=[
                {
                    "account_id": config.default_expense_account_id,
                    "debit_amount": total_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": config.default_ap_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": total_amount,
                },
            ],
            currency_code=currency_code or config.base_currency_code,
            reference=bill_number,
            description=f"Supplier bill {bill_number}",
            source_document_type="PurchaseBill",
            source_document_id=bill_id,
            actor_id=actor_id,
        )

        ap_transaction = APTransaction(
            company_id=company_id,
            supplier_ledger_id=ledger.id,
            transaction_type="BILL",
            transaction_date=transaction_date,
            due_date=due_date,
            currency_code=currency_code or config.base_currency_code,
            amount_foreign=total_amount,
            amount_base=total_amount,
            outstanding_amount=total_amount,
            status=APTransactionStatus.OPEN.value,
            source_document_type="PurchaseBill",
            source_document_id=bill_id,
            journal_entry_id=entry.id,
            bill_number=bill_number,
            created_by=actor_id,
        )
        self.db.add(ap_transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="APTransaction",
            entity_id=ap_transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._ap_transaction_snapshot(ap_transaction),
        )

        ledger.total_outstanding_base = ledger.total_outstanding_base + total_amount
        self.db.add(ledger)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(ap_transaction)
        return ap_transaction, result

    def record_supplier_credit_note(
        self,
        company_id: UUID,
        supplier_id: UUID,
        bill_id: UUID,
        bill_number: str,
        credit_amount: Decimal,
        transaction_date: date,
        actor_id: UUID | None,
    ) -> tuple[APTransaction, PostingResult]:
        """DR AP / CR Expense, plus a new OPEN credit-note ``APTransaction`` — atomically."""
        from modules.accounting.exceptions import PostingValidationError

        config = self._config_repo.get_for_company(company_id=company_id)
        if (
            config is None
            or config.default_ap_account_id is None
            or config.default_expense_account_id is None
        ):
            raise PostingValidationError(
                "Cannot post supplier credit note to AP: default AP/Expense "
                "control accounts are not configured for this company."
            )

        ledger = self.get_or_create_ledger(company_id, supplier_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PURCHASE",
            posting_date=transaction_date,
            lines=[
                {
                    "account_id": config.default_ap_account_id,
                    "debit_amount": credit_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": config.default_expense_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": credit_amount,
                },
            ],
            currency_code=config.base_currency_code,
            reference=bill_number,
            description=f"Credit note against bill {bill_number}",
            source_document_type="PurchaseBill",
            source_document_id=bill_id,
            actor_id=actor_id,
        )

        ap_transaction = APTransaction(
            company_id=company_id,
            supplier_ledger_id=ledger.id,
            transaction_type="CREDIT_NOTE",
            transaction_date=transaction_date,
            currency_code=config.base_currency_code,
            amount_foreign=credit_amount,
            amount_base=credit_amount,
            outstanding_amount=-credit_amount,
            status=APTransactionStatus.OPEN.value,
            source_document_type="PurchaseBill",
            source_document_id=bill_id,
            journal_entry_id=entry.id,
            bill_number=bill_number,
            created_by=actor_id,
        )
        self.db.add(ap_transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="APTransaction",
            entity_id=ap_transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._ap_transaction_snapshot(ap_transaction),
        )

        ledger.total_outstanding_base = ledger.total_outstanding_base - credit_amount
        self.db.add(ledger)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(ap_transaction)
        return ap_transaction, result

    def get_supplier_statement(
        self, company_id: UUID, supplier_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        ledger = self.get_supplier_ledger(company_id, supplier_id)
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
                    if t.transaction_type in ("BILL", "DEBIT_NOTE")
                    else -t.amount_base
                )
                for t in transactions
            ),
            Decimal("0"),
        )
        return {
            "supplier_id": supplier_id,
            "from_date": from_date,
            "to_date": to_date,
            "opening_balance": opening_balance,
            "transactions": transactions,
            "closing_balance": opening_balance + period_movement,
        }

    # ------------------------------------------------------------------
    # Aging
    # ------------------------------------------------------------------

    def get_supplier_aging(
        self, company_id: UUID, supplier_id: UUID, as_of_date: date
    ) -> APAgingRow | None:
        ledger = self.get_supplier_ledger(company_id, supplier_id)
        report = self.get_aging_report(company_id, as_of_date)
        row = next((r for r in report.rows if r.supplier_ledger_id == ledger.id), None)
        return row

    def get_aging_report(self, company_id: UUID, as_of_date: date) -> APAgingReport:
        from modules.accounting.services.aging_calculator import APAgingCalculator

        return APAgingCalculator(self._ledgers).calculate_ap_aging(
            company_id, as_of_date
        )

    # ------------------------------------------------------------------
    # Adjustments
    # ------------------------------------------------------------------

    def adjust_payable(
        self,
        company_id: UUID,
        supplier_id: UUID,
        amount: Decimal,
        contra_account_id: UUID,
        reason: str,
        posting_date: date,
        actor_id: UUID | None,
    ) -> APTransaction:
        """Post an AP adjustment (early-payment discount, dispute, rounding)
        to the ledger and GL.

        ``amount`` > 0 increases the payable (DR contra / CR AP);
        ``amount`` < 0 decreases it (DR AP / CR contra).
        """
        ledger = self.get_or_create_ledger(company_id, supplier_id)
        config = self._config_repo.get_for_company(company_id=company_id)
        ap_account_id = config.default_ap_account_id if config else None
        if ap_account_id is None:
            from modules.accounting.exceptions import PostingValidationError

            raise PostingValidationError(
                "Cannot post AP adjustment: default AP control account is not "
                "configured for this company."
            )

        abs_amount = abs(amount)
        if amount >= 0:
            lines = [
                {
                    "account_id": contra_account_id,
                    "debit_amount": abs_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ap_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": abs_amount,
                },
            ]
        else:
            lines = [
                {
                    "account_id": ap_account_id,
                    "debit_amount": abs_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": contra_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": abs_amount,
                },
            ]

        result = self._engine.post_direct(
            company_id=company_id,
            journal_type="ADJUSTING",
            posting_source="MANUAL",
            posting_date=posting_date,
            lines=lines,
            currency_code=config.base_currency_code if config else "USD",
            description=f"AP adjustment: {reason}",
            source_document_type="APAdjustment",
            source_document_id=ledger.id,
            actor_id=actor_id,
        )

        transaction = APTransaction(
            company_id=company_id,
            supplier_ledger_id=ledger.id,
            transaction_type="ADJUSTMENT",
            transaction_date=posting_date,
            currency_code=config.base_currency_code if config else "USD",
            amount_foreign=amount,
            amount_base=amount,
            outstanding_amount=amount,
            status=APTransactionStatus.OPEN.value,
            journal_entry_id=result.journal_entry_id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="APTransaction",
            entity_id=transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._ap_transaction_snapshot(transaction),
            reason=reason,
        )
        transaction = self._transactions.create(transaction)
        self._recompute_ledger_balance(company_id, ledger.id)
        return transaction

    # ------------------------------------------------------------------
    # Supplier statement reconciliation (T162, spec.md §19.6) — statement-
    # first pattern (research.md Decision 6, applied to AP)
    # ------------------------------------------------------------------

    def reconcile_supplier_statement(
        self,
        company_id: UUID,
        supplier_id: UUID,
        statement_date: date,
        statement_total: Decimal,
        statement_lines: list[dict[str, Any]],
        actor_id: UUID | None,
    ) -> SupplierStatementReconciliation:
        """Match supplier statement lines against open ``APTransaction``s.

        ``statement_lines``: list of ``{"reference": str, "amount": Decimal}``.
        Matching is by exact outstanding-amount equality (first-available,
        greedy) — sufficient for the common case of one bill per statement
        line; disputes/timing differences remain ``UNMATCHED_*`` for manual
        follow-up (spec.md §19.6's documented resolution workflow), not
        auto-resolved here.
        """
        ledger = self.get_or_create_ledger(company_id, supplier_id)
        open_transactions = list(
            self._ledgers.get_open_transactions(company_id, ledger.id)
        )

        reconciliation = self._reconciliations.create(
            SupplierStatementReconciliation(
                company_id=company_id,
                supplier_id=supplier_id,
                statement_date=statement_date,
                statement_total=statement_total,
                status="IN_PROGRESS",
                created_by=actor_id,
            )
        )

        matched_transaction_ids: set[UUID] = set()
        any_unmatched = False

        for line in statement_lines:
            line_amount = Decimal(str(line["amount"]))
            match = next(
                (
                    t
                    for t in open_transactions
                    if t.id not in matched_transaction_ids
                    and t.outstanding_amount == line_amount
                ),
                None,
            )
            if match is not None:
                matched_transaction_ids.add(match.id)
                self._reconciliation_items.create(
                    SupplierStatementReconciliationItem(
                        company_id=company_id,
                        reconciliation_id=reconciliation.id,
                        ap_transaction_id=match.id,
                        statement_line_reference=line.get("reference"),
                        statement_amount=line_amount,
                        gl_amount=match.outstanding_amount,
                        match_status=ReconciliationMatchStatus.MATCHED.value,
                        difference=Decimal("0"),
                    )
                )
            else:
                any_unmatched = True
                self._reconciliation_items.create(
                    SupplierStatementReconciliationItem(
                        company_id=company_id,
                        reconciliation_id=reconciliation.id,
                        ap_transaction_id=None,
                        statement_line_reference=line.get("reference"),
                        statement_amount=line_amount,
                        gl_amount=None,
                        match_status=ReconciliationMatchStatus.UNMATCHED_STATEMENT.value,
                        difference=line_amount,
                    )
                )

        for txn in open_transactions:
            if txn.id in matched_transaction_ids:
                continue
            any_unmatched = True
            self._reconciliation_items.create(
                SupplierStatementReconciliationItem(
                    company_id=company_id,
                    reconciliation_id=reconciliation.id,
                    ap_transaction_id=txn.id,
                    statement_line_reference=None,
                    statement_amount=None,
                    gl_amount=txn.outstanding_amount,
                    match_status=ReconciliationMatchStatus.UNMATCHED_GL.value,
                    difference=-txn.outstanding_amount,
                )
            )

        before = self._reconciliation_snapshot(reconciliation)
        reconciliation.status = "IN_PROGRESS" if any_unmatched else "COMPLETED"
        self._audit.record(
            company_id=company_id,
            entity_type="SupplierStatementReconciliation",
            entity_id=reconciliation.id,
            action="CREATED",
            actor_id=actor_id,
            before=before,
            after=self._reconciliation_snapshot(reconciliation),
        )
        return self._reconciliations.update(reconciliation)

    def get_reconciliation_items(
        self, company_id: UUID, reconciliation_id: UUID
    ) -> list[SupplierStatementReconciliationItem]:
        reconciliation = self._reconciliations.get_by_id_or_none(
            id=reconciliation_id, company_id=company_id
        )
        if reconciliation is None:
            raise SupplierReconciliationNotFoundError(
                reconciliation_id=str(reconciliation_id)
            )
        return self._reconciliation_items.find_by_reconciliation(
            company_id, reconciliation_id
        )

    # ------------------------------------------------------------------
    # Remittance advice (T162) — built from allocation rows sharing a
    # payment_id; returns empty until Phase 9 populates APPaymentAllocation
    # (no Payment entity exists yet), mirroring AR's identical deferral.
    # ------------------------------------------------------------------

    def generate_remittance_advice(
        self, company_id: UUID, payment_id: UUID
    ) -> dict[str, Any]:
        allocations = self._allocations.find_by_payment(company_id, payment_id)
        lines = []
        total_paid = Decimal("0")
        for allocation in allocations:
            transaction = self._transactions.get_by_id_or_none(
                id=allocation.ap_transaction_id, company_id=company_id
            )
            lines.append(
                {
                    "bill_number": transaction.bill_number if transaction else None,
                    "ap_transaction_id": allocation.ap_transaction_id,
                    "allocated_amount_base": allocation.allocated_amount_base,
                    "discount_amount": allocation.discount_amount,
                }
            )
            total_paid += allocation.allocated_amount_base
        return {
            "payment_id": payment_id,
            "lines": lines,
            "total_paid": total_paid,
        }

    # ------------------------------------------------------------------
    # Reconciliation (T165) — financial-integrity backstop, mirrors AR's T140
    # ------------------------------------------------------------------

    def reconcile_ap_control_account(self, company_id: UUID) -> Decimal:
        """Assert ``SUM(open APTransaction.outstanding_amount) == GL AP
        control account balance`` for this company. Returns the (equal)
        balance on success; raises :class:`APReconciliationError` on
        mismatch.
        """
        from modules.accounting.exceptions import PostingValidationError
        from modules.accounting.repositories.gl import GLReportRepository

        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None or config.default_ap_account_id is None:
            raise PostingValidationError(
                "Cannot reconcile AP: default AP control account is not "
                "configured for this company."
            )

        ap_sum = Decimal("0")
        for ledger in self._ledgers.list_all(company_id):
            open_transactions = self._ledgers.get_open_transactions(
                company_id, ledger.id
            )
            ap_sum += sum(
                (t.outstanding_amount for t in open_transactions), Decimal("0")
            )

        gl_report_repo = GLReportRepository(self.db)
        balances = gl_report_repo.account_balance_query(
            company_id=company_id, account_id=config.default_ap_account_id
        )
        # AP is a liability (credit-normal) — outstanding balance is CR - DR.
        gl_balance = balances["total_credit"] - balances["total_debit"]

        if ap_sum != gl_balance:
            raise APReconciliationError(
                ap_ledger_sum=str(ap_sum), gl_balance=str(gl_balance)
            )
        return ap_sum

    # ------------------------------------------------------------------
    # Bill-due reminder (T166) — daily APScheduler job
    # ------------------------------------------------------------------

    def run_bill_due_reminder_check(
        self, as_of_date: date, days_ahead: int = DEFAULT_BILL_DUE_REMINDER_DAYS
    ) -> dict[str, int]:
        """Cross-tenant daily job: publish ``accounting.ap.bill.due`` for
        every open bill due within ``days_ahead`` days. Mirrors
        ``AccountsReceivableService.run_overdue_check()``'s cross-tenant
        scan pattern (Phase 6).
        """
        bus = get_event_bus()
        due_count = 0

        due_transactions = self._transactions.find_bills_due_within_across_companies(
            as_of_date, days_ahead
        )
        for transaction in due_transactions:
            ledger = self._ledgers.get_by_id(
                id=transaction.supplier_ledger_id, company_id=transaction.company_id
            )
            days_until_due = (
                (transaction.due_date - as_of_date).days
                if transaction.due_date
                else None
            )
            bus.publish(
                BillDueEvent(
                    event_type="accounting.ap.bill.due",
                    aggregate_type="APTransaction",
                    aggregate_id=transaction.id,
                    company_id=transaction.company_id,
                    actor_id=None,
                    ap_transaction_id=transaction.id,
                    supplier_id=ledger.supplier_id,
                    bill_number=transaction.bill_number,
                    due_date=(
                        transaction.due_date.isoformat()
                        if transaction.due_date
                        else None
                    ),
                    days_until_due=days_until_due,
                    outstanding_amount_base=transaction.outstanding_amount,
                )
            )
            due_count += 1

        return {"due_count": due_count}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_transaction(
        self, company_id: UUID, ap_transaction_id: UUID
    ) -> APTransaction:
        transaction = self._transactions.get_by_id_or_none(
            id=ap_transaction_id, company_id=company_id
        )
        if transaction is None:
            raise APTransactionNotFoundError(ap_transaction_id=str(ap_transaction_id))
        return transaction

    def _recompute_ledger_balance(
        self, company_id: UUID, supplier_ledger_id: UUID
    ) -> SupplierLedger:
        """Recompute ``total_outstanding_base`` from the transactions table
        (never incremented/decremented in place — research.md Decision 3).
        """
        ledger = self._ledgers.get_by_id(id=supplier_ledger_id, company_id=company_id)
        open_transactions = self._ledgers.get_open_transactions(company_id, ledger.id)
        ledger.total_outstanding_base = sum(
            (t.outstanding_amount for t in open_transactions), Decimal("0")
        )
        return self._ledgers.update(ledger)

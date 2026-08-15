"""BankAccountService and BankReconciliationService — Banking — Phase 8.

Both services live in this one module per tasks.md T181/T182, which name
the same target file for both.

Reconciliation design (research.md Decision 6 — statement-first):
``BankStatementLine`` rows are imported/entered independently of
``BankTransaction`` rows; ``run_auto_match()``/``manual_match()`` pair them
via ``BankReconciliationMatch``, leaving unmatched items visible on both
sides — the same pattern already applied to AP's
``SupplierStatementReconciliation`` in Phase 7.

Scope simplification: ``complete_reconciliation()`` requires the raw GL
account balance as of the statement date to exactly equal the statement's
closing balance (the literal Independent Test: "verify statement_balance ==
GL_balance"). Real-world reconciliation also tolerates legitimate timing
differences (outstanding cheques, deposits in transit) via an "adjusted
balance" computation — that refinement is out of this phase's scope; here,
outstanding items simply keep the difference non-zero until they clear or
are otherwise matched/adjusted.

Spec ref: specs/008-accounting-finance/spec.md §20 Banking
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import (
    BankReconciliationMatchType,
    BankReconciliationStatus,
    BankTransactionType,
    ChequeStatus,
)
from modules.accounting.events import get_event_bus
from modules.accounting.events.banking_events import BankReconciledEvent
from modules.accounting.exceptions import (
    BankAccountNotFoundError,
    BankReconciliationNotFoundError,
    ChequeNotFoundError,
    PostingValidationError,
    ReconciliationLockedError,
    ReconciliationNotBalancedError,
)
from modules.accounting.models.banking import (
    BankAccount,
    BankReconciliation,
    BankReconciliationMatch,
    BankStatementLine,
    BankTransaction,
    Cheque,
)
from modules.accounting.repositories.banking import (
    BankAccountRepository,
    BankReconciliationMatchRepository,
    BankReconciliationRepository,
    BankStatementLineRepository,
    BankTransactionRepository,
    ChequeRepository,
)
from modules.accounting.repositories.gl import GLReportRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.posting_engine import PostingEngine, PostingResult

#: Cheque status transitions allowed by data-model.md §8.5.
_ALLOWED_CHEQUE_TRANSITIONS: dict[str, set[str]] = {
    "ISSUED": {"PRESENTED", "CLEARED", "CANCELLED", "STALE"},
    "PRESENTED": {"CLEARED"},
    "CLEARED": set(),
    "CANCELLED": set(),
    "STALE": set(),
}

#: Auto-match date-proximity window (days) — same amount within this window
#: is treated as a high-confidence match (research.md Decision 6).
_AUTO_MATCH_DATE_WINDOW_DAYS = 3


class BankAccountService:
    """Application service for bank account management and simple postings."""

    def __init__(
        self,
        db: Session,
        bank_account_repo: BankAccountRepository,
        transaction_repo: BankTransactionRepository,
        cheque_repo: ChequeRepository,
        posting_engine: PostingEngine,
        audit_service: AuditLogService,
    ) -> None:
        self.db = db
        self._accounts = bank_account_repo
        self._transactions = transaction_repo
        self._cheques = cheque_repo
        self._engine = posting_engine
        self._audit = audit_service

    @staticmethod
    def _bank_account_snapshot(account: BankAccount) -> dict[str, Any]:
        return {
            "bank_name": account.bank_name,
            "account_number": account.account_number,
            "is_active": account.is_active,
            "current_gl_balance": str(account.current_gl_balance),
        }

    @staticmethod
    def _bank_transaction_snapshot(transaction: BankTransaction) -> dict[str, Any]:
        return {
            "transaction_type": transaction.transaction_type,
            "amount": str(transaction.amount),
        }

    @staticmethod
    def _cheque_snapshot(cheque: Cheque) -> dict[str, Any]:
        return {
            "status": cheque.status,
            "cheque_number": cheque.cheque_number,
            "amount": str(cheque.amount),
        }

    def create_bank_account(
        self,
        company_id: UUID,
        bank_name: str,
        account_number: str,
        currency_code: str,
        gl_account_id: UUID,
        branch_name: str | None = None,
        iban: str | None = None,
        swift_bic: str | None = None,
        opening_balance: Decimal = Decimal("0"),
        opening_balance_date: date | None = None,
        actor_id: UUID | None = None,
    ) -> BankAccount:
        account = BankAccount(
            company_id=company_id,
            bank_name=bank_name,
            branch_name=branch_name,
            account_number=account_number,
            iban=iban,
            swift_bic=swift_bic,
            currency_code=currency_code,
            gl_account_id=gl_account_id,
            opening_balance=opening_balance,
            opening_balance_date=opening_balance_date,
            current_gl_balance=opening_balance,
            created_by=actor_id,
        )
        self.db.add(account)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="BankAccount",
            entity_id=account.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._bank_account_snapshot(account),
        )
        return self._accounts.create(account)

    def get_bank_account(self, company_id: UUID, bank_account_id: UUID) -> BankAccount:
        account = self._accounts.get_by_id_or_none(
            id=bank_account_id, company_id=company_id
        )
        if account is None:
            raise BankAccountNotFoundError(bank_account_id=str(bank_account_id))
        return account

    def list_bank_accounts(
        self, company_id: UUID, active_only: bool = False
    ) -> list[BankAccount]:
        return self._accounts.list_all(company_id, active_only=active_only)

    def update_bank_account(
        self, company_id: UUID, bank_account_id: UUID, **fields: Any
    ) -> BankAccount:
        account = self.get_bank_account(company_id, bank_account_id)
        before = self._bank_account_snapshot(account)
        for key, value in fields.items():
            if value is not None and hasattr(account, key):
                setattr(account, key, value)
        self._audit.record(
            company_id=company_id,
            entity_type="BankAccount",
            entity_id=account.id,
            action="UPDATED",
            actor_id=None,
            before=before,
            after=self._bank_account_snapshot(account),
        )
        return self._accounts.update(account)

    # ------------------------------------------------------------------
    # Transfers / deposits — atomic GL posting + BankTransaction creation,
    # via PostingEngine's staging primitives (same pattern as AR/AP Phase
    # 6/7 record_* methods).
    # ------------------------------------------------------------------

    def record_bank_transfer(
        self,
        company_id: UUID,
        from_bank_account_id: UUID,
        to_bank_account_id: UUID,
        amount: Decimal,
        transfer_date: date,
        reference: str | None = None,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[BankTransaction, BankTransaction, PostingResult]:
        """Move funds between two bank accounts owned by this company.

        Single balanced journal: DR destination bank GL account / CR source
        bank GL account — plus one ``BankTransaction`` row per leg, all
        committed atomically.
        """
        if amount <= 0:
            raise PostingValidationError("Bank transfer amount must be positive.")

        from_account = self.get_bank_account(company_id, from_bank_account_id)
        to_account = self.get_bank_account(company_id, to_bank_account_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="MANUAL",
            posting_date=transfer_date,
            lines=[
                {
                    "account_id": to_account.gl_account_id,
                    "debit_amount": amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": from_account.gl_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount,
                },
            ],
            currency_code=from_account.currency_code,
            reference=reference,
            description=description
            or f"Bank transfer {from_account.bank_name} -> {to_account.bank_name}",
            source_document_type="BankTransfer",
            source_document_id=None,
            actor_id=actor_id,
        )

        from_txn = BankTransaction(
            company_id=company_id,
            bank_account_id=from_account.id,
            transaction_date=transfer_date,
            transaction_type=BankTransactionType.TRANSFER.value,
            amount=-amount,
            reference=reference,
            description=description,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        to_txn = BankTransaction(
            company_id=company_id,
            bank_account_id=to_account.id,
            transaction_date=transfer_date,
            transaction_type=BankTransactionType.TRANSFER.value,
            amount=amount,
            reference=reference,
            description=description,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(from_txn)
        self.db.add(to_txn)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="BankTransaction",
            entity_id=from_txn.id,
            action="CREATED",
            actor_id=actor_id,
            after={
                **self._bank_transaction_snapshot(from_txn),
                "paired_bank_transaction_id": str(to_txn.id),
            },
        )

        from_account.current_gl_balance = from_account.current_gl_balance - amount
        to_account.current_gl_balance = to_account.current_gl_balance + amount
        self.db.add(from_account)
        self.db.add(to_account)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(from_txn)
        self.db.refresh(to_txn)
        return from_txn, to_txn, result

    def record_bank_deposit(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        total_amount: Decimal,
        contra_account_id: UUID,
        deposit_date: date,
        reference: str | None = None,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[BankTransaction, PostingResult]:
        """Record a batched deposit (spec.md §20.3: multiple receipts batched
        into one deposit record) as DR Bank / CR ``contra_account_id``.

        No ``Payment``/receipt entity exists yet (Phase 9), so the caller
        supplies the already-aggregated total and the contra account (e.g.
        an "Undeposited Funds" clearing account) rather than a list of
        individual receipts.
        """
        if total_amount <= 0:
            raise PostingValidationError("Bank deposit amount must be positive.")

        account = self.get_bank_account(company_id, bank_account_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="MANUAL",
            posting_date=deposit_date,
            lines=[
                {
                    "account_id": account.gl_account_id,
                    "debit_amount": total_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": contra_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": total_amount,
                },
            ],
            currency_code=account.currency_code,
            reference=reference,
            description=description or "Bank deposit",
            source_document_type="BankDeposit",
            source_document_id=None,
            actor_id=actor_id,
        )

        transaction = BankTransaction(
            company_id=company_id,
            bank_account_id=account.id,
            transaction_date=deposit_date,
            transaction_type=BankTransactionType.RECEIPT.value,
            amount=total_amount,
            reference=reference,
            description=description,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="BankTransaction",
            entity_id=transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._bank_transaction_snapshot(transaction),
        )

        account.current_gl_balance = account.current_gl_balance + total_amount
        self.db.add(account)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(transaction)
        return transaction, result

    # ------------------------------------------------------------------
    # Cheque register (spec.md §20.4)
    # ------------------------------------------------------------------

    def issue_cheque(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        cheque_number: str,
        payee_name: str,
        cheque_date: date,
        amount: Decimal,
        actor_id: UUID | None = None,
    ) -> Cheque:
        self.get_bank_account(company_id, bank_account_id)  # existence/tenant check
        cheque = Cheque(
            company_id=company_id,
            bank_account_id=bank_account_id,
            cheque_number=cheque_number,
            payee_name=payee_name,
            cheque_date=cheque_date,
            amount=amount,
            status=ChequeStatus.ISSUED.value,
            created_by=actor_id,
        )
        self.db.add(cheque)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="Cheque",
            entity_id=cheque.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._cheque_snapshot(cheque),
        )
        return self._cheques.create(cheque)

    def update_cheque_status(
        self,
        company_id: UUID,
        cheque_id: UUID,
        new_status: str,
        cancel_reason: str | None = None,
        bank_statement_line_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> Cheque:
        cheque = self._cheques.get_by_id_or_none(id=cheque_id, company_id=company_id)
        if cheque is None:
            raise ChequeNotFoundError(cheque_id=str(cheque_id))

        allowed = _ALLOWED_CHEQUE_TRANSITIONS.get(cheque.status, set())
        if new_status not in allowed:
            raise PostingValidationError(
                f"Cheque '{cheque_id}' cannot transition from {cheque.status} to {new_status}."
            )

        before = self._cheque_snapshot(cheque)
        cheque.status = new_status
        if new_status == "CANCELLED":
            cheque.cancelled_at = utcnow()
            cheque.cancel_reason = cancel_reason
        if new_status == "CLEARED" and bank_statement_line_id is not None:
            cheque.bank_statement_line_id = bank_statement_line_id
        self._audit.record(
            company_id=company_id,
            entity_type="Cheque",
            entity_id=cheque.id,
            action=new_status,
            actor_id=actor_id,
            before=before,
            after=self._cheque_snapshot(cheque),
            reason=cancel_reason,
        )
        return self._cheques.update(cheque)

    def list_cheques(self, company_id: UUID, status: str | None = None) -> list[Cheque]:
        return self._cheques.list_all(company_id, status=status)

    # ------------------------------------------------------------------
    # Bank book (statement-style view, mirrors AR/AP get_*_statement())
    # ------------------------------------------------------------------

    def get_bank_book(
        self, company_id: UUID, bank_account_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        account = self.get_bank_account(company_id, bank_account_id)
        transactions = [
            t
            for t in self._transactions.find_by_bank_account(
                company_id, bank_account_id
            )
            if from_date <= t.transaction_date <= to_date
        ]
        opening_balance = account.opening_balance + sum(
            (
                t.amount
                for t in self._transactions.find_by_bank_account(
                    company_id, bank_account_id
                )
                if t.transaction_date < from_date
            ),
            Decimal("0"),
        )
        closing_balance = opening_balance + sum(
            (t.amount for t in transactions), Decimal("0")
        )
        return {
            "bank_account_id": bank_account_id,
            "from_date": from_date,
            "to_date": to_date,
            "opening_balance": opening_balance,
            "transactions": transactions,
            "closing_balance": closing_balance,
        }


class BankReconciliationService:
    """Application service for the statement-first bank reconciliation workflow."""

    def __init__(
        self,
        db: Session,
        bank_account_repo: BankAccountRepository,
        transaction_repo: BankTransactionRepository,
        statement_line_repo: BankStatementLineRepository,
        reconciliation_repo: BankReconciliationRepository,
        match_repo: BankReconciliationMatchRepository,
        posting_engine: PostingEngine,
        audit_service: AuditLogService,
    ) -> None:
        self.db = db
        self._accounts = bank_account_repo
        self._transactions = transaction_repo
        self._statement_lines = statement_line_repo
        self._reconciliations = reconciliation_repo
        self._matches = match_repo
        self._engine = posting_engine
        self._audit = audit_service
        self._gl_reports = GLReportRepository(db)

    @staticmethod
    def _reconciliation_snapshot(reconciliation: BankReconciliation) -> dict[str, Any]:
        return {
            "status": reconciliation.status,
            "statement_closing_balance": str(reconciliation.statement_closing_balance),
            "gl_balance_at_date": str(reconciliation.gl_balance_at_date),
            "difference": str(reconciliation.difference),
        }

    @staticmethod
    def _match_snapshot(match: BankReconciliationMatch) -> dict[str, Any]:
        return {
            "match_type": match.match_type,
            "bank_transaction_id": str(match.bank_transaction_id),
            "statement_line_id": str(match.statement_line_id),
        }

    @staticmethod
    def _bank_transaction_snapshot(transaction: BankTransaction) -> dict[str, Any]:
        return {
            "transaction_type": transaction.transaction_type,
            "amount": str(transaction.amount),
        }

    def _get_reconciliation(
        self, company_id: UUID, reconciliation_id: UUID
    ) -> BankReconciliation:
        reconciliation = self._reconciliations.get_by_id_or_none(
            id=reconciliation_id, company_id=company_id
        )
        if reconciliation is None:
            raise BankReconciliationNotFoundError(
                reconciliation_id=str(reconciliation_id)
            )
        return reconciliation

    def _assert_not_locked(self, reconciliation: BankReconciliation) -> None:
        if reconciliation.status == BankReconciliationStatus.LOCKED.value:
            raise ReconciliationLockedError(str(reconciliation.id))

    def _gl_balance_at(
        self, company_id: UUID, bank_account: BankAccount, as_of: date
    ) -> Decimal:
        balances = self._gl_reports.account_balance_query(
            company_id=company_id, account_id=bank_account.gl_account_id, end_date=as_of
        )
        return balances["total_debit"] - balances["total_credit"]

    def start_reconciliation(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        statement_date: date,
        statement_closing_balance: Decimal,
        actor_id: UUID | None = None,
    ) -> BankReconciliation:
        account = self._accounts.get_by_id_or_none(
            id=bank_account_id, company_id=company_id
        )
        if account is None:
            raise BankAccountNotFoundError(bank_account_id=str(bank_account_id))

        gl_balance = self._gl_balance_at(company_id, account, statement_date)
        reconciliation = BankReconciliation(
            company_id=company_id,
            bank_account_id=bank_account_id,
            statement_date=statement_date,
            statement_closing_balance=statement_closing_balance,
            gl_balance_at_date=gl_balance,
            difference=statement_closing_balance - gl_balance,
            status=BankReconciliationStatus.IN_PROGRESS.value,
            created_by=actor_id,
        )
        self.db.add(reconciliation)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="BankReconciliation",
            entity_id=reconciliation.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._reconciliation_snapshot(reconciliation),
        )
        return self._reconciliations.create(reconciliation)

    def import_statement_lines(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        lines: list[dict[str, Any]],
        actor_id: UUID | None = None,
    ) -> list[BankStatementLine]:
        """Persist parsed statement rows (CSV parsing happens at the API
        layer — this accepts already-parsed dicts, matching the convention
        ``bulk_import_accounts`` established in Phase 2).

        Builds every row and commits once via ``create_many()`` (T301) —
        the naive per-row ``repo.create()`` loop this replaced committed
        once per line, which does not scale to a realistic multi-thousand-
        line statement import (measured: 5000 lines / 63s, well over the
        30s target; bulk commit: 5000 lines / ~2s).
        """
        new_lines = [
            BankStatementLine(
                company_id=company_id,
                bank_account_id=bank_account_id,
                statement_date=line["statement_date"],
                value_date=line.get("value_date"),
                amount=Decimal(str(line["amount"])),
                reference=line.get("reference"),
                description=line.get("description"),
                transaction_type=line.get("transaction_type"),
                created_by=actor_id,
            )
            for line in lines
        ]
        return self._statement_lines.create_many(new_lines)

    def run_auto_match(
        self, company_id: UUID, reconciliation_id: UUID, actor_id: UUID | None = None
    ) -> dict[str, int]:
        """Match unmatched statement lines to unreconciled transactions by
        exact amount within a date-proximity window (research.md Decision 6).
        """
        reconciliation = self._get_reconciliation(company_id, reconciliation_id)
        self._assert_not_locked(reconciliation)

        statement_lines = self._statement_lines.find_unmatched(
            company_id, reconciliation.bank_account_id
        )
        transactions = self._transactions.find_unreconciled(
            company_id, reconciliation.bank_account_id
        )

        matched_transaction_ids: set[UUID] = set()
        matched_count = 0

        for line in statement_lines:
            candidate = next(
                (
                    t
                    for t in transactions
                    if t.id not in matched_transaction_ids
                    and t.amount == line.amount
                    and abs((t.transaction_date - line.statement_date).days)
                    <= _AUTO_MATCH_DATE_WINDOW_DAYS
                ),
                None,
            )
            if candidate is None:
                continue

            matched_transaction_ids.add(candidate.id)
            self._create_match(
                company_id,
                reconciliation,
                candidate,
                line,
                BankReconciliationMatchType.AUTO.value,
                actor_id,
            )
            matched_count += 1

        return {
            "matched_count": matched_count,
            "unmatched_count": len(statement_lines) - matched_count,
        }

    def manual_match(
        self,
        company_id: UUID,
        reconciliation_id: UUID,
        bank_transaction_id: UUID,
        statement_line_id: UUID,
        actor_id: UUID | None = None,
    ) -> BankReconciliationMatch:
        reconciliation = self._get_reconciliation(company_id, reconciliation_id)
        self._assert_not_locked(reconciliation)

        transaction = self._transactions.get_by_id_or_none(
            id=bank_transaction_id, company_id=company_id
        )
        line = self._statement_lines.get_by_id_or_none(
            id=statement_line_id, company_id=company_id
        )
        if transaction is None or line is None:
            raise PostingValidationError(
                "Cannot manually match: bank transaction or statement line not found."
            )
        return self._create_match(
            company_id,
            reconciliation,
            transaction,
            line,
            BankReconciliationMatchType.MANUAL.value,
            actor_id,
        )

    def unmatch(
        self,
        company_id: UUID,
        reconciliation_id: UUID,
        match_id: UUID,
        actor_id: UUID | None = None,
    ) -> None:
        reconciliation = self._get_reconciliation(company_id, reconciliation_id)
        self._assert_not_locked(reconciliation)

        match = self._matches.get_by_id_or_none(id=match_id, company_id=company_id)
        if match is None:
            raise PostingValidationError(
                f"Reconciliation match '{match_id}' not found."
            )

        transaction = self._transactions.get_by_id_or_none(
            id=match.bank_transaction_id, company_id=company_id
        )
        line = self._statement_lines.get_by_id_or_none(
            id=match.statement_line_id, company_id=company_id
        )
        if transaction is not None:
            transaction.is_reconciled = False
            transaction.reconciliation_match_id = None
            self._transactions.update(transaction)
        if line is not None:
            line.is_matched = False
            line.reconciliation_match_id = None
            self._statement_lines.update(line)
        self._audit.record(
            company_id=company_id,
            entity_type="BankReconciliationMatch",
            entity_id=match.id,
            action="UNMATCHED",
            actor_id=actor_id,
            before=self._match_snapshot(match),
        )
        self._matches.soft_delete(id=match_id, company_id=company_id)

    def post_bank_charge(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        amount: Decimal,
        expense_account_id: UUID,
        charge_date: date,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[BankTransaction, PostingResult]:
        """Auto-create the GL entry for a bank charge found on the statement
        (DR Expense / CR Bank) — tasks.md T182.
        """
        if amount <= 0:
            raise PostingValidationError("Bank charge amount must be positive.")

        account = self._accounts.get_by_id_or_none(
            id=bank_account_id, company_id=company_id
        )
        if account is None:
            raise BankAccountNotFoundError(bank_account_id=str(bank_account_id))

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="MANUAL",
            posting_date=charge_date,
            lines=[
                {
                    "account_id": expense_account_id,
                    "debit_amount": amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": account.gl_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount,
                },
            ],
            currency_code=account.currency_code,
            description=description or "Bank charge",
            source_document_type="BankCharge",
            source_document_id=None,
            actor_id=actor_id,
        )

        transaction = BankTransaction(
            company_id=company_id,
            bank_account_id=account.id,
            transaction_date=charge_date,
            transaction_type=BankTransactionType.BANK_CHARGE.value,
            amount=-amount,
            description=description,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="BankTransaction",
            entity_id=transaction.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._bank_transaction_snapshot(transaction),
        )

        account.current_gl_balance = account.current_gl_balance - amount
        self.db.add(account)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(transaction)
        return transaction, result

    def complete_reconciliation(
        self, company_id: UUID, reconciliation_id: UUID, actor_id: UUID | None = None
    ) -> BankReconciliation:
        reconciliation = self._get_reconciliation(company_id, reconciliation_id)
        self._assert_not_locked(reconciliation)

        account = self._accounts.get_by_id_or_none(
            id=reconciliation.bank_account_id, company_id=company_id
        )
        if account is None:
            raise BankAccountNotFoundError(
                bank_account_id=str(reconciliation.bank_account_id)
            )

        gl_balance = self._gl_balance_at(
            company_id, account, reconciliation.statement_date
        )
        difference = reconciliation.statement_closing_balance - gl_balance

        if difference != 0:
            reconciliation.gl_balance_at_date = gl_balance
            reconciliation.difference = difference
            self._reconciliations.update(reconciliation)
            raise ReconciliationNotBalancedError(
                str(reconciliation_id), str(difference)
            )

        before = self._reconciliation_snapshot(reconciliation)
        reconciliation.gl_balance_at_date = gl_balance
        reconciliation.difference = Decimal("0")
        reconciliation.status = BankReconciliationStatus.COMPLETED.value
        reconciliation.completed_at = utcnow()
        reconciliation.completed_by_user_id = actor_id
        self._audit.record(
            company_id=company_id,
            entity_type="BankReconciliation",
            entity_id=reconciliation.id,
            action="RECONCILED",
            actor_id=actor_id,
            before=before,
            after=self._reconciliation_snapshot(reconciliation),
        )
        return self._reconciliations.update(reconciliation)

    def lock_reconciliation(
        self, company_id: UUID, reconciliation_id: UUID, actor_id: UUID | None = None
    ) -> BankReconciliation:
        reconciliation = self._get_reconciliation(company_id, reconciliation_id)
        if reconciliation.status != BankReconciliationStatus.COMPLETED.value:
            raise PostingValidationError(
                f"Reconciliation '{reconciliation_id}' must be COMPLETED before it can be locked "
                f"(current status: {reconciliation.status})."
            )

        before = self._reconciliation_snapshot(reconciliation)
        reconciliation.status = BankReconciliationStatus.LOCKED.value
        self._audit.record(
            company_id=company_id,
            entity_type="BankReconciliation",
            entity_id=reconciliation.id,
            action="LOCKED",
            actor_id=actor_id,
            before=before,
            after=self._reconciliation_snapshot(reconciliation),
        )
        reconciliation = self._reconciliations.update(reconciliation)

        account = self._accounts.get_by_id_or_none(
            id=reconciliation.bank_account_id, company_id=company_id
        )
        get_event_bus().publish(
            BankReconciledEvent(
                event_type="accounting.bank.reconciled",
                aggregate_type="BankReconciliation",
                aggregate_id=reconciliation.id,
                company_id=company_id,
                actor_id=actor_id,
                bank_account_id=reconciliation.bank_account_id,
                bank_account_name=account.bank_name if account else None,
                statement_date=reconciliation.statement_date.isoformat(),
                statement_closing_balance=reconciliation.statement_closing_balance,
                gl_balance_at_date=reconciliation.gl_balance_at_date,
            )
        )
        return reconciliation

    def get_reconciliation_report(
        self, company_id: UUID, reconciliation_id: UUID
    ) -> dict[str, Any]:
        reconciliation = self._get_reconciliation(company_id, reconciliation_id)
        matches = self._matches.find_by_reconciliation(company_id, reconciliation_id)
        unmatched_transactions = self._transactions.find_unreconciled(
            company_id, reconciliation.bank_account_id
        )
        unmatched_lines = self._statement_lines.find_unmatched(
            company_id, reconciliation.bank_account_id
        )
        return {
            "reconciliation": reconciliation,
            "matches": matches,
            "unmatched_transactions": unmatched_transactions,
            "unmatched_statement_lines": unmatched_lines,
        }

    def _create_match(
        self,
        company_id: UUID,
        reconciliation: BankReconciliation,
        transaction: BankTransaction,
        line: BankStatementLine,
        match_type: str,
        actor_id: UUID | None,
    ) -> BankReconciliationMatch:
        match = BankReconciliationMatch(
            company_id=company_id,
            reconciliation_id=reconciliation.id,
            bank_transaction_id=transaction.id,
            statement_line_id=line.id,
            match_type=match_type,
            matched_at=utcnow(),
            matched_by_user_id=actor_id,
            created_by=actor_id,
        )
        self.db.add(match)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="BankReconciliationMatch",
            entity_id=match.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._match_snapshot(match),
        )
        match = self._matches.create(match)
        transaction.is_reconciled = True
        transaction.reconciliation_match_id = match.id
        self._transactions.update(transaction)
        line.is_matched = True
        line.reconciliation_match_id = match.id
        self._statement_lines.update(line)
        return match

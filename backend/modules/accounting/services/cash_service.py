"""CashAccountService — Cash Management — Phase 9.

Covers cash account management, cash receipts/payments, the petty cash
voucher/replenishment workflow, and cash reconciliation.

Petty cash design (plan.md Phase 8/"Cash Management" section, spec.md §21.4):
a ``PettyCashVoucher`` records a disbursement of physical cash for audit
purposes but does NOT itself touch the GL — the imprest fund's GL balance
is only adjusted when vouchers are folded into a replenishment journal
(DR the vouchers' expense accounts / CR Bank). ``PettyCashVoucher.
journal_entry_id`` is NULL until replenished, mirroring the Cheque entity's
``bank_transaction_id`` lifecycle-linkage pattern from Phase 8.

Cash reconciliation (spec.md §21.5) is a single-shot operation — unlike
Bank's statement-first, multi-step session — record the physical count,
compute the difference against the GL balance, and post it to a Cash
Short/Over account via the PostingEngine, all in one call.

Spec ref: specs/008-accounting-finance/spec.md §21 Cash Management
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import CashReconciliationStatus, CashTransactionType
from modules.accounting.exceptions import (
    CashAccountNotFoundError,
    PettyCashVoucherNotFoundError,
    PostingValidationError,
    VoucherAlreadyReplenishedError,
)
from modules.accounting.models.cash import (
    CashAccount,
    CashReconciliation,
    CashTransaction,
    PettyCashVoucher,
)
from modules.accounting.repositories.cash import (
    CashAccountRepository,
    CashReconciliationRepository,
    CashTransactionRepository,
    PettyCashVoucherRepository,
)
from modules.accounting.repositories.gl import GLReportRepository
from modules.accounting.services.posting_engine import PostingEngine, PostingResult


class CashAccountService:
    """Application service for cash account management and cash postings."""

    def __init__(
        self,
        db: Session,
        cash_account_repo: CashAccountRepository,
        transaction_repo: CashTransactionRepository,
        voucher_repo: PettyCashVoucherRepository,
        reconciliation_repo: CashReconciliationRepository,
        posting_engine: PostingEngine,
    ) -> None:
        self.db = db
        self._accounts = cash_account_repo
        self._transactions = transaction_repo
        self._vouchers = voucher_repo
        self._reconciliations = reconciliation_repo
        self._engine = posting_engine
        self._gl_reports = GLReportRepository(db)

    # ------------------------------------------------------------------
    # Cash accounts
    # ------------------------------------------------------------------

    def create_cash_account(
        self,
        company_id: UUID,
        account_name: str,
        currency_code: str,
        gl_account_id: UUID,
        is_petty_cash: bool = False,
        float_amount: Decimal = Decimal("0"),
        actor_id: UUID | None = None,
    ) -> CashAccount:
        return self._accounts.create(
            CashAccount(
                company_id=company_id,
                account_name=account_name,
                currency_code=currency_code,
                gl_account_id=gl_account_id,
                is_petty_cash=is_petty_cash,
                float_amount=float_amount,
                created_by=actor_id,
            )
        )

    def get_cash_account(self, company_id: UUID, cash_account_id: UUID) -> CashAccount:
        account = self._accounts.get_by_id_or_none(
            id=cash_account_id, company_id=company_id
        )
        if account is None:
            raise CashAccountNotFoundError(cash_account_id=str(cash_account_id))
        return account

    def list_cash_accounts(
        self, company_id: UUID, active_only: bool = False
    ) -> list[CashAccount]:
        return self._accounts.list_all(company_id, active_only=active_only)

    # ------------------------------------------------------------------
    # Cash receipts / payments — atomic GL posting + CashTransaction,
    # same staging pattern as Bank's record_bank_deposit (Phase 8).
    # ------------------------------------------------------------------

    def record_cash_receipt(
        self,
        company_id: UUID,
        cash_account_id: UUID,
        amount: Decimal,
        contra_account_id: UUID,
        receipt_date: date,
        reference: str | None = None,
        description: str | None = None,
        counterparty_type: str | None = None,
        counterparty_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[CashTransaction, PostingResult]:
        """Record cash received (e.g. customer cash payment): DR Cash / CR
        ``contra_account_id`` (Revenue or AR control account).
        """
        if amount <= 0:
            raise PostingValidationError("Cash receipt amount must be positive.")

        account = self.get_cash_account(company_id, cash_account_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="CASH",
            posting_date=receipt_date,
            lines=[
                {
                    "account_id": account.gl_account_id,
                    "debit_amount": amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": contra_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount,
                },
            ],
            currency_code=account.currency_code,
            reference=reference,
            description=description or "Cash receipt",
            source_document_type="CashReceipt",
            source_document_id=None,
            actor_id=actor_id,
        )

        transaction = CashTransaction(
            company_id=company_id,
            cash_account_id=account.id,
            transaction_date=receipt_date,
            transaction_type=CashTransactionType.RECEIPT.value,
            amount=amount,
            reference=reference,
            description=description,
            journal_entry_id=entry.id,
            counterparty_type=counterparty_type,
            counterparty_id=counterparty_id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()

        account.current_balance = account.current_balance + amount
        self.db.add(account)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(transaction)
        return transaction, result

    def record_cash_payment(
        self,
        company_id: UUID,
        cash_account_id: UUID,
        amount: Decimal,
        contra_account_id: UUID,
        payment_date: date,
        reference: str | None = None,
        description: str | None = None,
        counterparty_type: str | None = None,
        counterparty_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[CashTransaction, PostingResult]:
        """Record cash paid out (e.g. supplier cash payment): DR
        ``contra_account_id`` (Expense or AP control account) / CR Cash.
        """
        if amount <= 0:
            raise PostingValidationError("Cash payment amount must be positive.")

        account = self.get_cash_account(company_id, cash_account_id)

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="CASH",
            posting_date=payment_date,
            lines=[
                {
                    "account_id": contra_account_id,
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
            reference=reference,
            description=description or "Cash payment",
            source_document_type="CashPayment",
            source_document_id=None,
            actor_id=actor_id,
        )

        transaction = CashTransaction(
            company_id=company_id,
            cash_account_id=account.id,
            transaction_date=payment_date,
            transaction_type=CashTransactionType.PAYMENT.value,
            amount=-amount,
            reference=reference,
            description=description,
            journal_entry_id=entry.id,
            counterparty_type=counterparty_type,
            counterparty_id=counterparty_id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()

        account.current_balance = account.current_balance - amount
        self.db.add(account)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(transaction)
        return transaction, result

    # ------------------------------------------------------------------
    # Petty cash vouchers / replenishment
    # ------------------------------------------------------------------

    def create_petty_cash_voucher(
        self,
        company_id: UUID,
        cash_account_id: UUID,
        voucher_date: date,
        amount: Decimal,
        expense_account_id: UUID,
        recipient_name: str,
        purpose: str,
        voucher_number: str,
        approved_by_user_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> PettyCashVoucher:
        if amount <= 0:
            raise PostingValidationError("Petty cash voucher amount must be positive.")

        self.get_cash_account(company_id, cash_account_id)  # existence/tenant check
        return self._vouchers.create(
            PettyCashVoucher(
                company_id=company_id,
                cash_account_id=cash_account_id,
                voucher_date=voucher_date,
                amount=amount,
                expense_account_id=expense_account_id,
                recipient_name=recipient_name,
                purpose=purpose,
                approved_by_user_id=approved_by_user_id,
                voucher_number=voucher_number,
                created_by=actor_id,
            )
        )

    def list_petty_cash_vouchers(
        self, company_id: UUID, cash_account_id: UUID
    ) -> list[PettyCashVoucher]:
        self.get_cash_account(company_id, cash_account_id)
        return self._vouchers.find_by_cash_account(company_id, cash_account_id)

    def replenish_petty_cash(
        self,
        company_id: UUID,
        cash_account_id: UUID,
        voucher_ids: list[UUID],
        bank_gl_account_id: UUID,
        replenishment_date: date,
        reference: str | None = None,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[CashTransaction, list[PettyCashVoucher], PostingResult]:
        """Fold the given vouchers into a single replenishment journal:
        DR each voucher's expense account (grouped/summed) / CR Bank.
        """
        account = self.get_cash_account(company_id, cash_account_id)

        vouchers: list[PettyCashVoucher] = []
        for voucher_id in voucher_ids:
            voucher = self._vouchers.get_by_id_or_none(
                id=voucher_id, company_id=company_id
            )
            if voucher is None:
                raise PettyCashVoucherNotFoundError(voucher_id=str(voucher_id))
            if voucher.cash_account_id != cash_account_id:
                raise PostingValidationError(
                    f"Voucher '{voucher_id}' does not belong to cash account '{cash_account_id}'."
                )
            if voucher.journal_entry_id is not None:
                raise VoucherAlreadyReplenishedError(str(voucher_id))
            vouchers.append(voucher)

        if not vouchers:
            raise PostingValidationError(
                "At least one voucher is required to replenish."
            )

        by_expense_account: dict[UUID, Decimal] = {}
        for voucher in vouchers:
            by_expense_account[voucher.expense_account_id] = (
                by_expense_account.get(voucher.expense_account_id, Decimal("0"))
                + voucher.amount
            )
        total = sum(by_expense_account.values(), Decimal("0"))

        lines = [
            {
                "account_id": expense_account_id,
                "debit_amount": subtotal,
                "credit_amount": Decimal("0"),
            }
            for expense_account_id, subtotal in by_expense_account.items()
        ]
        lines.append(
            {
                "account_id": bank_gl_account_id,
                "debit_amount": Decimal("0"),
                "credit_amount": total,
            }
        )

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="CASH",
            posting_date=replenishment_date,
            lines=lines,
            currency_code=account.currency_code,
            reference=reference,
            description=description or "Petty cash replenishment",
            source_document_type="PettyCashReplenishment",
            source_document_id=None,
            actor_id=actor_id,
        )

        for voucher in vouchers:
            voucher.journal_entry_id = entry.id
            self.db.add(voucher)

        transaction = CashTransaction(
            company_id=company_id,
            cash_account_id=account.id,
            transaction_date=replenishment_date,
            transaction_type=CashTransactionType.TRANSFER.value,
            amount=total,
            reference=reference,
            description=description or "Petty cash replenishment",
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(transaction)
        self.db.flush()

        account.current_balance = account.current_balance + total
        self.db.add(account)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(transaction)
        for voucher in vouchers:
            self.db.refresh(voucher)
        return transaction, vouchers, result

    # ------------------------------------------------------------------
    # Cash reconciliation
    # ------------------------------------------------------------------

    def _gl_balance_at(
        self, company_id: UUID, account: CashAccount, as_of: date
    ) -> Decimal:
        balances = self._gl_reports.account_balance_query(
            company_id=company_id, account_id=account.gl_account_id, end_date=as_of
        )
        return balances["total_debit"] - balances["total_credit"]

    def reconcile_cash(
        self,
        company_id: UUID,
        cash_account_id: UUID,
        reconciliation_date: date,
        physical_count_amount: Decimal,
        difference_account_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> CashReconciliation:
        """Record a physical cash count against the GL balance and, if they
        differ, post the difference to ``difference_account_id`` (Cash
        Short/Over) via the PostingEngine — all as a single-shot operation.
        """
        if physical_count_amount < 0:
            raise PostingValidationError("Physical count amount cannot be negative.")

        account = self.get_cash_account(company_id, cash_account_id)
        gl_balance = self._gl_balance_at(company_id, account, reconciliation_date)
        difference = physical_count_amount - gl_balance

        if difference != 0:
            if difference_account_id is None:
                raise PostingValidationError(
                    "difference_account_id is required when physical count differs from GL balance."
                )
            if difference > 0:
                lines = [
                    {
                        "account_id": account.gl_account_id,
                        "debit_amount": difference,
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": difference_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": difference,
                    },
                ]
            else:
                shortage = -difference
                lines = [
                    {
                        "account_id": difference_account_id,
                        "debit_amount": shortage,
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": account.gl_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": shortage,
                    },
                ]

            entry, journal_number, posted_at = self._engine.stage_direct_posting(
                company_id=company_id,
                journal_type="AUTOMATED",
                posting_source="CASH",
                posting_date=reconciliation_date,
                lines=lines,
                currency_code=account.currency_code,
                description="Cash short/over adjustment",
                source_document_type="CashReconciliation",
                source_document_id=None,
                actor_id=actor_id,
            )

            reconciliation = CashReconciliation(
                company_id=company_id,
                cash_account_id=cash_account_id,
                reconciliation_date=reconciliation_date,
                physical_count_amount=physical_count_amount,
                gl_balance_amount=gl_balance,
                difference=difference,
                difference_account_id=difference_account_id,
                status=CashReconciliationStatus.COMPLETED.value,
                completed_at=utcnow(),
                created_by=actor_id,
            )
            self.db.add(reconciliation)
            self.db.flush()
            reconciliation.journal_entry_id = entry.id

            account.current_balance = physical_count_amount
            self.db.add(account)

            self._engine.finalize_and_publish(
                entry, journal_number, posted_at, actor_id
            )
            self.db.refresh(reconciliation)
            return reconciliation

        reconciliation = CashReconciliation(
            company_id=company_id,
            cash_account_id=cash_account_id,
            reconciliation_date=reconciliation_date,
            physical_count_amount=physical_count_amount,
            gl_balance_amount=gl_balance,
            difference=Decimal("0"),
            status=CashReconciliationStatus.COMPLETED.value,
            completed_at=utcnow(),
            created_by=actor_id,
        )
        self.db.add(reconciliation)
        account.current_balance = physical_count_amount
        self.db.add(account)
        self.db.commit()
        self.db.refresh(reconciliation)
        return reconciliation

    # ------------------------------------------------------------------
    # Cash book (statement-style view, mirrors Bank's get_bank_book())
    # ------------------------------------------------------------------

    def get_cash_book(
        self, company_id: UUID, cash_account_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        self.get_cash_account(company_id, cash_account_id)  # existence/tenant check
        all_transactions = self._transactions.find_by_cash_account(
            company_id, cash_account_id
        )
        transactions = [
            t for t in all_transactions if from_date <= t.transaction_date <= to_date
        ]
        opening_balance = sum(
            (t.amount for t in all_transactions if t.transaction_date < from_date),
            Decimal("0"),
        )
        closing_balance = opening_balance + sum(
            (t.amount for t in transactions), Decimal("0")
        )
        return {
            "cash_account_id": cash_account_id,
            "from_date": from_date,
            "to_date": to_date,
            "opening_balance": opening_balance,
            "transactions": transactions,
            "closing_balance": closing_balance,
        }

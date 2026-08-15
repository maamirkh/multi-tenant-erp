"""Repositories for Accounts Receivable entities — Phase 6.

  CustomerLedgerRepository        — ledger root CRUD + aging/statement queries
  ARTransactionRepository         — transaction CRUD
  ARPaymentAllocationRepository   — allocation CRUD (Phase 9 populates this)
  CustomerCreditHistoryRepository — audit trail CRUD

Spec ref: specs/008-accounting-finance/tasks.md T136
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.ar import (
    ARPaymentAllocation,
    ARTransaction,
    CustomerCreditHistory,
    CustomerLedger,
)
from modules.accounting.repositories import BaseAccountingRepository


class CustomerLedgerRepository(BaseAccountingRepository[CustomerLedger]):
    """Data-access layer for the ``accounting_customer_ledgers`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerLedger)

    def find_by_customer(
        self, company_id: UUID, customer_id: UUID
    ) -> CustomerLedger | None:
        stmt = (
            select(CustomerLedger)
            .where(CustomerLedger.company_id == company_id)
            .where(CustomerLedger.customer_id == customer_id)
            .where(CustomerLedger.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID) -> list[CustomerLedger]:
        stmt = (
            select(CustomerLedger)
            .where(CustomerLedger.company_id == company_id)
            .where(CustomerLedger.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_all_not_on_hold_across_companies(self) -> list[CustomerLedger]:
        """Cross-tenant scan for the daily overdue-check job's credit-limit-
        warning pass (tasks.md T143) — excludes ledgers already on HOLD.
        """
        stmt = (
            select(CustomerLedger)
            .where(CustomerLedger.is_deleted == False)  # noqa: E712
            .where(CustomerLedger.credit_status != "HOLD")
            .where(CustomerLedger.credit_limit > 0)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_open_transactions(
        self, company_id: UUID, customer_ledger_id: UUID
    ) -> list[ARTransaction]:
        stmt = (
            select(ARTransaction)
            .where(ARTransaction.company_id == company_id)
            .where(ARTransaction.customer_ledger_id == customer_ledger_id)
            .where(ARTransaction.is_deleted == False)  # noqa: E712
            .where(
                ARTransaction.status.in_(
                    ["OPEN", "PARTIALLY_PAID", "OVERDUE", "DISPUTED"]
                )
            )
            .order_by(ARTransaction.transaction_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_aging_data(self, company_id: UUID, as_of_date: date) -> list[ARTransaction]:
        """Return every open AR transaction across all customers, for aging calc.

        Aging is calculated from ``due_date`` (spec.md §18.3), not the
        transaction date — filtering/bucketing happens in ``AgingCalculator``.
        """
        stmt = (
            select(ARTransaction)
            .where(ARTransaction.company_id == company_id)
            .where(ARTransaction.is_deleted == False)  # noqa: E712
            .where(
                ARTransaction.status.in_(
                    ["OPEN", "PARTIALLY_PAID", "OVERDUE", "DISPUTED"]
                )
            )
            .where(ARTransaction.transaction_date <= as_of_date)
            .order_by(ARTransaction.customer_ledger_id, ARTransaction.due_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_statement_data(
        self, company_id: UUID, customer_ledger_id: UUID, from_date: date, to_date: date
    ) -> list[ARTransaction]:
        stmt = (
            select(ARTransaction)
            .where(ARTransaction.company_id == company_id)
            .where(ARTransaction.customer_ledger_id == customer_ledger_id)
            .where(ARTransaction.is_deleted == False)  # noqa: E712
            .where(ARTransaction.transaction_date >= from_date)
            .where(ARTransaction.transaction_date <= to_date)
            .order_by(ARTransaction.transaction_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_opening_balance(
        self, company_id: UUID, customer_ledger_id: UUID, before_date: date
    ) -> Decimal:
        stmt = select(ARTransaction).where(
            ARTransaction.company_id == company_id,
            ARTransaction.customer_ledger_id == customer_ledger_id,
            ARTransaction.is_deleted == False,  # noqa: E712
            ARTransaction.transaction_date < before_date,
        )
        rows = self.db.execute(stmt).scalars().all()
        total = Decimal("0")
        for row in rows:
            sign = (
                Decimal("1")
                if row.transaction_type in ("INVOICE", "DEBIT_NOTE")
                else Decimal("-1")
            )
            total += sign * row.amount_base
        return total


class ARTransactionRepository(BaseAccountingRepository[ARTransaction]):
    """Data-access layer for the ``accounting_ar_transactions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ARTransaction)

    def find_overdue_across_companies(self, as_of_date: date) -> list[ARTransaction]:
        """Cross-tenant scan for the daily overdue-check job (tasks.md T143) —
        mirrors ``RecurringJournalTemplateRepository.find_due()``'s
        established cross-tenant scan pattern (Phase 5).
        """
        stmt = (
            select(ARTransaction)
            .where(ARTransaction.is_deleted == False)  # noqa: E712
            .where(ARTransaction.status.in_(["OPEN", "PARTIALLY_PAID", "DISPUTED"]))
            .where(ARTransaction.due_date.is_not(None))
            .where(ARTransaction.due_date < as_of_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_source_document(
        self, company_id: UUID, source_document_type: str, source_document_id: UUID
    ) -> ARTransaction | None:
        stmt = (
            select(ARTransaction)
            .where(ARTransaction.company_id == company_id)
            .where(ARTransaction.source_document_type == source_document_type)
            .where(ARTransaction.source_document_id == source_document_id)
            .where(ARTransaction.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_id_locked(self, id: UUID, company_id: UUID) -> ARTransaction | None:
        """``SELECT ... FOR UPDATE`` row lock (tasks.md T207) — serializes
        concurrent allocations against the same transaction. A no-op lock
        clause on dialects without row-level locking (e.g. SQLite in tests);
        real concurrency protection applies under PostgreSQL.
        """
        stmt = (
            select(ARTransaction)
            .where(ARTransaction.id == id)
            .where(ARTransaction.company_id == company_id)
            .where(ARTransaction.is_deleted == False)  # noqa: E712
            .with_for_update()
        )
        return self.db.execute(stmt).scalars().one_or_none()


class ARPaymentAllocationRepository(BaseAccountingRepository[ARPaymentAllocation]):
    """Data-access layer for the ``accounting_ar_allocations`` table (Phase 9 populates this)."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ARPaymentAllocation)

    def find_by_transaction(
        self, company_id: UUID, ar_transaction_id: UUID
    ) -> list[ARPaymentAllocation]:
        stmt = (
            select(ARPaymentAllocation)
            .where(ARPaymentAllocation.company_id == company_id)
            .where(ARPaymentAllocation.ar_transaction_id == ar_transaction_id)
            .where(ARPaymentAllocation.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class CustomerCreditHistoryRepository(BaseAccountingRepository[CustomerCreditHistory]):
    """Data-access layer for the ``accounting_customer_credit_history`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerCreditHistory)

    def find_by_customer_ledger(
        self, company_id: UUID, customer_ledger_id: UUID
    ) -> list[CustomerCreditHistory]:
        stmt = (
            select(CustomerCreditHistory)
            .where(CustomerCreditHistory.company_id == company_id)
            .where(CustomerCreditHistory.customer_ledger_id == customer_ledger_id)
            .where(CustomerCreditHistory.is_deleted == False)  # noqa: E712
            .order_by(CustomerCreditHistory.occurred_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

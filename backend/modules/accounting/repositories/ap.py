"""Repositories for Accounts Payable entities — Phase 7.

  SupplierLedgerRepository                    — ledger root CRUD + aging/statement queries
  APTransactionRepository                     — transaction CRUD
  APPaymentAllocationRepository               — allocation CRUD (Phase 9 populates this)
  SupplierStatementReconciliationRepository   — reconciliation session CRUD
  SupplierStatementReconciliationItemRepository — reconciliation line CRUD

Mirrors ``repositories/ar.py``'s design exactly.

Spec ref: specs/008-accounting-finance/tasks.md T161
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.ap import (
    APPaymentAllocation,
    APTransaction,
    SupplierLedger,
    SupplierStatementReconciliation,
    SupplierStatementReconciliationItem,
)
from modules.accounting.repositories import BaseAccountingRepository


class SupplierLedgerRepository(BaseAccountingRepository[SupplierLedger]):
    """Data-access layer for the ``accounting_supplier_ledgers`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierLedger)

    def find_by_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> SupplierLedger | None:
        stmt = (
            select(SupplierLedger)
            .where(SupplierLedger.company_id == company_id)
            .where(SupplierLedger.supplier_id == supplier_id)
            .where(SupplierLedger.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID) -> list[SupplierLedger]:
        stmt = (
            select(SupplierLedger)
            .where(SupplierLedger.company_id == company_id)
            .where(SupplierLedger.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_open_transactions(
        self, company_id: UUID, supplier_ledger_id: UUID
    ) -> list[APTransaction]:
        stmt = (
            select(APTransaction)
            .where(APTransaction.company_id == company_id)
            .where(APTransaction.supplier_ledger_id == supplier_ledger_id)
            .where(APTransaction.is_deleted == False)  # noqa: E712
            .where(
                APTransaction.status.in_(
                    ["OPEN", "PARTIALLY_PAID", "OVERDUE", "DISPUTED"]
                )
            )
            .order_by(APTransaction.transaction_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_aging_data(self, company_id: UUID, as_of_date: date) -> list[APTransaction]:
        """Return every open AP transaction across all suppliers, for aging calc.

        Aging is calculated from ``due_date`` (spec.md §19.3), not the
        transaction date — filtering/bucketing happens in ``AgingCalculator``.
        """
        stmt = (
            select(APTransaction)
            .where(APTransaction.company_id == company_id)
            .where(APTransaction.is_deleted == False)  # noqa: E712
            .where(
                APTransaction.status.in_(
                    ["OPEN", "PARTIALLY_PAID", "OVERDUE", "DISPUTED"]
                )
            )
            .where(APTransaction.transaction_date <= as_of_date)
            .order_by(APTransaction.supplier_ledger_id, APTransaction.due_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_statement_data(
        self, company_id: UUID, supplier_ledger_id: UUID, from_date: date, to_date: date
    ) -> list[APTransaction]:
        stmt = (
            select(APTransaction)
            .where(APTransaction.company_id == company_id)
            .where(APTransaction.supplier_ledger_id == supplier_ledger_id)
            .where(APTransaction.is_deleted == False)  # noqa: E712
            .where(APTransaction.transaction_date >= from_date)
            .where(APTransaction.transaction_date <= to_date)
            .order_by(APTransaction.transaction_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_opening_balance(
        self, company_id: UUID, supplier_ledger_id: UUID, before_date: date
    ) -> Decimal:
        stmt = select(APTransaction).where(
            APTransaction.company_id == company_id,
            APTransaction.supplier_ledger_id == supplier_ledger_id,
            APTransaction.is_deleted == False,  # noqa: E712
            APTransaction.transaction_date < before_date,
        )
        rows = self.db.execute(stmt).scalars().all()
        total = Decimal("0")
        for row in rows:
            sign = (
                Decimal("1")
                if row.transaction_type in ("BILL", "DEBIT_NOTE")
                else Decimal("-1")
            )
            total += sign * row.amount_base
        return total


class APTransactionRepository(BaseAccountingRepository[APTransaction]):
    """Data-access layer for the ``accounting_ap_transactions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=APTransaction)

    def find_bills_due_within_across_companies(
        self, as_of_date: date, days_ahead: int
    ) -> list[APTransaction]:
        """Cross-tenant scan for the daily bill-due-reminder job (tasks.md
        T166) — mirrors ``ARTransactionRepository.find_overdue_across_
        companies()``'s established cross-tenant scan pattern (Phase 6).
        """
        from datetime import timedelta

        horizon = as_of_date + timedelta(days=days_ahead)
        stmt = (
            select(APTransaction)
            .where(APTransaction.is_deleted == False)  # noqa: E712
            .where(APTransaction.status.in_(["OPEN", "PARTIALLY_PAID", "DISPUTED"]))
            .where(APTransaction.due_date.is_not(None))
            .where(APTransaction.due_date >= as_of_date)
            .where(APTransaction.due_date <= horizon)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_overdue_across_companies(self, as_of_date: date) -> list[APTransaction]:
        """Cross-tenant scan mirroring the AR overdue job — used to flag
        AP transactions OVERDUE (tasks.md T165's reconciliation context).
        """
        stmt = (
            select(APTransaction)
            .where(APTransaction.is_deleted == False)  # noqa: E712
            .where(APTransaction.status.in_(["OPEN", "PARTIALLY_PAID", "DISPUTED"]))
            .where(APTransaction.due_date.is_not(None))
            .where(APTransaction.due_date < as_of_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_source_document(
        self, company_id: UUID, source_document_type: str, source_document_id: UUID
    ) -> APTransaction | None:
        stmt = (
            select(APTransaction)
            .where(APTransaction.company_id == company_id)
            .where(APTransaction.source_document_type == source_document_type)
            .where(APTransaction.source_document_id == source_document_id)
            .where(APTransaction.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_id_locked(self, id: UUID, company_id: UUID) -> APTransaction | None:
        """``SELECT ... FOR UPDATE`` row lock (tasks.md T207) — mirrors
        ``ARTransactionRepository.get_by_id_locked()``.
        """
        stmt = (
            select(APTransaction)
            .where(APTransaction.id == id)
            .where(APTransaction.company_id == company_id)
            .where(APTransaction.is_deleted == False)  # noqa: E712
            .with_for_update()
        )
        return self.db.execute(stmt).scalars().one_or_none()


class APPaymentAllocationRepository(BaseAccountingRepository[APPaymentAllocation]):
    """Data-access layer for the ``accounting_ap_allocations`` table (Phase 9 populates this)."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=APPaymentAllocation)

    def find_by_transaction(
        self, company_id: UUID, ap_transaction_id: UUID
    ) -> list[APPaymentAllocation]:
        stmt = (
            select(APPaymentAllocation)
            .where(APPaymentAllocation.company_id == company_id)
            .where(APPaymentAllocation.ap_transaction_id == ap_transaction_id)
            .where(APPaymentAllocation.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_payment(
        self, company_id: UUID, payment_id: UUID
    ) -> list[APPaymentAllocation]:
        """All allocation lines for a given payment — the raw material for
        ``AccountsPayableService.generate_remittance_advice()`` (T162).
        Returns empty until Phase 9 populates this table (no ``Payment``
        entity exists yet to produce these rows), mirroring AR's identical
        deferral for ``ARPaymentAllocationRepository``.
        """
        stmt = (
            select(APPaymentAllocation)
            .where(APPaymentAllocation.company_id == company_id)
            .where(APPaymentAllocation.payment_id == payment_id)
            .where(APPaymentAllocation.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class SupplierStatementReconciliationRepository(
    BaseAccountingRepository[SupplierStatementReconciliation]
):
    """Data-access layer for the ``accounting_supplier_reconciliations`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierStatementReconciliation)

    def find_by_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[SupplierStatementReconciliation]:
        stmt = (
            select(SupplierStatementReconciliation)
            .where(SupplierStatementReconciliation.company_id == company_id)
            .where(SupplierStatementReconciliation.supplier_id == supplier_id)
            .where(SupplierStatementReconciliation.is_deleted == False)  # noqa: E712
            .order_by(SupplierStatementReconciliation.statement_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())


class SupplierStatementReconciliationItemRepository(
    BaseAccountingRepository[SupplierStatementReconciliationItem]
):
    """Data-access layer for the ``accounting_supplier_reconciliation_items`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierStatementReconciliationItem)

    def find_by_reconciliation(
        self, company_id: UUID, reconciliation_id: UUID
    ) -> list[SupplierStatementReconciliationItem]:
        stmt = (
            select(SupplierStatementReconciliationItem)
            .where(SupplierStatementReconciliationItem.company_id == company_id)
            .where(
                SupplierStatementReconciliationItem.reconciliation_id
                == reconciliation_id
            )
            .where(
                SupplierStatementReconciliationItem.is_deleted == False  # noqa: E712
            )
        )
        return list(self.db.execute(stmt).scalars().all())

"""Repositories for Banking entities — Phase 8.

  BankAccountRepository             — bank account CRUD
  BankTransactionRepository         — transaction CRUD + unreconciled scan
  BankStatementLineRepository       — statement line CRUD + unmatched scan
  BankReconciliationRepository      — reconciliation session CRUD
  BankReconciliationMatchRepository — match CRUD
  ChequeRepository                  — cheque register CRUD

Spec ref: specs/008-accounting-finance/tasks.md T175-T180
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.accounting.models.banking import (
    BankAccount,
    BankReconciliation,
    BankReconciliationMatch,
    BankStatementLine,
    BankTransaction,
    Cheque,
)
from modules.accounting.repositories import BaseAccountingRepository


class BankAccountRepository(BaseAccountingRepository[BankAccount]):
    """Data-access layer for the ``accounting_bank_accounts`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=BankAccount)

    def list_all(
        self, company_id: UUID, active_only: bool = False
    ) -> list[BankAccount]:
        stmt = (
            select(BankAccount)
            .where(BankAccount.company_id == company_id)
            .where(BankAccount.is_deleted == False)  # noqa: E712
        )
        if active_only:
            stmt = stmt.where(BankAccount.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())


class BankTransactionRepository(BaseAccountingRepository[BankTransaction]):
    """Data-access layer for the ``accounting_bank_transactions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=BankTransaction)

    def find_by_bank_account(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[BankTransaction]:
        """``from_date``/``to_date``/``limit``/``offset`` are optional,
        SQL-level bounds (Epic 11 Reports, additive seam) — omitting them
        reproduces the exact prior unbounded behavior for existing
        callers."""
        stmt = (
            select(BankTransaction)
            .where(BankTransaction.company_id == company_id)
            .where(BankTransaction.bank_account_id == bank_account_id)
            .where(BankTransaction.is_deleted == False)  # noqa: E712
        )
        if from_date is not None:
            stmt = stmt.where(BankTransaction.transaction_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(BankTransaction.transaction_date <= to_date)
        # BankTransaction.id: unique tiebreaker (Epic 11 T270) — same-day rows would
        # otherwise come back in unspecified order across offset pages.
        stmt = stmt.order_by(BankTransaction.transaction_date, BankTransaction.id)
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_bank_transactions(
        self,
        company_id: UUID,
        bank_account_id: UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> int:
        """Epic 11 Reports additive seam — cheap SQL-level count mirroring
        ``find_by_bank_account``'s filter."""
        stmt = (
            select(func.count())
            .select_from(BankTransaction)
            .where(BankTransaction.company_id == company_id)
            .where(BankTransaction.bank_account_id == bank_account_id)
            .where(BankTransaction.is_deleted == False)  # noqa: E712
        )
        if from_date is not None:
            stmt = stmt.where(BankTransaction.transaction_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(BankTransaction.transaction_date <= to_date)
        return int(self.db.execute(stmt).scalar_one())

    def find_unreconciled(
        self, company_id: UUID, bank_account_id: UUID
    ) -> list[BankTransaction]:
        stmt = (
            select(BankTransaction)
            .where(BankTransaction.company_id == company_id)
            .where(BankTransaction.bank_account_id == bank_account_id)
            .where(BankTransaction.is_deleted == False)  # noqa: E712
            .where(BankTransaction.is_reconciled == False)  # noqa: E712
            .order_by(BankTransaction.transaction_date)
        )
        return list(self.db.execute(stmt).scalars().all())


class BankStatementLineRepository(BaseAccountingRepository[BankStatementLine]):
    """Data-access layer for the ``accounting_bank_statement_lines`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=BankStatementLine)

    def find_by_bank_account(
        self, company_id: UUID, bank_account_id: UUID
    ) -> list[BankStatementLine]:
        stmt = (
            select(BankStatementLine)
            .where(BankStatementLine.company_id == company_id)
            .where(BankStatementLine.bank_account_id == bank_account_id)
            .where(BankStatementLine.is_deleted == False)  # noqa: E712
            .order_by(BankStatementLine.statement_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_many(self, lines: list[BankStatementLine]) -> list[BankStatementLine]:
        """Persist many lines in a single commit — used by bulk statement
        import (T301), where the inherited ``create()``'s commit-per-row
        cost (measured at ~13ms/row) does not scale to a realistic
        multi-thousand-line statement import."""
        self.db.add_all(lines)
        self.db.commit()
        for line in lines:
            self.db.refresh(line)
        return lines

    def find_unmatched(
        self, company_id: UUID, bank_account_id: UUID
    ) -> list[BankStatementLine]:
        stmt = (
            select(BankStatementLine)
            .where(BankStatementLine.company_id == company_id)
            .where(BankStatementLine.bank_account_id == bank_account_id)
            .where(BankStatementLine.is_deleted == False)  # noqa: E712
            .where(BankStatementLine.is_matched == False)  # noqa: E712
            .order_by(BankStatementLine.statement_date)
        )
        return list(self.db.execute(stmt).scalars().all())


class BankReconciliationRepository(BaseAccountingRepository[BankReconciliation]):
    """Data-access layer for the ``accounting_bank_reconciliations`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=BankReconciliation)

    def find_by_bank_account(
        self, company_id: UUID, bank_account_id: UUID
    ) -> list[BankReconciliation]:
        stmt = (
            select(BankReconciliation)
            .where(BankReconciliation.company_id == company_id)
            .where(BankReconciliation.bank_account_id == bank_account_id)
            .where(BankReconciliation.is_deleted == False)  # noqa: E712
            .order_by(BankReconciliation.statement_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())


class BankReconciliationMatchRepository(
    BaseAccountingRepository[BankReconciliationMatch]
):
    """Data-access layer for the ``accounting_bank_reconciliation_matches`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=BankReconciliationMatch)

    def find_by_reconciliation(
        self, company_id: UUID, reconciliation_id: UUID
    ) -> list[BankReconciliationMatch]:
        stmt = (
            select(BankReconciliationMatch)
            .where(BankReconciliationMatch.company_id == company_id)
            .where(BankReconciliationMatch.reconciliation_id == reconciliation_id)
            .where(BankReconciliationMatch.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class ChequeRepository(BaseAccountingRepository[Cheque]):
    """Data-access layer for the ``accounting_cheques`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Cheque)

    def list_all(self, company_id: UUID, status: str | None = None) -> list[Cheque]:
        stmt = (
            select(Cheque)
            .where(Cheque.company_id == company_id)
            .where(Cheque.is_deleted == False)  # noqa: E712
        )
        if status is not None:
            stmt = stmt.where(Cheque.status == status)
        return list(self.db.execute(stmt).scalars().all())

    def find_by_bank_account(
        self, company_id: UUID, bank_account_id: UUID
    ) -> list[Cheque]:
        stmt = (
            select(Cheque)
            .where(Cheque.company_id == company_id)
            .where(Cheque.bank_account_id == bank_account_id)
            .where(Cheque.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

"""Repositories for Cash Management entities — Phase 9.

  CashAccountRepository        — cash account CRUD
  CashTransactionRepository    — transaction CRUD + cash-book range scan
  PettyCashVoucherRepository   — voucher CRUD + unreplenished scan
  CashReconciliationRepository — reconciliation record CRUD

Spec ref: specs/008-accounting-finance/tasks.md T192-T195
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.cash import (
    CashAccount,
    CashReconciliation,
    CashTransaction,
    PettyCashVoucher,
)
from modules.accounting.repositories import BaseAccountingRepository


class CashAccountRepository(BaseAccountingRepository[CashAccount]):
    """Data-access layer for the ``accounting_cash_accounts`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CashAccount)

    def list_all(
        self, company_id: UUID, active_only: bool = False
    ) -> list[CashAccount]:
        stmt = (
            select(CashAccount)
            .where(CashAccount.company_id == company_id)
            .where(CashAccount.is_deleted == False)  # noqa: E712
        )
        if active_only:
            stmt = stmt.where(CashAccount.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())

    def get_petty_cash_accounts(self, company_id: UUID) -> list[CashAccount]:
        stmt = (
            select(CashAccount)
            .where(CashAccount.company_id == company_id)
            .where(CashAccount.is_deleted == False)  # noqa: E712
            .where(CashAccount.is_petty_cash == True)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class CashTransactionRepository(BaseAccountingRepository[CashTransaction]):
    """Data-access layer for the ``accounting_cash_transactions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CashTransaction)

    def find_by_cash_account(
        self, company_id: UUID, cash_account_id: UUID
    ) -> list[CashTransaction]:
        stmt = (
            select(CashTransaction)
            .where(CashTransaction.company_id == company_id)
            .where(CashTransaction.cash_account_id == cash_account_id)
            .where(CashTransaction.is_deleted == False)  # noqa: E712
            .order_by(CashTransaction.transaction_date)
        )
        return list(self.db.execute(stmt).scalars().all())


class PettyCashVoucherRepository(BaseAccountingRepository[PettyCashVoucher]):
    """Data-access layer for the ``accounting_petty_cash_vouchers`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PettyCashVoucher)

    def find_by_cash_account(
        self, company_id: UUID, cash_account_id: UUID
    ) -> list[PettyCashVoucher]:
        stmt = (
            select(PettyCashVoucher)
            .where(PettyCashVoucher.company_id == company_id)
            .where(PettyCashVoucher.cash_account_id == cash_account_id)
            .where(PettyCashVoucher.is_deleted == False)  # noqa: E712
            .order_by(PettyCashVoucher.voucher_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_unreplenished(
        self, company_id: UUID, cash_account_id: UUID
    ) -> list[PettyCashVoucher]:
        stmt = (
            select(PettyCashVoucher)
            .where(PettyCashVoucher.company_id == company_id)
            .where(PettyCashVoucher.cash_account_id == cash_account_id)
            .where(PettyCashVoucher.is_deleted == False)  # noqa: E712
            .where(PettyCashVoucher.journal_entry_id.is_(None))
            .order_by(PettyCashVoucher.voucher_date)
        )
        return list(self.db.execute(stmt).scalars().all())


class CashReconciliationRepository(BaseAccountingRepository[CashReconciliation]):
    """Data-access layer for the ``accounting_cash_reconciliations`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CashReconciliation)

    def find_by_cash_account(
        self, company_id: UUID, cash_account_id: UUID
    ) -> list[CashReconciliation]:
        stmt = (
            select(CashReconciliation)
            .where(CashReconciliation.company_id == company_id)
            .where(CashReconciliation.cash_account_id == cash_account_id)
            .where(CashReconciliation.is_deleted == False)  # noqa: E712
            .order_by(CashReconciliation.reconciliation_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

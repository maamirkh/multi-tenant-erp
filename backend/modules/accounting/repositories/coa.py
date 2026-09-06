"""Repositories for Chart of Accounts entities — Phase 2.

  AccountGroupRepository — account group hierarchy
  AccountRepository      — individual ledger accounts

Tree traversal follows the same pattern already established by
``modules.inventory.repositories.category_repository`` (Epic 5): fetch the
full flat, ordered list of nodes scoped to the company; the caller (service
layer or frontend) builds the nested hierarchy view from ``parent_*_id``
references. This keeps the query simple and avoids a raw recursive CTE where
practical COA depth is small (research.md Decision 12: ~5 levels typical).

Spec ref: specs/008-accounting-finance/tasks.md T052
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.repositories import BaseAccountingRepository


class AccountGroupRepository(BaseAccountingRepository[AccountGroup]):
    """Data-access layer for the ``accounting_account_groups`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=AccountGroup)

    def find_by_code(self, company_id: UUID, group_code: str) -> AccountGroup | None:
        stmt = (
            select(AccountGroup)
            .where(AccountGroup.company_id == company_id)
            .where(AccountGroup.group_code == group_code)
            .where(AccountGroup.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID) -> list[AccountGroup]:
        """Return all active account groups for a company, tree-display order."""
        stmt = (
            select(AccountGroup)
            .where(AccountGroup.company_id == company_id)
            .where(AccountGroup.is_deleted == False)  # noqa: E712
            .order_by(
                AccountGroup.account_type,
                AccountGroup.display_order,
                AccountGroup.group_name,
            )
        )
        return list(self.db.execute(stmt).scalars().all())


class AccountRepository(BaseAccountingRepository[Account]):
    """Data-access layer for the ``accounting_accounts`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Account)

    def find_by_code(self, company_id: UUID, account_code: str) -> Account | None:
        """Return the account with this code for the company, or None."""
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.account_code == account_code)
            .where(Account.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_active_leaf_accounts(
        self, company_id: UUID, account_type: str | None = None
    ) -> list[Account]:
        """Return active, leaf-level accounts (the only accounts postable to)."""
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.is_deleted == False)  # noqa: E712
            .where(Account.is_active == True)  # noqa: E712
            .where(Account.is_leaf == True)  # noqa: E712
        )
        if account_type is not None:
            stmt = stmt.where(Account.account_type == account_type)
        return list(
            self.db.execute(stmt.order_by(Account.account_code)).scalars().all()
        )

    def find_by_type(self, company_id: UUID, account_type: str) -> list[Account]:
        """Return all accounts of a given type (leaf and parent), ordered by code."""
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.account_type == account_type)
            .where(Account.is_deleted == False)  # noqa: E712
            .order_by(Account.account_code)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_coa_tree(self, company_id: UUID) -> list[Account]:
        """Return the full flat, ordered account list for tree construction.

        Ordered by account_type (Asset/Liability/Equity/Revenue/Expense) then
        account_code so the caller can build the nested tree deterministically.
        """
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.is_deleted == False)  # noqa: E712
            .order_by(Account.account_type, Account.account_code)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_children(self, company_id: UUID, parent_account_id: UUID) -> list[Account]:
        """Return direct children of a parent account."""
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.parent_account_id == parent_account_id)
            .where(Account.is_deleted == False)  # noqa: E712
            .order_by(Account.account_code)
        )
        return list(self.db.execute(stmt).scalars().all())

    def search(self, company_id: UUID, query: str, limit: int = 50) -> list[Account]:
        """Search accounts by code or name (case-insensitive substring match)."""
        pattern = f"%{query.lower()}%"
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.is_deleted == False)  # noqa: E712
            .where(
                (Account.account_code.ilike(pattern))
                | (Account.account_name.ilike(pattern))
            )
            .order_by(Account.account_code)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

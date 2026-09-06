"""Integration tests for AccountRepository and AccountGroupRepository.

Tests:
  - Account CRUD
  - Account code uniqueness per company (DB-level unique constraint)
  - COA tree query (flat, ordered)
  - Cross-company isolation
  - Soft-delete exclusion from queries
  - find_active_leaf_accounts / find_by_type / search

Spec ref: specs/008-accounting-finance/tasks.md T065
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)


class TestAccountRepositoryCRUD:
    def test_create_and_get_by_id(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        account = repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Cash",
                account_type="ASSET",
            )
        )
        fetched = repo.get_by_id(id=account.id, company_id=company_id)
        assert fetched.account_code == "1000"
        assert fetched.is_active is True
        assert fetched.is_leaf is True

    def test_find_by_code(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        repo.create(
            Account(
                company_id=company_id,
                account_code="2000",
                account_name="Accounts Payable",
                account_type="LIABILITY",
            )
        )
        found = repo.find_by_code(company_id=company_id, account_code="2000")
        assert found is not None
        assert found.account_name == "Accounts Payable"

    def test_soft_delete_excludes_from_queries(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        account = repo.create(
            Account(
                company_id=company_id,
                account_code="3000",
                account_name="Share Capital",
                account_type="EQUITY",
            )
        )
        repo.soft_delete(id=account.id, company_id=company_id)
        assert repo.find_by_code(company_id=company_id, account_code="3000") is None


class TestAccountCodeUniquenessDbLevel:
    def test_duplicate_code_same_company_raises_integrity_error(
        self, db_session: Session
    ) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Cash",
                account_type="ASSET",
            )
        )
        with pytest.raises(IntegrityError):
            repo.create(
                Account(
                    company_id=company_id,
                    account_code="1000",
                    account_name="Cash Dup",
                    account_type="ASSET",
                )
            )
        db_session.rollback()


class TestCOATreeQuery:
    def test_get_coa_tree_ordered_by_type_then_code(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        repo.create(
            Account(
                company_id=company_id,
                account_code="4000",
                account_name="Revenue",
                account_type="REVENUE",
            )
        )
        repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Cash",
                account_type="ASSET",
            )
        )
        flat = repo.get_coa_tree(company_id=company_id)
        assert [a.account_code for a in flat] == ["1000", "4000"]

    def test_find_children(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        parent = repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Assets",
                account_type="ASSET",
                is_leaf=False,
            )
        )
        repo.create(
            Account(
                company_id=company_id,
                account_code="1010",
                account_name="Cash",
                account_type="ASSET",
                parent_account_id=parent.id,
            )
        )
        children = repo.find_children(
            company_id=company_id, parent_account_id=parent.id
        )
        assert len(children) == 1
        assert children[0].account_code == "1010"


class TestCrossCompanyIsolation:
    def test_find_by_code_scoped_to_company(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_a, company_b = uuid4(), uuid4()
        repo.create(
            Account(
                company_id=company_a,
                account_code="1000",
                account_name="A's Cash",
                account_type="ASSET",
            )
        )
        assert repo.find_by_code(company_id=company_b, account_code="1000") is None

    def test_get_coa_tree_scoped_to_company(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_a, company_b = uuid4(), uuid4()
        repo.create(
            Account(
                company_id=company_a,
                account_code="1000",
                account_name="A's Cash",
                account_type="ASSET",
            )
        )
        assert repo.get_coa_tree(company_id=company_b) == []


class TestFindActiveLeafAndByType:
    def test_find_active_leaf_accounts_excludes_non_leaf_and_inactive(
        self, db_session: Session
    ) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        parent = repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Assets",
                account_type="ASSET",
                is_leaf=False,
            )
        )
        leaf_active = repo.create(
            Account(
                company_id=company_id,
                account_code="1010",
                account_name="Cash",
                account_type="ASSET",
                parent_account_id=parent.id,
            )
        )
        leaf_inactive = repo.create(
            Account(
                company_id=company_id,
                account_code="1020",
                account_name="Old Bank",
                account_type="ASSET",
                parent_account_id=parent.id,
            )
        )
        leaf_inactive.is_active = False
        repo.update(leaf_inactive)

        results = repo.find_active_leaf_accounts(company_id=company_id)
        codes = {a.account_code for a in results}
        assert codes == {"1010"}
        assert parent.account_code not in codes
        assert leaf_active.account_code in codes

    def test_find_by_type(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Cash",
                account_type="ASSET",
            )
        )
        repo.create(
            Account(
                company_id=company_id,
                account_code="2000",
                account_name="AP",
                account_type="LIABILITY",
            )
        )
        assets = repo.find_by_type(company_id=company_id, account_type="ASSET")
        assert len(assets) == 1
        assert assets[0].account_code == "1000"

    def test_search_by_name_or_code(self, db_session: Session) -> None:
        repo = AccountRepository(db_session)
        company_id = uuid4()
        repo.create(
            Account(
                company_id=company_id,
                account_code="1000",
                account_name="Petty Cash",
                account_type="ASSET",
            )
        )
        by_name = repo.search(company_id=company_id, query="petty")
        by_code = repo.search(company_id=company_id, query="1000")
        assert len(by_name) == 1
        assert len(by_code) == 1


class TestAccountGroupRepository:
    def test_create_and_find_by_code(self, db_session: Session) -> None:
        repo = AccountGroupRepository(db_session)
        company_id = uuid4()
        repo.create(
            AccountGroup(
                company_id=company_id,
                group_code="CUR-AST",
                group_name="Current Assets",
                account_type="ASSET",
            )
        )
        found = repo.find_by_code(company_id=company_id, group_code="CUR-AST")
        assert found is not None
        assert found.group_name == "Current Assets"

    def test_list_all_ordered(self, db_session: Session) -> None:
        repo = AccountGroupRepository(db_session)
        company_id = uuid4()
        repo.create(
            AccountGroup(
                company_id=company_id,
                group_code="FIX-AST",
                group_name="Fixed Assets",
                account_type="ASSET",
                display_order=2,
            )
        )
        repo.create(
            AccountGroup(
                company_id=company_id,
                group_code="CUR-AST",
                group_name="Current Assets",
                account_type="ASSET",
                display_order=1,
            )
        )
        groups = repo.list_all(company_id=company_id)
        assert [g.group_code for g in groups] == ["CUR-AST", "FIX-AST"]

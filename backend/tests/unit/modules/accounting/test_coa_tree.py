"""Unit tests for COA tree traversal (ChartOfAccountsService.get_coa_tree).

Tests:
  - Parent-child relationships are correctly nested
  - Root accounts (no parent) have no parent and appear at top level
  - Leaf accounts have no children
  - Multi-level nesting (grandchildren) resolves correctly

Spec ref: specs/008-accounting-finance/tasks.md T064
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)
from modules.accounting.repositories.feature_flag_repository import (
    AccountingFeatureFlagRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.services.coa_service import ChartOfAccountsService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)


@pytest.fixture
def coa_service(db_session: Session) -> ChartOfAccountsService:
    return ChartOfAccountsService(
        db=db_session,
        account_repo=AccountRepository(db_session),
        group_repo=AccountGroupRepository(db_session),
        config_repo=AccountingConfigurationRepository(db_session),
        flag_service=AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        ),
    )


def _find_node(nodes: list[dict], account_code: str) -> dict | None:
    for node in nodes:
        if node["account_code"] == account_code:
            return node
        found = _find_node(node["children"], account_code)
        if found is not None:
            return found
    return None


class TestCOATreeTraversal:
    def test_root_accounts_have_no_parent_and_appear_at_top_level(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Assets",
            account_type="ASSET",
            is_leaf=False,
        )
        tree = coa_service.get_coa_tree(company_id=company_id)
        assert len(tree) == 1
        assert tree[0]["account_code"] == "1000"

    def test_parent_child_relationship_nested_correctly(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        parent = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Current Assets",
            account_type="ASSET",
            is_leaf=False,
        )
        coa_service.create_account(
            company_id=company_id,
            account_code="1010",
            account_name="Cash",
            account_type="ASSET",
            parent_account_id=parent.id,
        )
        coa_service.create_account(
            company_id=company_id,
            account_code="1020",
            account_name="Bank",
            account_type="ASSET",
            parent_account_id=parent.id,
        )

        tree = coa_service.get_coa_tree(company_id=company_id)
        assert len(tree) == 1  # only the root parent at top level
        root = tree[0]
        assert root["account_code"] == "1000"
        assert len(root["children"]) == 2
        child_codes = {c["account_code"] for c in root["children"]}
        assert child_codes == {"1010", "1020"}

    def test_leaf_accounts_have_no_children(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        coa_service.create_account(
            company_id=company_id,
            account_code="1010",
            account_name="Cash",
            account_type="ASSET",
        )
        tree = coa_service.get_coa_tree(company_id=company_id)
        node = _find_node(tree, "1010")
        assert node is not None
        assert node["is_leaf"] is True
        assert node["children"] == []

    def test_multi_level_nesting_grandchildren(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        grandparent = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Assets",
            account_type="ASSET",
            is_leaf=False,
        )
        parent = coa_service.create_account(
            company_id=company_id,
            account_code="1100",
            account_name="Current Assets",
            account_type="ASSET",
            is_leaf=False,
            parent_account_id=grandparent.id,
        )
        coa_service.create_account(
            company_id=company_id,
            account_code="1110",
            account_name="Cash",
            account_type="ASSET",
            parent_account_id=parent.id,
        )

        tree = coa_service.get_coa_tree(company_id=company_id)
        assert len(tree) == 1
        root = tree[0]
        assert root["account_code"] == "1000"
        assert len(root["children"]) == 1
        mid = root["children"][0]
        assert mid["account_code"] == "1100"
        assert len(mid["children"]) == 1
        assert mid["children"][0]["account_code"] == "1110"

    def test_company_isolation_in_tree(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_a, company_b = uuid4(), uuid4()
        coa_service.create_account(
            company_id=company_a,
            account_code="1000",
            account_name="A's Cash",
            account_type="ASSET",
        )
        coa_service.create_account(
            company_id=company_b,
            account_code="2000",
            account_name="B's Cash",
            account_type="ASSET",
        )
        tree_a = coa_service.get_coa_tree(company_id=company_a)
        codes_a = {n["account_code"] for n in tree_a}
        assert codes_a == {"1000"}

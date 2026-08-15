"""Unit/service-level tests for ChartOfAccountsService invariants.

Tests:
  - Account code uniqueness enforced per company
  - Leaf-only posting invariant (AccountInvariantValidator)
  - Deactivation blocked when active children exist
  - Deactivation allowed when children are all inactive
  - Account type validation (system account role type-matching)
  - Industry template application creates groups + accounts idempotently

Spec ref: specs/008-accounting-finance/tasks.md T063
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.exceptions import (
    AccountDeactivationBlockedError,
    DuplicateAccountCodeError,
    InvalidSystemAccountTypeError,
    NonLeafPostingError,
)
from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)
from modules.accounting.repositories.feature_flag_repository import (
    AccountingFeatureFlagRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.services.coa_service import (
    AccountInvariantValidator,
    ChartOfAccountsService,
)
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


class TestAccountCodeUniqueness:
    def test_duplicate_code_same_company_raises(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
        with pytest.raises(DuplicateAccountCodeError):
            coa_service.create_account(
                company_id=company_id,
                account_code="1000",
                account_name="Cash Duplicate",
                account_type="ASSET",
            )

    def test_same_code_different_companies_allowed(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_a, company_b = uuid4(), uuid4()
        acc_a = coa_service.create_account(
            company_id=company_a,
            account_code="1000",
            account_name="Cash A",
            account_type="ASSET",
        )
        acc_b = coa_service.create_account(
            company_id=company_b,
            account_code="1000",
            account_name="Cash B",
            account_type="ASSET",
        )
        assert acc_a.account_code == acc_b.account_code
        assert acc_a.company_id != acc_b.company_id

    def test_update_to_conflicting_code_raises(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
        acc2 = coa_service.create_account(
            company_id=company_id,
            account_code="1001",
            account_name="Bank",
            account_type="ASSET",
        )
        with pytest.raises(DuplicateAccountCodeError):
            coa_service.update_account(
                company_id=company_id, account_id=acc2.id, account_code="1000"
            )

    def test_update_keeping_same_code_does_not_raise(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        acc = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
        updated = coa_service.update_account(
            company_id=company_id,
            account_id=acc.id,
            account_code="1000",
            account_name="Cash Renamed",
        )
        assert updated.account_name == "Cash Renamed"


class TestLeafOnlyPosting:
    def test_leaf_account_passes_validation(self) -> None:
        from modules.accounting.models.coa import Account

        account = Account(
            account_code="1000", account_name="Cash", account_type="ASSET", is_leaf=True
        )
        AccountInvariantValidator.validate_leaf_for_posting(account)  # no raise

    def test_non_leaf_account_raises(self) -> None:
        from modules.accounting.models.coa import Account

        account = Account(
            account_code="1000",
            account_name="Current Assets",
            account_type="ASSET",
            is_leaf=False,
        )
        with pytest.raises(NonLeafPostingError):
            AccountInvariantValidator.validate_leaf_for_posting(account)


class TestDeactivation:
    def test_deactivation_blocked_with_active_children(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        parent = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Assets Parent",
            account_type="ASSET",
            is_leaf=False,
        )
        coa_service.create_account(
            company_id=company_id,
            account_code="1001",
            account_name="Cash",
            account_type="ASSET",
            parent_account_id=parent.id,
        )
        with pytest.raises(AccountDeactivationBlockedError):
            coa_service.deactivate_account(company_id=company_id, account_id=parent.id)

    def test_deactivation_allowed_when_children_inactive(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        parent = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Assets Parent",
            account_type="ASSET",
            is_leaf=False,
        )
        child = coa_service.create_account(
            company_id=company_id,
            account_code="1001",
            account_name="Cash",
            account_type="ASSET",
            parent_account_id=parent.id,
        )
        coa_service.deactivate_account(company_id=company_id, account_id=child.id)
        deactivated_parent = coa_service.deactivate_account(
            company_id=company_id, account_id=parent.id
        )
        assert deactivated_parent.is_active is False

    def test_deactivation_allowed_leaf_with_no_children(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        account = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
        result = coa_service.deactivate_account(
            company_id=company_id, account_id=account.id
        )
        assert result.is_active is False

    def test_reactivation(self, coa_service: ChartOfAccountsService) -> None:
        company_id = uuid4()
        account = coa_service.create_account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
        coa_service.deactivate_account(company_id=company_id, account_id=account.id)
        reactivated = coa_service.activate_account(
            company_id=company_id, account_id=account.id
        )
        assert reactivated.is_active is True


class TestSystemAccountTypeValidation:
    def test_matching_type_succeeds(self, coa_service: ChartOfAccountsService) -> None:
        company_id = uuid4()
        ar_account = coa_service.create_account(
            company_id=company_id,
            account_code="1100",
            account_name="Accounts Receivable",
            account_type="ASSET",
        )
        coa_service.set_system_account(
            company_id=company_id,
            role="default_ar_account_id",
            account_id=ar_account.id,
        )
        config = coa_service._config_repo.get_for_company(company_id=company_id)
        assert config is not None
        assert config.default_ar_account_id == ar_account.id

    def test_mismatched_type_raises(self, coa_service: ChartOfAccountsService) -> None:
        company_id = uuid4()
        expense_account = coa_service.create_account(
            company_id=company_id,
            account_code="6000",
            account_name="Salaries",
            account_type="EXPENSE",
        )
        with pytest.raises(InvalidSystemAccountTypeError):
            coa_service.set_system_account(
                company_id=company_id,
                role="default_ar_account_id",  # requires ASSET
                account_id=expense_account.id,
            )

    def test_unknown_role_raises_value_error(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        account = coa_service.create_account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
        with pytest.raises(ValueError, match="Unknown system account role"):
            coa_service.set_system_account(
                company_id=company_id, role="not_a_real_role", account_id=account.id
            )


class TestTemplateApplication:
    def test_apply_generic_template_creates_accounts(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        created = coa_service.apply_template(
            company_id=company_id, template_key="GENERIC"
        )
        assert len(created) > 0
        tree = coa_service.list_accounts(company_id=company_id)
        assert len(tree) == len(created)

    def test_apply_template_is_idempotent(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        company_id = uuid4()
        first = coa_service.apply_template(company_id=company_id, template_key="RETAIL")
        second_run_created = coa_service.apply_template(
            company_id=company_id, template_key="RETAIL"
        )
        assert len(second_run_created) == 0
        assert len(first) > 0

    def test_unknown_template_raises(self, coa_service: ChartOfAccountsService) -> None:
        with pytest.raises(ValueError, match="Unknown COA template"):
            coa_service.apply_template(
                company_id=uuid4(), template_key="NOT_A_TEMPLATE"
            )

    def test_all_six_templates_are_applicable(
        self, coa_service: ChartOfAccountsService
    ) -> None:
        for key in (
            "RETAIL",
            "MANUFACTURING",
            "SERVICES",
            "CONSTRUCTION",
            "MEDICAL",
            "GENERIC",
        ):
            company_id = uuid4()
            created = coa_service.apply_template(
                company_id=company_id, template_key=key
            )
            assert len(created) > 0, f"Template {key} created no accounts"

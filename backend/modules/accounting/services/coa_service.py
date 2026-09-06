"""ChartOfAccountsService — Chart of Accounts application service.

Responsibilities:
  - CRUD for Account and AccountGroup
  - COA tree construction (nested view from the flat repository list)
  - System account configuration (AR/AP/Revenue/Expense/Tax control accounts)
  - Bulk import/export of accounts

``AccountInvariantValidator`` encapsulates the domain invariants that must
hold for every Account regardless of which service method touches it:
  - account_code unique per company (spec.md §13.5)
  - only leaf accounts accept postings (spec.md FR-008) — enforced fully by
    the PostingEngine in Phase 4; validated here defensively for callers
    that construct postings directly
  - a parent account cannot be deactivated while it has active children

NOTE on deactivation and GL activity: spec.md/plan.md require that an
account cannot be deactivated if it has GL activity in the current fiscal
year. The GL (``JournalLine``) does not exist until Phase 4, so that check
is a documented no-op in Phase 2 — see ``AccountInvariantValidator.
validate_deactivation`` docstring. It must be wired in when Phase 4 ships.

Spec ref: specs/008-accounting-finance/tasks.md T053, T054
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.constants import AccountType
from modules.accounting.exceptions import (
    AccountDeactivationBlockedError,
    AccountGroupNotFoundError,
    AccountNotFoundError,
    DuplicateAccountCodeError,
    InvalidSystemAccountTypeError,
    NonLeafPostingError,
)
from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.services.coa_templates import get_template
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)

logger = logging.getLogger(__name__)

#: Maps an AccountingConfiguration system-account field name to the
#: AccountType it must be assigned to (plan.md Phase 2 acceptance criteria).
SYSTEM_ACCOUNT_TYPE_REQUIREMENTS: dict[str, str] = {
    "default_ar_account_id": AccountType.ASSET.value,
    "default_ap_account_id": AccountType.LIABILITY.value,
    "default_retained_earnings_account_id": AccountType.EQUITY.value,
    "default_exchange_gain_account_id": AccountType.REVENUE.value,
    "default_exchange_loss_account_id": AccountType.EXPENSE.value,
    "default_bad_debt_account_id": AccountType.EXPENSE.value,
    "default_revenue_account_id": AccountType.REVENUE.value,
    "default_expense_account_id": AccountType.EXPENSE.value,
    "default_tax_liability_account_id": AccountType.LIABILITY.value,
    "default_input_tax_account_id": AccountType.ASSET.value,
}


class AccountInvariantValidator:
    """Stateless domain invariant checks for Account entities."""

    @staticmethod
    def validate_unique_code(
        repo: AccountRepository,
        company_id: UUID,
        account_code: str,
        exclude_account_id: UUID | None = None,
    ) -> None:
        """Raise ``DuplicateAccountCodeError`` if the code is already in use."""
        existing = repo.find_by_code(company_id=company_id, account_code=account_code)
        if existing is not None and existing.id != exclude_account_id:
            raise DuplicateAccountCodeError(account_code)

    @staticmethod
    def validate_leaf_for_posting(account: Account) -> None:
        """Raise ``NonLeafPostingError`` if this account cannot accept postings."""
        if not account.is_leaf:
            raise NonLeafPostingError(account.account_code)

    @staticmethod
    def validate_deactivation(
        repo: AccountRepository, company_id: UUID, account: Account
    ) -> None:
        """Raise ``AccountDeactivationBlockedError`` if deactivation is not allowed.

        Checks performed in Phase 2:
          - The account has no active child accounts.

        NOT YET CHECKED (documented gap — GL does not exist until Phase 4):
          - Whether the account has GL activity in the current fiscal year.
          This must be added when ``JournalLine`` ships in Phase 4.
        """
        children = repo.find_children(
            company_id=company_id, parent_account_id=account.id
        )
        active_children = [c for c in children if c.is_active]
        if active_children:
            raise AccountDeactivationBlockedError(
                account.account_code,
                reason=f"{len(active_children)} active child account(s) exist",
            )


class ChartOfAccountsService:
    """Application service for Chart of Accounts management.

    Args:
        db:               SQLAlchemy session.
        account_repo:     ``AccountRepository`` instance (injected).
        group_repo:       ``AccountGroupRepository`` instance (injected).
        config_repo:      ``AccountingConfigurationRepository`` instance (injected).
        flag_service:     ``AccountingFeatureFlagService`` instance (injected).
    """

    def __init__(
        self,
        db: Session,
        account_repo: AccountRepository,
        group_repo: AccountGroupRepository,
        config_repo: AccountingConfigurationRepository,
        flag_service: AccountingFeatureFlagService,
    ) -> None:
        self.db = db
        self._accounts = account_repo
        self._groups = group_repo
        self._config_repo = config_repo
        self._flags = flag_service

    # ------------------------------------------------------------------
    # Account CRUD
    # ------------------------------------------------------------------

    def create_account(
        self,
        company_id: UUID,
        account_code: str,
        account_name: str,
        account_type: str,
        account_group_id: UUID | None = None,
        parent_account_id: UUID | None = None,
        is_leaf: bool = True,
        currency_code: str | None = None,
        requires_cost_center: bool = False,
        is_bank_account: bool = False,
        is_cash_account: bool = False,
        tax_category: str | None = None,
        notes: str | None = None,
        created_by: UUID | None = None,
    ) -> Account:
        """Create a new account after validating the domain invariants."""
        AccountInvariantValidator.validate_unique_code(
            self._accounts, company_id, account_code
        )

        if account_group_id is not None:
            group = self._groups.get_by_id_or_none(
                id=account_group_id, company_id=company_id
            )
            if group is None:
                raise AccountGroupNotFoundError(str(account_group_id))

        if parent_account_id is not None:
            parent = self._accounts.get_by_id_or_none(
                id=parent_account_id, company_id=company_id
            )
            if parent is None:
                raise AccountNotFoundError(account_id=str(parent_account_id))

        account = Account(
            company_id=company_id,
            account_code=account_code,
            account_name=account_name,
            account_type=account_type,
            account_group_id=account_group_id,
            parent_account_id=parent_account_id,
            is_leaf=is_leaf,
            currency_code=currency_code,
            requires_cost_center=requires_cost_center,
            is_bank_account=is_bank_account,
            is_cash_account=is_cash_account,
            tax_category=tax_category,
            notes=notes,
            created_by=created_by,
        )
        return self._accounts.create(account)

    def get_account(self, company_id: UUID, account_id: UUID) -> Account:
        account = self._accounts.get_by_id_or_none(id=account_id, company_id=company_id)
        if account is None:
            raise AccountNotFoundError(account_id=str(account_id))
        return account

    def list_accounts(
        self, company_id: UUID, account_type: str | None = None
    ) -> list[Account]:
        """Return accounts for a company, optionally filtered by account type."""
        if account_type is not None:
            return self._accounts.find_by_type(company_id, account_type)
        return self._accounts.get_coa_tree(company_id=company_id)

    def list_account_groups(self, company_id: UUID) -> list[AccountGroup]:
        """Return all account groups for a company, in tree-display order."""
        return self._groups.list_all(company_id=company_id)

    def create_account_group(
        self,
        company_id: UUID,
        group_code: str,
        group_name: str,
        account_type: str,
        parent_group_id: UUID | None = None,
        display_order: int = 0,
        created_by: UUID | None = None,
    ) -> AccountGroup:
        """Create a new account group."""
        existing = self._groups.find_by_code(company_id, group_code)
        if existing is not None:
            from modules.accounting.exceptions import AccountingException

            raise AccountingException(
                message=f"Account group code '{group_code}' already exists for this company.",
                code="DUPLICATE_GROUP_CODE",
                details={"group_code": group_code},
                http_status=409,
            )
        group = AccountGroup(
            company_id=company_id,
            group_code=group_code,
            group_name=group_name,
            account_type=account_type,
            parent_group_id=parent_group_id,
            display_order=display_order,
            created_by=created_by,
        )
        return self._groups.create(group)

    def update_account(
        self,
        company_id: UUID,
        account_id: UUID,
        **updates: object,
    ) -> Account:
        """Update mutable fields on an existing account.

        If ``account_code`` is among ``updates``, uniqueness is re-validated
        excluding this account's own row.
        """
        account = self.get_account(company_id, account_id)

        new_code = updates.get("account_code")
        if isinstance(new_code, str) and new_code != account.account_code:
            AccountInvariantValidator.validate_unique_code(
                self._accounts, company_id, new_code, exclude_account_id=account_id
            )

        for key, value in updates.items():
            if value is not None and hasattr(account, key):
                setattr(account, key, value)

        return self._accounts.update(account)

    def activate_account(self, company_id: UUID, account_id: UUID) -> Account:
        account = self.get_account(company_id, account_id)
        account.is_active = True
        return self._accounts.update(account)

    def deactivate_account(self, company_id: UUID, account_id: UUID) -> Account:
        """Deactivate an account after validating it has no active children.

        See ``AccountInvariantValidator.validate_deactivation`` for the
        documented gap around current-year GL activity (Phase 4 dependency).
        """
        account = self.get_account(company_id, account_id)
        AccountInvariantValidator.validate_deactivation(
            self._accounts, company_id, account
        )
        account.is_active = False
        return self._accounts.update(account)

    # ------------------------------------------------------------------
    # Tree / hierarchy
    # ------------------------------------------------------------------

    def get_coa_tree(self, company_id: UUID) -> list[dict[str, Any]]:
        """Return the full COA as a nested tree structure.

        Root nodes are accounts with ``parent_account_id IS NULL``; each
        node carries its ``children`` list, built in Python from the flat,
        ordered repository result (matches the pattern already established
        by Inventory's Category tree — see repositories/coa.py docstring).
        """
        flat = self._accounts.get_coa_tree(company_id=company_id)
        by_id: dict[UUID, dict[str, object]] = {
            acc.id: self._to_tree_node(acc) for acc in flat
        }
        roots: list[dict[str, object]] = []
        for acc in flat:
            node = by_id[acc.id]
            if acc.parent_account_id is not None and acc.parent_account_id in by_id:
                children = by_id[acc.parent_account_id]["children"]
                assert isinstance(children, list)
                children.append(node)
            else:
                roots.append(node)
        return roots

    @staticmethod
    def _to_tree_node(account: Account) -> dict[str, object]:
        return {
            "id": account.id,
            "account_code": account.account_code,
            "account_name": account.account_name,
            "account_type": account.account_type,
            "is_leaf": account.is_leaf,
            "is_active": account.is_active,
            "children": [],
        }

    # ------------------------------------------------------------------
    # System accounts
    # ------------------------------------------------------------------

    def set_system_account(self, company_id: UUID, role: str, account_id: UUID) -> None:
        """Designate an account for a system role (AR, AP, Revenue, Tax, ...).

        Args:
            role: One of the keys in ``SYSTEM_ACCOUNT_TYPE_REQUIREMENTS``
                  (e.g. ``"default_ar_account_id"``).
            account_id: The account to designate.

        Raises:
            ValueError: If ``role`` is not a recognised system account role.
            AccountNotFoundError: If the account does not exist.
            InvalidSystemAccountTypeError: If the account's type does not
                match the role's required type.
        """
        expected_type = SYSTEM_ACCOUNT_TYPE_REQUIREMENTS.get(role)
        if expected_type is None:
            raise ValueError(
                f"Unknown system account role: '{role}'. "
                f"Valid roles: {sorted(SYSTEM_ACCOUNT_TYPE_REQUIREMENTS)}"
            )

        account = self.get_account(company_id, account_id)
        if account.account_type != expected_type:
            raise InvalidSystemAccountTypeError(
                role=role,
                account_code=account.account_code,
                expected_type=expected_type,
                actual_type=account.account_type,
            )

        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None:
            from modules.accounting.models.foundation import AccountingConfiguration

            config = self._config_repo.create(
                AccountingConfiguration(company_id=company_id)
            )
        setattr(config, role, account_id)
        self._config_repo.update(config)

    # ------------------------------------------------------------------
    # Industry templates
    # ------------------------------------------------------------------

    def apply_template(
        self, company_id: UUID, template_key: str, created_by: UUID | None = None
    ) -> list[Account]:
        """Load an industry COA template's groups and accounts for a company.

        Idempotent per group/account code: groups and accounts that already
        exist (matched by code) are left untouched rather than duplicated,
        so re-applying a template (or applying a second template) never
        raises a uniqueness conflict.

        Raises:
            ValueError: If ``template_key`` is not a recognised template.
        """
        template = get_template(template_key)

        group_id_by_code: dict[str, UUID] = {}
        for group_def in template.groups:
            existing_group = self._groups.find_by_code(company_id, group_def.group_code)
            if existing_group is not None:
                group_id_by_code[group_def.group_code] = existing_group.id
                continue
            created_group = self._groups.create(
                AccountGroup(
                    company_id=company_id,
                    group_code=group_def.group_code,
                    group_name=group_def.group_name,
                    account_type=group_def.account_type,
                    display_order=group_def.display_order,
                    created_by=created_by,
                )
            )
            group_id_by_code[group_def.group_code] = created_group.id

        created_accounts: list[Account] = []
        for account_def in template.accounts:
            if self._accounts.find_by_code(company_id, account_def.account_code):
                continue
            account = self.create_account(
                company_id=company_id,
                account_code=account_def.account_code,
                account_name=account_def.account_name,
                account_type=account_def.account_type,
                account_group_id=group_id_by_code.get(account_def.group_code),
                is_leaf=account_def.is_leaf,
                is_bank_account=account_def.is_bank_account,
                is_cash_account=account_def.is_cash_account,
                requires_cost_center=account_def.requires_cost_center,
                created_by=created_by,
            )
            created_accounts.append(account)
        return created_accounts

    # ------------------------------------------------------------------
    # Bulk import / export
    # ------------------------------------------------------------------

    def bulk_import_coa(
        self,
        company_id: UUID,
        rows: list[dict[str, Any]],
        created_by: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Bulk-import accounts from parsed CSV rows.

        Gated by the ``accounting.bulkimport.enabled`` feature flag. Each
        row is validated independently; a failure in one row does not abort
        the others — the caller receives a per-row result list for
        row-level error reporting (plan.md Phase 2 acceptance criteria).

        Args:
            rows: List of dicts with keys: account_code, account_name,
                  account_type, account_group_code (optional), is_leaf
                  (optional, default True).

        Returns:
            List of per-row result dicts: ``{"row": int, "success": bool,
            "account_code": str, "error": str | None}``.

        Raises:
            ValueError: If bulk import is disabled for this company.
        """
        if not self._flags.is_enabled(company_id, "accounting.bulkimport.enabled"):
            raise ValueError("Bulk COA import is disabled for this company.")

        results: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            code = row.get("account_code", "")
            try:
                group_id = None
                group_code = row.get("account_group_code")
                if group_code:
                    group = self._groups.find_by_code(company_id, group_code)
                    group_id = group.id if group else None

                self.create_account(
                    company_id=company_id,
                    account_code=code,
                    account_name=row["account_name"],
                    account_type=row["account_type"],
                    account_group_id=group_id,
                    is_leaf=row.get("is_leaf", True),
                    created_by=created_by,
                )
                results.append(
                    {"row": idx, "success": True, "account_code": code, "error": None}
                )
            except Exception as exc:  # noqa: BLE001 — row-level isolation by design
                results.append(
                    {
                        "row": idx,
                        "success": False,
                        "account_code": code,
                        "error": str(exc),
                    }
                )
        return results

    def export_coa(self, company_id: UUID) -> list[Account]:
        """Return all accounts for export (CSV rendering happens at the API layer)."""
        return self._accounts.get_coa_tree(company_id=company_id)

"""Pydantic v2 schemas for Chart of Accounts — Phase 2.

  AccountGroupCreate/Read
  AccountCreateRequest / AccountUpdateRequest / AccountResponse
  AccountTreeNode (recursive)
  COAImportRow / COAImportResultRow
  SystemAccountConfigRequest

Spec ref: specs/008-accounting-finance/tasks.md T055
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Account Group
# ---------------------------------------------------------------------------


class AccountGroupCreate(AccountingBaseSchema):
    """Request body for creating an account group."""

    group_code: str = Field(..., min_length=1, max_length=20)
    group_name: str = Field(..., min_length=1, max_length=200)
    account_type: str = Field(..., pattern="^(ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE)$")
    parent_group_id: UUID | None = None
    display_order: int = 0


class AccountGroupRead(AccountingBaseSchema):
    """Response schema for an account group."""

    id: UUID
    company_id: UUID
    group_code: str
    group_name: str
    account_type: str
    parent_group_id: UUID | None
    display_order: int
    is_active: bool


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


class AccountCreateRequest(AccountingBaseSchema):
    """Request body for creating an account."""

    account_code: str = Field(..., min_length=1, max_length=20)
    account_name: str = Field(..., min_length=1, max_length=200)
    account_type: str = Field(..., pattern="^(ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE)$")
    account_group_id: UUID | None = None
    parent_account_id: UUID | None = None
    is_leaf: bool = True
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    requires_cost_center: bool = False
    is_bank_account: bool = False
    is_cash_account: bool = False
    tax_category: str | None = None
    notes: str | None = None


class AccountUpdateRequest(AccountingBaseSchema):
    """Request body for updating an account. All fields optional."""

    account_code: str | None = Field(None, min_length=1, max_length=20)
    account_name: str | None = Field(None, min_length=1, max_length=200)
    account_group_id: UUID | None = None
    parent_account_id: UUID | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    requires_cost_center: bool | None = None
    is_bank_account: bool | None = None
    is_cash_account: bool | None = None
    tax_category: str | None = None
    notes: str | None = None


class AccountResponse(AccountingBaseSchema):
    """Response schema for an account, with nested group and type context."""

    id: UUID
    company_id: UUID
    account_code: str
    account_name: str
    account_type: str
    account_group_id: UUID | None
    parent_account_id: UUID | None
    is_leaf: bool
    currency_code: str | None
    requires_cost_center: bool
    is_bank_account: bool
    is_cash_account: bool
    is_active: bool
    tax_category: str | None
    notes: str | None


class AccountTreeNode(AccountingBaseSchema):
    """Recursive tree node for the COA hierarchy view (``?tree=true``)."""

    id: UUID
    account_code: str
    account_name: str
    account_type: str
    is_leaf: bool
    is_active: bool
    children: list[AccountTreeNode] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bulk import / export
# ---------------------------------------------------------------------------


class COAImportRow(AccountingBaseSchema):
    """A single row of a bulk COA CSV import."""

    account_code: str
    account_name: str
    account_type: str = Field(..., pattern="^(ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE)$")
    account_group_code: str | None = None
    is_leaf: bool = True


class COAImportResultRow(AccountingBaseSchema):
    """Per-row result of a bulk COA import — enables row-level error reporting."""

    row: int
    success: bool
    account_code: str
    error: str | None = None


# ---------------------------------------------------------------------------
# System accounts
# ---------------------------------------------------------------------------


class SystemAccountConfigRequest(AccountingBaseSchema):
    """Request body for designating a system account role."""

    role: str = Field(
        ...,
        description=(
            "One of: default_ar_account_id, default_ap_account_id, "
            "default_retained_earnings_account_id, default_exchange_gain_account_id, "
            "default_exchange_loss_account_id, default_bad_debt_account_id, "
            "default_revenue_account_id, default_expense_account_id, "
            "default_tax_liability_account_id, default_input_tax_account_id"
        ),
    )
    account_id: UUID


class COATemplateApplyRequest(AccountingBaseSchema):
    """Request body for applying an industry COA template."""

    template_key: str = Field(
        ...,
        pattern="^(RETAIL|MANUFACTURING|SERVICES|CONSTRUCTION|MEDICAL|GENERIC)$",
    )


class COATemplateInfo(AccountingBaseSchema):
    """Response schema listing an available COA template."""

    key: str
    label: str

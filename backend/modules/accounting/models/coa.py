"""Chart of Accounts ORM models — Phase 2.

Phase 2 entities:
  AccountGroup — sub-classification within an account type (self-referencing)
  Account      — individual ledger account (leaf or parent/group node)

Both hang off the account-type root implicitly via ``account_type`` — there
is no separate "root" table row; Asset/Liability/Equity/Revenue/Expense are
represented purely by the ``account_type`` enum value (spec.md §13.4).

Spec ref: specs/008-accounting-finance/spec.md §13 Chart of Accounts
Data model: specs/008-accounting-finance/data-model.md §2.1 ChartOfAccounts
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class AccountGroup(TenantBaseModel):
    """Account group — sub-classification within an account type.

    Self-referencing hierarchy via ``parent_group_id`` (e.g. "Current Assets"
    under "Assets"). Spec ref: spec.md §13.3.

    Invariant: ``group_code`` unique per company (enforced by unique
    constraint + service-layer validation).
    """

    __tablename__ = "accounting_account_groups"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "group_code", name="uq_accounting_groups_company_code"
        ),
        CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name="ck_accounting_groups_type",
        ),
        {"comment": "Chart of Accounts group hierarchy, scoped per company"},
    )

    group_code: Mapped[str] = mapped_column(String(20), nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)

    parent_group_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_account_groups.id", ondelete="RESTRICT"),
        nullable=True,
        doc="FK to parent AccountGroup — NULL for a top-level group",
    )

    display_order: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )


class Account(TenantBaseModel):
    """Individual ledger account — the leaf or parent node in the COA tree.

    Invariants (enforced at service layer — ``AccountInvariantValidator``):
      - ``account_code`` unique per company
      - Only ``is_leaf=True`` accounts accept GL postings
      - ``is_active=False`` accounts reject all new postings
      - A parent account cannot be deactivated while it has active children
      - Cannot be deactivated if it has GL activity in the current fiscal year

    Spec ref: spec.md §13.6 Account Properties
    """

    __tablename__ = "accounting_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "account_code", name="uq_accounting_accounts_company_code"
        ),
        CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name="ck_accounting_accounts_type",
        ),
        {
            "comment": "Chart of Accounts — individual ledger accounts, scoped per company"
        },
    )

    account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)

    account_group_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_account_groups.id", ondelete="RESTRICT"),
        nullable=True,
    )

    parent_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        doc="FK to parent Account — NULL for a top-level account",
    )

    is_leaf: Mapped[bool] = mapped_column(
        Boolean,
        server_default=true(),
        nullable=False,
        doc="Only leaf accounts accept GL postings (spec.md §13.4)",
    )

    currency_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        doc="NULL = base currency; set for foreign-denominated accounts",
    )

    requires_cost_center: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    is_bank_account: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    is_cash_account: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )

    tax_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

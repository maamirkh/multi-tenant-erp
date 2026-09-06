"""Tax Engine ORM models — Phase 11.

Phase 11 entities:
  TaxCode      — a single tax rule (rate resolved from its TaxRate history)
  TaxRate      — effective-dated rate history for one TaxCode
  TaxGroup     — a named bundle of TaxCodes applied together
  TaxGroupLine — membership of one TaxCode within a TaxGroup

Design note — no ``tax_code_id`` on ``JournalLine``: tax reports (T232's
``get_vat_summary_report()``/``get_tax_detail_report()``) correlate tax
postings to their originating ``TaxCode`` via ``TaxCode.gl_account_id`` —
the same account-as-join-key pattern ``GLReportRepository.
account_balance_query()`` already uses for Cash/Bank/AR/AP reconciliation —
rather than adding a new column to the append-only ``accounting_journal_lines``
table. tasks.md T224-T238 does not list altering that table, and each tax
code already owns exactly one dedicated GL account (data-model.md §2.9),
so the account itself is a sufficient, non-invasive correlation key.

Spec ref: specs/008-accounting-finance/spec.md §23 Tax Management
Data model: specs/008-accounting-finance/data-model.md §2.9 TaxManagement
Tasks ref: specs/008-accounting-finance/tasks.md T224-T227
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class TaxCode(TenantBaseModel):
    """A single tax rule — the atomic unit of tax configuration."""

    __tablename__ = "accounting_tax_codes"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "tax_code", name="uq_accounting_tax_codes_company_code"
        ),
        CheckConstraint(
            "tax_type IN ('SALES_TAX','VAT','GST','WITHHOLDING','COMPOUND',"
            "'EXEMPT','ZERO_RATED','OUT_OF_SCOPE')",
            name="ck_accounting_tax_codes_type",
        ),
        CheckConstraint(
            "applicability IN ('SALES','PURCHASES','BOTH')",
            name="ck_accounting_tax_codes_applicability",
        ),
        {"comment": "Tax code definitions, scoped per company"},
    )

    tax_code: Mapped[str] = mapped_column(String(20), nullable=False)
    tax_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(20), nullable=False)
    applicability: Mapped[str] = mapped_column(String(20), nullable=False)
    gl_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_input_tax_recoverable: Mapped[bool] = mapped_column(
        nullable=False, server_default=false()
    )
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())


class TaxRate(TenantBaseModel):
    """Effective-dated rate history for one TaxCode.

    Invariant (data-model.md §2.9, enforced at service layer):
    effective date ranges cannot overlap for the same tax code.
    """

    __tablename__ = "accounting_tax_rates"
    __table_args__ = (
        CheckConstraint("rate >= 0", name="ck_accounting_tax_rates_non_negative"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_accounting_tax_rates_date_order",
        ),
        CheckConstraint(
            "rounding_rule IN ('HALF_UP','HALF_EVEN','DOWN','UP')",
            name="ck_accounting_tax_rates_rounding_rule",
        ),
        {"comment": "Tax rate history per tax code, scoped per company"},
    )

    tax_code_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_tax_codes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="NULL = still in effect (open-ended, current rate)."
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), nullable=False, doc="Percentage, e.g. 15.000000 for 15%."
    )
    rounding_rule: Mapped[str] = mapped_column(
        String(20), server_default="HALF_UP", nullable=False
    )


class TaxGroup(TenantBaseModel):
    """A named bundle of TaxCodes applied together (e.g. Federal + Provincial)."""

    __tablename__ = "accounting_tax_groups"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "group_code", name="uq_accounting_tax_groups_company_code"
        ),
        CheckConstraint(
            "applicability IN ('SALES','PURCHASES','BOTH')",
            name="ck_accounting_tax_groups_applicability",
        ),
        {"comment": "Tax group definitions, scoped per company"},
    )

    group_code: Mapped[str] = mapped_column(String(20), nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    applicability: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())


class TaxGroupLine(TenantBaseModel):
    """Membership of one TaxCode within a TaxGroup, with display order."""

    __tablename__ = "accounting_tax_group_lines"
    __table_args__ = (
        UniqueConstraint(
            "tax_group_id",
            "tax_code_id",
            name="uq_accounting_tax_group_lines_group_code",
        ),
        {"comment": "Tax codes within each tax group, scoped per company"},
    )

    tax_group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_tax_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    tax_code_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_tax_codes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )

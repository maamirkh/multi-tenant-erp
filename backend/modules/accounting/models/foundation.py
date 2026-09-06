"""Accounting foundation ORM models — Phase 1.

Phase 1 entities:
  AccountingConfiguration — company-level accounting settings (one row per company)
  AccountingSequence      — advisory-lock-free gap-free journal number generation
  Currency                — ISO 4217 currency registry (global, not company-scoped)
  ExchangeRate            — exchange rate per currency pair per date

Foreign keys to ``accounting_accounts`` (Chart of Accounts, Phase 2) and
``accounting_currencies`` are intentionally deferred/unenforced at the DB
level in this migration, following the same deferred-FK convention used for
``company_id``/``created_by`` in ``TenantBaseModel`` — the referenced table
either does not exist yet (Account, until Phase 2) or the constraint is
added once the dependency epic/phase ships.

Spec ref: specs/008-accounting-finance/data-model.md §11 Database Tables
Plan ref: specs/008-accounting-finance/plan.md Phase 1
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel
from core.database.models.tenant_base import TenantBaseModel
from modules.accounting.constants import ExchangeRateType


class AccountingConfiguration(TenantBaseModel):
    """Company-level accounting settings — one row per company.

    Holds base currency, approval thresholds, and default system-account
    references used by the PostingEngine and integration event handlers
    when no more specific account mapping is available (see ADR-0004).
    """

    __tablename__ = "accounting_configurations"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_accounting_configuration_company"),
        CheckConstraint(
            "credit_warning_threshold_pct >= 0 AND credit_warning_threshold_pct <= 100",
            name="ck_accounting_config_credit_threshold",
        ),
        CheckConstraint(
            "cheque_stale_days >= 1", name="ck_accounting_config_cheque_stale_days"
        ),
        {"comment": "Company-level accounting configuration — one row per company"},
    )

    base_currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 base currency code for this company's financial reporting",
    )

    journal_approval_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6),
        nullable=True,
        doc="Manual journal amount above which approval is required (BR-008)",
    )

    payment_approval_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6),
        nullable=True,
        doc="Payment amount above which approval is required",
    )

    credit_warning_threshold_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        server_default="80.00",
        nullable=False,
        doc="Customer credit utilisation percentage that triggers a warning event",
    )

    cheque_stale_days: Mapped[int] = mapped_column(
        Integer,
        server_default="180",
        nullable=False,
        doc="Days after which an uncleared cheque is marked STALE",
    )

    # --- Default system control accounts (nullable — set once COA exists, Phase 2) ---
    default_ar_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Default Accounts Receivable control account",
    )
    default_ap_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Default Accounts Payable control account",
    )
    default_retained_earnings_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Retained earnings account for year-end close",
    )
    default_exchange_gain_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, doc="Realised/unrealised FX gain account"
    )
    default_exchange_loss_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, doc="Realised/unrealised FX loss account"
    )
    default_bad_debt_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Bad debt expense account for AR write-offs",
    )
    # --- Added per ADR-0004 (GL account resolution for integration events) ---
    default_revenue_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Default revenue account for Sales invoice postings lacking a per-line mapping",
    )
    default_expense_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Default expense account for Purchase bill postings lacking a per-line mapping",
    )
    default_tax_liability_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Default output tax liability account for Sales invoice postings",
    )
    default_input_tax_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Default recoverable input tax account for Purchase bill postings",
    )


class AccountingSequence(TenantBaseModel):
    """Gap-free sequence counter for accounting document numbering.

    Concurrency safety: locked via ``SELECT ... FOR UPDATE`` on this row by
    ``AccountingSequenceService`` to guarantee no gaps and no duplicates
    under concurrent journal posting (research.md Decision 2).

    Only ``sequence_type='JOURNAL'`` is used in Phase 1; the column exists
    so future document types can share the same table without a migration.
    """

    __tablename__ = "accounting_sequences"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "sequence_type",
            "year",
            name="uq_accounting_seq_company_type_year",
        ),
        CheckConstraint("sequence_type IN ('JOURNAL')", name="ck_accounting_seq_type"),
        CheckConstraint("current_value >= 0", name="ck_accounting_seq_current_value"),
        {
            "comment": "Gap-free auto-numbering sequences for accounting documents, "
            "locked with SELECT FOR UPDATE"
        },
    )

    sequence_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Document type this sequence generates numbers for",
    )
    prefix: Mapped[str] = mapped_column(
        String(10),
        server_default="'JE'",
        nullable=False,
        doc="Number prefix, e.g. 'JE'",
    )
    current_value: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False, doc="Last issued sequence value"
    )
    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Calendar year this counter applies to (yearly reset)",
    )
    format_pattern: Mapped[str] = mapped_column(
        String(50),
        server_default="'{PREFIX}-{YEAR}-{SEQ:06d}'",
        nullable=False,
        doc="Format pattern used to render the final document number string",
    )


class Currency(BaseModel):
    """ISO 4217 currency registry — global, shared across all companies.

    Unlike other accounting tables, ``Currency`` has no ``company_id``: a
    currency (e.g. USD, EUR) is a universal fact, not a tenant-specific
    concept (data-model.md §11 Foundation Tables).
    """

    __tablename__ = "accounting_currencies"
    __table_args__ = (
        UniqueConstraint("iso_code", name="uq_accounting_currencies_iso_code"),
        CheckConstraint(
            "decimal_places >= 0", name="ck_accounting_currencies_decimals"
        ),
        {"comment": "ISO 4217 currency registry — global reference data"},
    )

    iso_code: Mapped[str] = mapped_column(
        String(3), nullable=False, doc="ISO 4217 three-letter currency code, e.g. 'USD'"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    decimal_places: Mapped[int] = mapped_column(
        Integer, server_default="2", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )


class ExchangeRate(TenantBaseModel):
    """Exchange rate for a currency pair on a given date, scoped per company.

    Company-scoped (not global like ``Currency``) so that companies with
    different banking relationships or negotiated rates can maintain their
    own rate history — see quickstart.md "Phase 0 Verification Findings"
    for the rationale (Non-Negotiable Rule #10: every business table
    requires ``company_id``; only ``Currency`` is an explicit exception).

    Resolution order at posting time (research.md Decision 8):
      1. Explicit rate on the posting request
      2. Exact-date match in this table
      3. Most recent rate within a 7-day lookback window
      4. ``ExchangeRateNotFoundError`` if none found
    """

    __tablename__ = "accounting_exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "from_currency_code",
            "to_currency_code",
            "rate_date",
            "rate_type",
            name="uq_accounting_fx_rate_company_pair_date_type",
        ),
        CheckConstraint("rate > 0", name="ck_accounting_fx_rate_positive"),
        {"comment": "Exchange rate per currency pair per date, scoped per company"},
    )

    from_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    rate_type: Mapped[ExchangeRateType] = mapped_column(
        String(20), server_default=ExchangeRateType.SPOT.value, nullable=False
    )

"""General Ledger ORM models — Phase 4 (CRITICAL).

Phase 4 entities:
  JournalEntry        — the aggregate root (mutable while DRAFT/SUBMITTED/
                         APPROVED; effectively frozen once POSTED — no field
                         is ever written again after Step 7 of PostingEngine
                         except by ``reverse()``, which only flips ``status``)
  JournalLine         — append-only GL line (data-model.md §1, research.md
                         Decision 1). Does NOT inherit ``TenantBaseModel`` or
                         even ``BaseModel`` — no ``is_deleted``/``deleted_at``
                         and no ``updated_at`` column exists at all, so there
                         is structurally nothing to "soft delete" or "touch
                         on update". A DB trigger (migration 038) additionally
                         blocks any UPDATE/DELETE at the SQL level — belt and
                         suspenders per research.md Decision 4. There is no
                         "edit a draft's lines" capability in this phase —
                         T101's endpoint list has no such route; lines are
                         fixed at journal-creation time.
  JournalApproval      — one row per approve/reject decision (audit trail)
  AccountingAuditLog   — append-only immutable audit record for every
                         journal state change (same no-``updated_at`` pattern
                         as ``JournalLine``, mirroring
                         ``modules.companies.models.company_audit_log
                         .CompanyAuditLog``)

Spec ref: specs/008-accounting-finance/spec.md §14 General Ledger, §15 Journal Entries
Data model: specs/008-accounting-finance/data-model.md §2.3 JournalEntry
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.database.models.tenant_base import TenantBaseModel


class JournalEntry(TenantBaseModel):
    """The GL journal entry aggregate root.

    ``journal_number`` is NULL until the entry is actually POSTED (Step 6 of
    ``PostingEngine.post()``/``post_direct()``) — gap-free numbering counts
    only real ledger postings, never abandoned drafts (data-model.md §2.3,
    tasks.md T093 Step 6).

    ``fiscal_period_id``/``fiscal_year_id`` are resolved and stored only at
    posting time (Step 3/7) — a DRAFT is not yet bound to a period, since
    the period covering its ``posting_date`` might change (lock/unlock)
    before it is actually posted.

    ``is_balanced`` is nullable: NULL for any not-yet-posted entry (not yet
    validated at the DB level); the app layer (PostingEngine Step 1) never
    permits writing ``False`` — the CHECK constraint below is a structural
    backstop against a hypothetical direct-DB write (research.md Decision 4).
    """

    __tablename__ = "accounting_journal_entries"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "journal_number", name="uq_accounting_journals_company_number"
        ),
        Index(
            "ix_accounting_journal_entries_company_posting_date",
            "company_id",
            "posting_date",
        ),
        CheckConstraint(
            "journal_type IN ('STANDARD','ADJUSTING','REVERSING',"
            "'RECURRING_INSTANCE','OPENING_BALANCE','CLOSING','AUTOMATED')",
            name="ck_accounting_journals_type",
        ),
        CheckConstraint(
            "posting_source IN ('MANUAL','SALES','PURCHASE','INVENTORY','BANK',"
            "'CASH','PAYMENT','RECURRING','SYSTEM')",
            name="ck_accounting_journals_source",
        ),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','POSTED','REJECTED','REVERSED')",
            name="ck_accounting_journals_status",
        ),
        CheckConstraint(
            "is_balanced IS NULL OR is_balanced = true",
            name="ck_accounting_journals_is_balanced",
        ),
        {
            "comment": "General Ledger journal entries (aggregate root), scoped per company"
        },
    )

    journal_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    journal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    posting_source: Mapped[str] = mapped_column(String(20), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)

    fiscal_period_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_fiscal_periods.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fiscal_year_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_fiscal_years.id", ondelete="RESTRICT"),
        nullable=True,
    )

    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), server_default="DRAFT", nullable=False
    )

    reversal_of_journal_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Set on the REVERSAL entry, pointing back to the original POSTED entry.",
    )
    is_reversal: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    posted_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    source_document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(20, 10), server_default="1", nullable=False
    )
    total_debit_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    total_credit_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    is_balanced: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class JournalLine(Base):
    """An append-only GL line. NO soft-delete, NO update, ever — see module docstring.

    Does not inherit ``TenantBaseModel``/``BaseModel``: no ``is_deleted``,
    ``deleted_at``, ``created_by``, or ``updated_at`` column exists at all.
    """

    __tablename__ = "accounting_journal_lines"
    __table_args__ = (
        UniqueConstraint(
            "journal_entry_id",
            "line_number",
            name="uq_accounting_journal_lines_entry_number",
        ),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_accounting_journal_lines_one_sided",
        ),
        CheckConstraint(
            "debit_amount >= 0 AND credit_amount >= 0",
            name="ck_accounting_journal_lines_non_negative",
        ),
        {"comment": "Append-only General Ledger lines — no UPDATE/DELETE, ever"},
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )

    journal_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_code: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="Denormalized for query performance."
    )

    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    debit_amount_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    credit_amount_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(20, 10), server_default="1", nullable=False
    )

    cost_center_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    project_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JournalApproval(TenantBaseModel):
    """One row per approve/reject decision on a ``JournalEntry``."""

    __tablename__ = "accounting_journal_approvals"
    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('APPROVED', 'REJECTED')",
            name="ck_accounting_journal_approvals_status",
        ),
        {
            "comment": "Approval/rejection decisions on journal entries, scoped per company"
        },
    )

    journal_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approver_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccountingAuditLog(Base):
    """Immutable audit record for every accounting financial state change.

    Mirrors ``modules.companies.models.company_audit_log.CompanyAuditLog``:
    does not inherit ``BaseModel`` (no ``updated_at``), append-only by
    convention (repository exposes ``create`` only — see repositories/gl.py).
    """

    __tablename__ = "accounting_audit_log"
    __table_args__ = (
        {"comment": "Immutable audit trail for accounting financial state changes"},
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    session_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

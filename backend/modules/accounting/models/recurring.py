"""Recurring Journal Entry ORM models — Phase 5.

Phase 5 entities:
  RecurringJournalTemplate      — schedule + defaults for a recurring entry
  RecurringJournalTemplateLine  — the template's DR/CR lines
  RecurringJournalInstance      — one row per execution (audit/history)

Research ref: research.md Decision 13 — template + instance pattern. Each
execution creates a standard ``JournalEntry`` via ``PostingEngine``; all
normal posting rules apply. The instance table exists purely for audit and
history — it does not itself hold ledger data.

Spec ref: specs/008-accounting-finance/spec.md §15.4 Recurring Journal Entries
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class RecurringJournalTemplate(TenantBaseModel):
    """Schedule and defaults for a recurring journal entry.

    ``next_run_date`` starts equal to ``start_date`` and advances by
    ``frequency`` after each execution (``RecurringJournalService``).
    ``auto_post=True`` posts each instance immediately via
    ``PostingEngine.post_direct()``; otherwise the instance is created as
    DRAFT (or SUBMITTED, if ``approval_required=True``) for manual review.
    """

    __tablename__ = "accounting_recurring_templates"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUALLY')",
            name="ck_accounting_recurring_templates_frequency",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date > start_date",
            name="ck_accounting_recurring_templates_date_range",
        ),
        {"comment": "Recurring journal templates, scoped per company"},
    )

    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="NULL = indefinite (spec.md §15.4)"
    )
    next_run_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
    auto_post: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecurringJournalTemplateLine(TenantBaseModel):
    """A single DR/CR line within a recurring journal template."""

    __tablename__ = "accounting_recurring_template_lines"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "line_number",
            name="uq_accounting_recurring_lines_template_number",
        ),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_accounting_recurring_lines_one_sided",
        ),
        {"comment": "Template lines for recurring journal entries, scoped per company"},
    )

    template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_recurring_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_center_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class RecurringJournalInstance(TenantBaseModel):
    """One row per recurring-template execution — audit/history only.

    Unique on ``(template_id, execution_date)`` — the DB-level backstop for
    the idempotency check in ``RecurringJournalService.execute_due_templates()``
    (tasks.md T119): a second execution attempt for the same scheduled date
    is rejected even if the app-layer pre-check were ever bypassed.
    """

    __tablename__ = "accounting_recurring_instances"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "execution_date",
            name="uq_accounting_recurring_instances_template_date",
        ),
        CheckConstraint(
            "status IN ('SUCCESS', 'FAILED')",
            name="ck_accounting_recurring_instances_status",
        ),
        {
            "comment": "Execution history for recurring journal templates, scoped per company"
        },
    )

    template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_recurring_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        doc="NULL when status=FAILED and no JournalEntry could be created.",
    )
    execution_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

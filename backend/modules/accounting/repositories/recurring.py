"""Repositories for Recurring Journal Entry entities — Phase 5.

  RecurringJournalTemplateRepository      — template CRUD + due-template lookup
  RecurringJournalTemplateLineRepository  — template line CRUD
  RecurringJournalInstanceRepository      — execution history + idempotency lookup

Spec ref: specs/008-accounting-finance/tasks.md T115-T117
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.recurring import (
    RecurringJournalInstance,
    RecurringJournalTemplate,
    RecurringJournalTemplateLine,
)
from modules.accounting.repositories import BaseAccountingRepository


class RecurringJournalTemplateRepository(
    BaseAccountingRepository[RecurringJournalTemplate]
):
    """Data-access layer for the ``accounting_recurring_templates`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=RecurringJournalTemplate)

    def list_all(self, company_id: UUID) -> list[RecurringJournalTemplate]:
        stmt = (
            select(RecurringJournalTemplate)
            .where(RecurringJournalTemplate.company_id == company_id)
            .where(RecurringJournalTemplate.is_deleted == False)  # noqa: E712
            .order_by(RecurringJournalTemplate.template_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_due(self, as_of_date: date) -> list[RecurringJournalTemplate]:
        """Return all active templates across all companies due on or before ``as_of_date``.

        Called by the APScheduler job, which has no single company_id
        context — it must scan across tenants (mirrors the pattern any
        cross-tenant background job needs; still filters by company_id on
        every downstream write via PostingEngine/repositories).
        """
        stmt = (
            select(RecurringJournalTemplate)
            .where(RecurringJournalTemplate.is_deleted == False)  # noqa: E712
            .where(RecurringJournalTemplate.is_active == True)  # noqa: E712
            .where(RecurringJournalTemplate.next_run_date <= as_of_date)
            .order_by(RecurringJournalTemplate.next_run_date)
        )
        return list(self.db.execute(stmt).scalars().all())


class RecurringJournalTemplateLineRepository(
    BaseAccountingRepository[RecurringJournalTemplateLine]
):
    """Data-access layer for the ``accounting_recurring_template_lines`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=RecurringJournalTemplateLine)

    def find_by_template(
        self, company_id: UUID, template_id: UUID
    ) -> list[RecurringJournalTemplateLine]:
        stmt = (
            select(RecurringJournalTemplateLine)
            .where(RecurringJournalTemplateLine.company_id == company_id)
            .where(RecurringJournalTemplateLine.template_id == template_id)
            .where(RecurringJournalTemplateLine.is_deleted == False)  # noqa: E712
            .order_by(RecurringJournalTemplateLine.line_number)
        )
        return list(self.db.execute(stmt).scalars().all())


class RecurringJournalInstanceRepository(
    BaseAccountingRepository[RecurringJournalInstance]
):
    """Data-access layer for the ``accounting_recurring_instances`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=RecurringJournalInstance)

    def find_by_template_and_date(
        self, template_id: UUID, execution_date: date
    ) -> RecurringJournalInstance | None:
        """The idempotency check (tasks.md T119): has this template already
        executed for this scheduled date?
        """
        stmt = (
            select(RecurringJournalInstance)
            .where(RecurringJournalInstance.template_id == template_id)
            .where(RecurringJournalInstance.execution_date == execution_date)
            .where(RecurringJournalInstance.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_template(
        self, company_id: UUID, template_id: UUID
    ) -> list[RecurringJournalInstance]:
        stmt = (
            select(RecurringJournalInstance)
            .where(RecurringJournalInstance.company_id == company_id)
            .where(RecurringJournalInstance.template_id == template_id)
            .where(RecurringJournalInstance.is_deleted == False)  # noqa: E712
            .order_by(RecurringJournalInstance.execution_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

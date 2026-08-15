"""RecurringJournalService — recurring journal templates — Phase 5.

Research ref: research.md Decision 13 — template + instance pattern. Each
execution creates a standard ``JournalEntry`` via ``PostingEngine`` (all
normal posting rules apply) and records a ``RecurringJournalInstance`` for
audit/history. ``execute_due_templates()`` is called by the APScheduler job
(``services/scheduler.py``).

Idempotency (tasks.md T119): before creating an instance, check whether one
already exists for this template + scheduled date; if so, skip journal
creation and just complete the (possibly interrupted) advance of
``next_run_date``. This handles the documented APScheduler-restart
double-execution risk (plan.md Phase 4 Risks) — a DB-level unique
constraint on ``(template_id, execution_date)`` backstops this at the
storage layer too.

Spec ref: specs/008-accounting-finance/tasks.md T118, T119
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import (
    JournalType,
    PostingSource,
    RecurringFrequency,
    RecurringInstanceStatus,
)
from modules.accounting.exceptions import (
    AccountNotFoundError,
    PostingValidationError,
    RecurringTemplateNotFoundError,
)
from modules.accounting.models.recurring import (
    RecurringJournalInstance,
    RecurringJournalTemplate,
    RecurringJournalTemplateLine,
)
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.recurring import (
    RecurringJournalInstanceRepository,
    RecurringJournalTemplateLineRepository,
    RecurringJournalTemplateRepository,
)
from modules.accounting.services.posting_engine import PostingEngine

logger = logging.getLogger(__name__)


class RecurringJournalService:
    """Application service for recurring journal template management and execution."""

    def __init__(
        self,
        db: Session,
        template_repo: RecurringJournalTemplateRepository,
        line_repo: RecurringJournalTemplateLineRepository,
        instance_repo: RecurringJournalInstanceRepository,
        account_repo: AccountRepository,
        posting_engine: PostingEngine,
    ) -> None:
        self.db = db
        self._templates = template_repo
        self._lines = line_repo
        self._instances = instance_repo
        self._accounts = account_repo
        self._engine = posting_engine

    # ------------------------------------------------------------------
    # Template CRUD
    # ------------------------------------------------------------------

    def create_template(
        self,
        company_id: UUID,
        template_name: str,
        frequency: str,
        start_date: date,
        lines: list[dict[str, Any]],
        end_date: date | None = None,
        auto_post: bool = False,
        approval_required: bool = False,
        currency_code: str | None = None,
        reference: str | None = None,
        description: str | None = None,
        created_by: UUID | None = None,
    ) -> RecurringJournalTemplate:
        """Create a recurring journal template with its lines.

        Raises:
            PostingValidationError: Fewer than 2 lines, unbalanced lines,
                or an invalid debit/credit combination on a line.
            AccountNotFoundError: A referenced account does not exist.
            ValueError: Invalid ``frequency``.
        """
        RecurringFrequency(
            frequency
        )  # validates the value; raises ValueError if unknown
        if len(lines) < 2:
            raise PostingValidationError(
                "A recurring journal template must have at least two lines."
            )
        self._validate_lines(company_id, lines)

        template = RecurringJournalTemplate(
            company_id=company_id,
            template_name=template_name,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            next_run_date=start_date,
            is_active=True,
            auto_post=auto_post,
            approval_required=approval_required,
            currency_code=currency_code or "USD",
            reference=reference,
            description=description,
            created_by=created_by,
        )
        template = self._templates.create(template)

        for idx, line in enumerate(lines, start=1):
            self._lines.create(
                RecurringJournalTemplateLine(
                    company_id=company_id,
                    template_id=template.id,
                    line_number=idx,
                    account_id=line["account_id"],
                    debit_amount=line.get("debit_amount", 0),
                    credit_amount=line.get("credit_amount", 0),
                    description=line.get("description"),
                    cost_center_id=line.get("cost_center_id"),
                    created_by=created_by,
                )
            )
        return template

    def _validate_lines(self, company_id: UUID, lines: list[dict[str, Any]]) -> None:
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for line in lines:
            debit = Decimal(str(line.get("debit_amount", 0)))
            credit = Decimal(str(line.get("credit_amount", 0)))
            if debit < 0 or credit < 0:
                raise PostingValidationError("Line amounts must not be negative.")
            if debit > 0 and credit > 0:
                raise PostingValidationError(
                    "A line cannot have both a debit and a credit amount."
                )
            if debit == 0 and credit == 0:
                raise PostingValidationError(
                    "A line must have a non-zero debit or credit amount."
                )
            if (
                self._accounts.get_by_id_or_none(
                    id=line["account_id"], company_id=company_id
                )
                is None
            ):
                raise AccountNotFoundError(account_id=str(line["account_id"]))
            total_debit += debit
            total_credit += credit
        if total_debit != total_credit:
            raise PostingValidationError("Recurring journal template must balance")

    def get_template(
        self, company_id: UUID, template_id: UUID
    ) -> RecurringJournalTemplate:
        template = self._templates.get_by_id_or_none(
            id=template_id, company_id=company_id
        )
        if template is None:
            raise RecurringTemplateNotFoundError(template_id=str(template_id))
        return template

    def list_templates(self, company_id: UUID) -> list[RecurringJournalTemplate]:
        return self._templates.list_all(company_id=company_id)

    def update_template(
        self, company_id: UUID, template_id: UUID, **updates: object
    ) -> RecurringJournalTemplate:
        """Update mutable fields on a template. Schedule/lines are immutable
        once created — cancel (deactivate) and create a new template instead.
        """
        template = self.get_template(company_id, template_id)
        mutable_fields = {
            "template_name",
            "end_date",
            "auto_post",
            "approval_required",
            "reference",
            "description",
        }
        for key, value in updates.items():
            if key in mutable_fields and value is not None:
                setattr(template, key, value)
        return self._templates.update(template)

    def activate_template(
        self, company_id: UUID, template_id: UUID
    ) -> RecurringJournalTemplate:
        template = self.get_template(company_id, template_id)
        template.is_active = True
        return self._templates.update(template)

    def deactivate_template(
        self, company_id: UUID, template_id: UUID
    ) -> RecurringJournalTemplate:
        template = self.get_template(company_id, template_id)
        template.is_active = False
        return self._templates.update(template)

    def get_template_history(
        self, company_id: UUID, template_id: UUID
    ) -> list[RecurringJournalInstance]:
        self.get_template(company_id, template_id)  # existence check
        return self._instances.find_by_template(company_id, template_id)

    def list_template_lines(
        self, company_id: UUID, template_id: UUID
    ) -> list[RecurringJournalTemplateLine]:
        return self._lines.find_by_template(company_id, template_id)

    # ------------------------------------------------------------------
    # Execution (called by APScheduler — services/scheduler.py)
    # ------------------------------------------------------------------

    def execute_due_templates(
        self, as_of_date: date | None = None
    ) -> list[RecurringJournalInstance]:
        """Execute every active, due template across all companies.

        Args:
            as_of_date: Defaults to today (UTC). Explicit for testability
                ("advance mock clock by 1 month" — Phase 5 Independent Test).

        Returns:
            One ``RecurringJournalInstance`` per due template processed
            this call (SUCCESS or FAILED — a failure in one template does
            not stop the others).
        """
        effective_date = as_of_date or utcnow().date()
        due_templates = self._templates.find_due(effective_date)
        return [self._execute_one(template) for template in due_templates]

    def _execute_one(
        self, template: RecurringJournalTemplate
    ) -> RecurringJournalInstance:
        scheduled_date = template.next_run_date

        existing = self._instances.find_by_template_and_date(
            template.id, scheduled_date
        )
        if existing is not None:
            logger.info(
                "RecurringJournalService: instance already exists for template=%s date=%s, skipping (idempotency)",
                template.id,
                scheduled_date,
            )
            self._advance_next_run_date(template)
            return existing

        lines = self._lines.find_by_template(template.company_id, template.id)
        posting_lines = [
            {
                "account_id": line.account_id,
                "debit_amount": line.debit_amount,
                "credit_amount": line.credit_amount,
                "description": line.description,
                "cost_center_id": line.cost_center_id,
            }
            for line in lines
        ]
        description = template.description or f"Recurring: {template.template_name}"

        journal_entry_id: UUID | None = None
        status = RecurringInstanceStatus.SUCCESS.value
        error_message: str | None = None
        try:
            if template.auto_post:
                result = self._engine.post_direct(
                    company_id=template.company_id,
                    journal_type=JournalType.RECURRING_INSTANCE.value,
                    posting_source=PostingSource.RECURRING.value,
                    posting_date=scheduled_date,
                    lines=posting_lines,
                    currency_code=template.currency_code,
                    reference=template.reference,
                    description=description,
                    source_document_type="RecurringJournalTemplate",
                    source_document_id=template.id,
                )
                journal_entry_id = result.journal_entry_id
            else:
                entry = self._engine.create_journal(
                    company_id=template.company_id,
                    journal_type=JournalType.RECURRING_INSTANCE.value,
                    posting_source=PostingSource.RECURRING.value,
                    posting_date=scheduled_date,
                    lines=posting_lines,
                    currency_code=template.currency_code,
                    reference=template.reference,
                    description=description,
                    source_document_type="RecurringJournalTemplate",
                    source_document_id=template.id,
                )
                if template.approval_required:
                    self._engine.submit(template.company_id, entry.id, None)
                journal_entry_id = entry.id
        except (
            Exception
        ) as exc:  # noqa: BLE001 — one template's failure must not stop the batch
            status = RecurringInstanceStatus.FAILED.value
            error_message = str(exc)
            logger.exception(
                "RecurringJournalService: execution failed for template=%s date=%s",
                template.id,
                scheduled_date,
            )

        instance = self._instances.create(
            RecurringJournalInstance(
                company_id=template.company_id,
                template_id=template.id,
                journal_entry_id=journal_entry_id,
                execution_date=scheduled_date,
                status=status,
                error_message=error_message,
            )
        )
        self._advance_next_run_date(template)
        return instance

    def _advance_next_run_date(self, template: RecurringJournalTemplate) -> None:
        next_date = self._compute_next_date(template.next_run_date, template.frequency)
        template.next_run_date = next_date
        if template.end_date is not None and next_date > template.end_date:
            template.is_active = False
        self._templates.update(template)

    @staticmethod
    def _compute_next_date(current: date, frequency: str) -> date:
        freq = RecurringFrequency(frequency)
        if freq == RecurringFrequency.DAILY:
            return current + timedelta(days=1)
        if freq == RecurringFrequency.WEEKLY:
            return current + timedelta(days=7)
        if freq == RecurringFrequency.MONTHLY:
            return _add_months(current, 1)
        if freq == RecurringFrequency.QUARTERLY:
            return _add_months(current, 3)
        return _add_months(current, 12)  # ANNUALLY


def _add_months(d: date, months: int) -> date:
    """Add ``months`` to ``d``, clamping the day to the target month's length."""
    total_month = d.month - 1 + months
    year = d.year + total_month // 12
    month = total_month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

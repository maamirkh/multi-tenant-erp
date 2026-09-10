"""Unit tests for RecurringJournalService — Phase 5.

Tests (tasks.md T128):
  - Due template executes (creates + posts a journal, records SUCCESS instance)
  - Future (not-yet-due) template is skipped
  - Idempotency: a second execution for the same scheduled date skips
    (simulates the APScheduler-restart double-execution risk)
  - next_run_date advances correctly per frequency (DAILY/WEEKLY/MONTHLY/
    QUARTERLY/ANNUALLY), including month-end day clamping
  - A template past its end_date is auto-deactivated
  - auto_post=False creates a DRAFT (or SUBMITTED, if approval_required)
    instead of posting immediately

Spec ref: specs/008-accounting-finance/tasks.md T128
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.constants import RecurringInstanceStatus
from modules.accounting.models.coa import Account
from modules.accounting.models.recurring import RecurringJournalInstance
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.feature_flag_repository import (
    AccountingFeatureFlagRepository,
)
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    JournalApprovalRepository,
    JournalEntryRepository,
    JournalLineRepository,
)
from modules.accounting.repositories.recurring import (
    RecurringJournalInstanceRepository,
    RecurringJournalTemplateLineRepository,
    RecurringJournalTemplateRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.recurring_journal_service import (
    RecurringJournalService,
    _add_months,
)
from modules.accounting.services.sequence_service import AccountingSequenceService


@pytest.fixture
def account_repo(db_session: Session) -> AccountRepository:
    return AccountRepository(db_session)


@pytest.fixture
def posting_engine(
    db_session: Session, account_repo: AccountRepository
) -> PostingEngine:
    return PostingEngine(
        db=db_session,
        journal_repo=JournalEntryRepository(db_session),
        line_repo=JournalLineRepository(db_session),
        approval_repo=JournalApprovalRepository(db_session),
        account_repo=account_repo,
        fiscal_period_repo=FiscalPeriodRepository(db_session),
        sequence_service=AccountingSequenceService(db_session),
        config_repo=AccountingConfigurationRepository(db_session),
        flag_service=AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        ),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )


@pytest.fixture
def recurring_service(
    db_session: Session, account_repo: AccountRepository, posting_engine: PostingEngine
) -> RecurringJournalService:
    return RecurringJournalService(
        db=db_session,
        template_repo=RecurringJournalTemplateRepository(db_session),
        line_repo=RecurringJournalTemplateLineRepository(db_session),
        instance_repo=RecurringJournalInstanceRepository(db_session),
        account_repo=account_repo,
        posting_engine=posting_engine,
    )


@pytest.fixture
def gl_setup(account_repo: AccountRepository, db_session: Session) -> dict[str, Any]:
    company_id = uuid4()
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    rent = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6100",
            account_name="Rent Expense",
            account_type="EXPENSE",
        )
    )
    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        "FY-Recurring",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"company_id": company_id, "rent": rent, "cash": cash, "today": today}


def _lines(rent_id, cash_id, amount=Decimal("1500")):
    return [
        {"account_id": rent_id, "debit_amount": amount},
        {"account_id": cash_id, "credit_amount": amount},
    ]


def _result_for(
    results: list[RecurringJournalInstance], template_id: Any
) -> RecurringJournalInstance:
    """Isolate this test's own instance from ``results``.

    ``execute_due_templates()`` runs across ALL companies by design (see
    its docstring) — it is a global scheduler batch, not a tenant-scoped
    query. Other tests sharing the same real database may also have a
    template due on the same real calendar day (``date.today()``), so
    asserting a fragile global count/index (``len(results) == 1``,
    ``results[0]``) breaks depending on what else has run. Match by
    ``template_id`` instead.
    """
    matches = [r for r in results if r.template_id == template_id]
    assert len(matches) == 1, (
        f"expected exactly one instance for template {template_id}, "
        f"found {len(matches)} among {len(results)} globally-due results"
    )
    return matches[0]


def _not_among(results: list[RecurringJournalInstance], template_id: Any) -> None:
    """Assert this test's own template was NOT executed, without asserting
    the (fragile, global) ``results`` list is empty overall."""
    assert template_id not in {r.template_id for r in results}


class TestDueTemplateExecutes:
    def test_due_template_creates_and_posts_journal(
        self, recurring_service: RecurringJournalService, gl_setup: dict[str, Any]
    ) -> None:
        template = recurring_service.create_template(
            company_id=gl_setup["company_id"],
            template_name="Monthly Rent",
            frequency="MONTHLY",
            start_date=gl_setup["today"],
            lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            auto_post=True,
        )
        results = recurring_service.execute_due_templates(as_of_date=gl_setup["today"])
        own = _result_for(results, template.id)
        assert own.status == RecurringInstanceStatus.SUCCESS.value
        assert own.journal_entry_id is not None

        refreshed = recurring_service.get_template(gl_setup["company_id"], template.id)
        assert refreshed.next_run_date == _add_months(gl_setup["today"], 1)


class TestFutureTemplateSkipped:
    def test_not_yet_due_template_is_not_executed(
        self, recurring_service: RecurringJournalService, gl_setup: dict[str, Any]
    ) -> None:
        from datetime import timedelta

        future_start = gl_setup["today"] + timedelta(days=10)
        template = recurring_service.create_template(
            company_id=gl_setup["company_id"],
            template_name="Future Template",
            frequency="MONTHLY",
            start_date=future_start,
            lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            auto_post=True,
        )
        results = recurring_service.execute_due_templates(as_of_date=gl_setup["today"])
        _not_among(results, template.id)


class TestIdempotency:
    def test_second_execution_for_same_scheduled_date_skips(
        self, recurring_service: RecurringJournalService, gl_setup: dict[str, Any]
    ) -> None:
        template = recurring_service.create_template(
            company_id=gl_setup["company_id"],
            template_name="Monthly Insurance",
            frequency="MONTHLY",
            start_date=gl_setup["today"],
            lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            auto_post=True,
        )
        first_results = recurring_service.execute_due_templates(
            as_of_date=gl_setup["today"]
        )
        first_own = _result_for(first_results, template.id)

        # Simulate a scheduler restart before next_run_date was durably
        # advanced: reset it back to the same scheduled date and re-run.
        refreshed = recurring_service.get_template(gl_setup["company_id"], template.id)
        refreshed.next_run_date = gl_setup["today"]
        recurring_service.db.commit()

        second_results = recurring_service.execute_due_templates(
            as_of_date=gl_setup["today"]
        )
        second_own = _result_for(second_results, template.id)
        assert second_own.id == first_own.id  # same instance, not a duplicate

        history = recurring_service.get_template_history(
            gl_setup["company_id"], template.id
        )
        assert len(history) == 1  # not 2


class TestNextRunDateAdvancement:
    @pytest.mark.parametrize(
        "frequency,start,expected",
        [
            ("DAILY", date(2026, 3, 15), date(2026, 3, 16)),
            ("WEEKLY", date(2026, 3, 15), date(2026, 3, 22)),
            ("MONTHLY", date(2026, 1, 31), date(2026, 2, 28)),  # month-end clamp
            ("QUARTERLY", date(2026, 1, 31), date(2026, 4, 30)),
            ("ANNUALLY", date(2026, 3, 15), date(2027, 3, 15)),
        ],
    )
    def test_compute_next_date(
        self, frequency: str, start: date, expected: date
    ) -> None:
        assert RecurringJournalService._compute_next_date(start, frequency) == expected


class TestEndDateDeactivation:
    def test_template_deactivated_once_past_end_date(
        self, recurring_service: RecurringJournalService, gl_setup: dict[str, Any]
    ) -> None:
        from datetime import timedelta

        start = gl_setup["today"]
        end = start + timedelta(days=1)  # minimum valid: end_date > start_date
        template = recurring_service.create_template(
            company_id=gl_setup["company_id"],
            template_name="Short-Lived Template",
            frequency="DAILY",
            start_date=start,
            end_date=end,
            lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            auto_post=True,
        )
        # First execution: next_run_date start -> start+1 (== end_date, not yet past it).
        recurring_service.execute_due_templates(as_of_date=start)
        refreshed = recurring_service.get_template(gl_setup["company_id"], template.id)
        assert refreshed.is_active is True
        assert refreshed.next_run_date == end

        # Second execution: next_run_date end -> end+1 (now PAST end_date) -> deactivated.
        recurring_service.execute_due_templates(as_of_date=end)
        refreshed = recurring_service.get_template(gl_setup["company_id"], template.id)
        assert refreshed.is_active is False

        # A subsequent call, even if next_run_date would technically be
        # due, must not execute a deactivated template.
        results = recurring_service.execute_due_templates(
            as_of_date=gl_setup["today"] + timedelta(days=5)
        )
        _not_among(results, template.id)


class TestAutoPostFalse:
    def test_creates_draft_without_posting_when_auto_post_false(
        self,
        recurring_service: RecurringJournalService,
        gl_setup: dict[str, Any],
        posting_engine: PostingEngine,
    ) -> None:
        template = recurring_service.create_template(
            company_id=gl_setup["company_id"],
            template_name="Manual Review Template",
            frequency="MONTHLY",
            start_date=gl_setup["today"],
            lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            auto_post=False,
            approval_required=False,
        )
        results = recurring_service.execute_due_templates(as_of_date=gl_setup["today"])
        own = _result_for(results, template.id)
        assert own.journal_entry_id is not None
        entry = posting_engine.get_journal(gl_setup["company_id"], own.journal_entry_id)
        assert entry.status == "DRAFT"

    def test_creates_submitted_when_approval_required(
        self,
        recurring_service: RecurringJournalService,
        gl_setup: dict[str, Any],
        posting_engine: PostingEngine,
    ) -> None:
        template = recurring_service.create_template(
            company_id=gl_setup["company_id"],
            template_name="Approval Required Template",
            frequency="MONTHLY",
            start_date=gl_setup["today"],
            lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            auto_post=False,
            approval_required=True,
        )
        results = recurring_service.execute_due_templates(as_of_date=gl_setup["today"])
        own = _result_for(results, template.id)
        assert own.journal_entry_id is not None
        entry = posting_engine.get_journal(gl_setup["company_id"], own.journal_entry_id)
        assert entry.status == "SUBMITTED"


class TestTemplateValidation:
    def test_unbalanced_template_rejected(
        self, recurring_service: RecurringJournalService, gl_setup: dict[str, Any]
    ) -> None:
        from modules.accounting.exceptions import PostingValidationError

        with pytest.raises(PostingValidationError, match="balance"):
            recurring_service.create_template(
                company_id=gl_setup["company_id"],
                template_name="Bad Template",
                frequency="MONTHLY",
                start_date=gl_setup["today"],
                lines=[
                    {"account_id": gl_setup["rent"].id, "debit_amount": Decimal("100")},
                    {"account_id": gl_setup["cash"].id, "credit_amount": Decimal("50")},
                ],
            )

    def test_invalid_frequency_rejected(
        self, recurring_service: RecurringJournalService, gl_setup: dict[str, Any]
    ) -> None:
        with pytest.raises(ValueError):
            recurring_service.create_template(
                company_id=gl_setup["company_id"],
                template_name="Bad Frequency",
                frequency="FORTNIGHTLY",
                start_date=gl_setup["today"],
                lines=_lines(gl_setup["rent"].id, gl_setup["cash"].id),
            )

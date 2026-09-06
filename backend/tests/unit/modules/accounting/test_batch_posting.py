"""Unit tests for atomic batch posting — Phase 5 (T122).

Not explicitly named as its own task in T128-T131, but T122 ("Implement
batch journal posting... approve and post all atomically: all succeed or
none post") is a real, new capability introduced this phase and requires
its own coverage per the phase's general testing mandate.

Spec ref: specs/008-accounting-finance/tasks.md T122
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.exceptions import (
    InvalidJournalStateTransitionError,
    PostingValidationError,
)
from modules.accounting.models.coa import Account
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
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.journal_service import JournalEntryService
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.sequence_service import AccountingSequenceService


@pytest.fixture
def posting_engine(db_session: Session) -> PostingEngine:
    return PostingEngine(
        db=db_session,
        journal_repo=JournalEntryRepository(db_session),
        line_repo=JournalLineRepository(db_session),
        approval_repo=JournalApprovalRepository(db_session),
        account_repo=AccountRepository(db_session),
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
def journal_service(posting_engine: PostingEngine) -> JournalEntryService:
    return JournalEntryService(posting_engine)


@pytest.fixture
def gl_setup(db_session: Session) -> dict:
    account_repo = AccountRepository(db_session)
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    company_id = uuid4()
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id, "FY-Batch", date(today.year, 1, 1), date(today.year, 12, 31), "USD"
    )
    return {"company_id": company_id, "ar": ar, "revenue": revenue, "today": today}


def _draft(posting_engine, gl_setup, amount=Decimal("100")):
    return posting_engine.create_journal(
        company_id=gl_setup["company_id"],
        journal_type="STANDARD",
        posting_source="MANUAL",
        posting_date=gl_setup["today"],
        lines=[
            {
                "account_id": gl_setup["ar"].id,
                "debit_amount": amount,
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": gl_setup["revenue"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": amount,
            },
        ],
        currency_code="USD",
    )


class TestBatchPostAllSucceed:
    def test_all_entries_posted(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        drafts = [_draft(posting_engine, gl_setup) for _ in range(3)]
        results = journal_service.batch_post(
            gl_setup["company_id"], [d.id for d in drafts], uuid4()
        )
        assert len(results) == 3
        numbers = [r.journal_number for r in results]
        assert len(set(numbers)) == 3  # gap-free, all distinct
        for draft in drafts:
            entry = posting_engine.get_journal(gl_setup["company_id"], draft.id)
            assert entry.status == "POSTED"


class TestBatchPostAllOrNothing:
    def test_one_invalid_entry_rolls_back_the_whole_batch(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        good_draft_1 = _draft(posting_engine, gl_setup)
        good_draft_2 = _draft(posting_engine, gl_setup)
        # Post one of them individually first — re-posting it in the batch
        # must fail the state-machine check (already POSTED).
        posting_engine.post(gl_setup["company_id"], good_draft_2.id, uuid4())

        with pytest.raises(InvalidJournalStateTransitionError):
            journal_service.batch_post(
                gl_setup["company_id"],
                [good_draft_1.id, good_draft_2.id],
                uuid4(),
            )

        # good_draft_1 must NOT have been posted despite being valid on its own.
        entry1 = posting_engine.get_journal(gl_setup["company_id"], good_draft_1.id)
        assert entry1.status == "DRAFT"

    def test_period_lock_mid_batch_rolls_back_the_whole_batch(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        fiscal_service = FiscalCalendarService(
            db=posting_engine.db,
            year_repo=FiscalYearRepository(posting_engine.db),
            period_repo=FiscalPeriodRepository(posting_engine.db),
            opening_balance_repo=OpeningBalanceRepository(posting_engine.db),
            audit_service=AuditLogService(
                db=posting_engine.db,
                audit_repo=AccountingAuditLogRepository(posting_engine.db),
            ),
        )
        good_draft = _draft(posting_engine, gl_setup)
        to_lock_draft = _draft(posting_engine, gl_setup)

        year = fiscal_service.list_fiscal_years(gl_setup["company_id"])[0]
        periods = fiscal_service.list_periods(gl_setup["company_id"], year.id)
        current_period = next(
            p for p in periods if p.start_date <= gl_setup["today"] <= p.end_date
        )
        fiscal_service.lock_period(
            gl_setup["company_id"], current_period.id, uuid4(), "close"
        )

        with pytest.raises(PostingValidationError, match="Period is locked"):
            journal_service.batch_post(
                gl_setup["company_id"], [good_draft.id, to_lock_draft.id], uuid4()
            )

        entry = posting_engine.get_journal(gl_setup["company_id"], good_draft.id)
        assert entry.status == "DRAFT"  # not posted despite being otherwise valid

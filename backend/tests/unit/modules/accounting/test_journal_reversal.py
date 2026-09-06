"""Unit tests for journal reversal — Phase 5.

Reversal itself was implemented and verified in Phase 4
(``PostingEngine.reverse()``, ``test_gl_immutability.py``,
``test_journal_api.py``). This file specifically covers T129's exact
assertions via the Phase 5 ``JournalEntryService`` facade:
  - The reversal entry has every line's debit/credit swapped (opposite sign)
  - The original entry is marked REVERSED
  - The reversal entry links to the original (``reversal_of_journal_id``)

Spec ref: specs/008-accounting-finance/tasks.md T129
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.exceptions import JournalNotReversibleError
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
        company_id,
        "FY-Reversal",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"company_id": company_id, "ar": ar, "revenue": revenue, "today": today}


class TestReversalOppositeSign:
    def test_reversal_entry_has_swapped_debit_credit(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("800"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("800"),
                },
            ],
            currency_code="USD",
        )
        original_lines = {
            (line.account_id): (line.debit_amount, line.credit_amount)
            for line in posting_engine.get_lines(result.journal_entry_id)
        }

        reversal = journal_service.reverse_journal(
            gl_setup["company_id"],
            result.journal_entry_id,
            uuid4(),
            reason="correction",
        )
        reversal_lines = {
            (line.account_id): (line.debit_amount, line.credit_amount)
            for line in posting_engine.get_lines(reversal.id)
        }

        for account_id, (orig_debit, orig_credit) in original_lines.items():
            rev_debit, rev_credit = reversal_lines[account_id]
            assert rev_debit == orig_credit
            assert rev_credit == orig_debit

        assert reversal.total_debit_base == reversal.total_credit_base


class TestOriginalMarkedReversed:
    def test_original_status_becomes_reversed(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("300"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("300"),
                },
            ],
            currency_code="USD",
        )
        journal_service.reverse_journal(
            gl_setup["company_id"], result.journal_entry_id, uuid4()
        )

        original = posting_engine.get_journal(
            gl_setup["company_id"], result.journal_entry_id
        )
        assert original.status == "REVERSED"


class TestReversalLinksToOriginal:
    def test_reversal_entry_references_original(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("120"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("120"),
                },
            ],
            currency_code="USD",
        )
        reversal = journal_service.reverse_journal(
            gl_setup["company_id"], result.journal_entry_id, uuid4()
        )
        assert reversal.reversal_of_journal_id == result.journal_entry_id
        assert reversal.is_reversal is True


class TestOnlyPostedCanBeReversed:
    def test_draft_cannot_be_reversed(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        draft = posting_engine.create_journal(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("50"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("50"),
                },
            ],
            currency_code="USD",
        )
        with pytest.raises(JournalNotReversibleError):
            journal_service.reverse_journal(gl_setup["company_id"], draft.id, uuid4())

    def test_already_reversed_cannot_be_reversed_again(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict,
    ) -> None:
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("60"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("60"),
                },
            ],
            currency_code="USD",
        )
        journal_service.reverse_journal(
            gl_setup["company_id"], result.journal_entry_id, uuid4()
        )
        with pytest.raises(JournalNotReversibleError):
            journal_service.reverse_journal(
                gl_setup["company_id"], result.journal_entry_id, uuid4()
            )

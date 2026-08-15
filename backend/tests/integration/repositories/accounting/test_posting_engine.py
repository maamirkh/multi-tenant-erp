"""Integration tests for PostingEngine against the real repository/DB layer.

Tests:
  - Post a journal → verify GL lines persisted with correct account/amounts
  - SUM(debit) == SUM(credit) verified directly against the DB
  - journal_number is gap-free across 100 sequential postings

The 100-concurrent-postings requirement (tasks.md T109) uses a
**sequential** loop, not real OS threads — mirrors T044's documented
limitation for `AccountingSequenceService`: the SQLite `StaticPool` test
engine is documented unsafe for genuine concurrent multi-threaded
checkout, and real row-lock (`SELECT ... FOR UPDATE`) contention behavior
requires PostgreSQL. True concurrent-posting verification is deferred to
Docker/Postgres (T114).

Spec ref: specs/008-accounting-finance/tasks.md T109
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account
from modules.accounting.models.gl import JournalLine
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
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.sequence_service import AccountingSequenceService


def _build_engine(db_session: Session) -> PostingEngine:
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


def _setup_company(db_session: Session) -> dict:
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
    year = fiscal_service.create_fiscal_year(
        company_id, "FY2061", date(2061, 1, 1), date(2061, 12, 31), "USD"
    )
    return {"company_id": company_id, "ar": ar, "revenue": revenue, "year": year}


class TestPostJournalPersistsGLLines:
    def test_post_creates_correct_gl_lines(self, db_session: Session) -> None:
        setup = _setup_company(db_session)
        engine = _build_engine(db_session)

        result = engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=date(2061, 5, 10),
            lines=[
                {
                    "account_id": setup["ar"].id,
                    "debit_amount": Decimal("2500.50"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("2500.50"),
                },
            ],
            currency_code="USD",
        )

        lines = list(
            db_session.execute(
                select(JournalLine).where(
                    JournalLine.journal_entry_id == result.journal_entry_id
                )
            )
            .scalars()
            .all()
        )
        assert len(lines) == 2
        assert {line.account_code for line in lines} == {"1100", "4000"}

    def test_sum_debit_equals_sum_credit_in_db(self, db_session: Session) -> None:
        setup = _setup_company(db_session)
        engine = _build_engine(db_session)

        result = engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=date(2061, 6, 1),
            lines=[
                {
                    "account_id": setup["ar"].id,
                    "debit_amount": Decimal("777.77"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("777.77"),
                },
            ],
            currency_code="USD",
        )

        from sqlalchemy import func

        total_debit, total_credit = db_session.execute(
            select(
                func.sum(JournalLine.debit_amount), func.sum(JournalLine.credit_amount)
            ).where(JournalLine.journal_entry_id == result.journal_entry_id)
        ).one()
        assert total_debit == total_credit == Decimal("777.77")


class TestGapFreeNumbering:
    def test_100_sequential_postings_produce_no_gaps(self, db_session: Session) -> None:
        setup = _setup_company(db_session)
        engine = _build_engine(db_session)

        numbers = []
        for _ in range(100):
            result = engine.post_direct(
                company_id=setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(2061, 7, 1),
                lines=[
                    {
                        "account_id": setup["ar"].id,
                        "debit_amount": Decimal("1"),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["revenue"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": Decimal("1"),
                    },
                ],
                currency_code="USD",
            )
            numbers.append(int(result.journal_number.split("-")[-1]))

        assert numbers == list(range(numbers[0], numbers[0] + 100))
        assert len(set(numbers)) == 100

"""Integration tests for GL immutability — Phase 4 (CRITICAL).

The real invariant (tasks.md T095/T110: "attempt UPDATE on
accounting_journal_lines → DB constraint blocks it; attempt DELETE → DB
constraint blocks it") is enforced by a PostgreSQL ``BEFORE UPDATE OR
DELETE`` trigger (migration 038) — ``plpgsql`` triggers do not exist under
the SQLite test engine, and this codebase has no existing precedent of
testing a Postgres-only trigger through the SQLite-based pytest suite
(e.g. Sales' `trg_customer_tsvector`, migration 026, has zero test
coverage in this suite either — verified only via Docker/real Postgres).

What IS verified here, at the application/repository layer under SQLite:
  - ``JournalLineRepository`` exposes no ``update``/``delete`` method at
    all — there is structurally no code path in this codebase that could
    mutate a posted line, independent of the DB trigger.
  - A journal, once posted, is never revisited by any ``PostingEngine``
    method except ``reverse()``, which only ever INSERTs new rows.

The actual DB-trigger enforcement is verified against real PostgreSQL as
part of Docker verification (T114), where ``UPDATE``/``DELETE`` against
``accounting_journal_lines`` are executed directly via ``psql`` and
confirmed to raise.

Spec ref: specs/008-accounting-finance/tasks.md T110
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
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


class TestJournalLineRepositoryHasNoMutationMethods:
    def test_no_update_method_exists(self, db_session: Session) -> None:
        repo = JournalLineRepository(db_session)
        assert not hasattr(repo, "update")

    def test_no_delete_method_exists(self, db_session: Session) -> None:
        repo = JournalLineRepository(db_session)
        assert not hasattr(repo, "delete")
        assert not hasattr(repo, "soft_delete")

    def test_only_create_and_read_methods_exist(self, db_session: Session) -> None:
        repo = JournalLineRepository(db_session)
        public_methods = {
            name
            for name in dir(repo)
            if not name.startswith("_") and callable(getattr(repo, name))
        }
        assert public_methods == {"create", "find_by_journal_entry"}


class TestAccountingAuditLogRepositoryHasNoMutationMethods:
    def test_only_create_and_read_methods_exist(self, db_session: Session) -> None:
        repo = AccountingAuditLogRepository(db_session)
        public_methods = {
            name
            for name in dir(repo)
            if not name.startswith("_") and callable(getattr(repo, name))
        }
        # list_filtered (Phase 14, T279) is a read-only, filterable/paginated
        # query added for GET /accounting/audit-log — no new write/mutation
        # surface; the append-only guarantee this test protects (no
        # update()/delete()) still holds.
        assert public_methods == {"create", "list_for_entity", "list_filtered"}


class TestReversalNeverMutatesOriginalLines:
    def test_reverse_only_inserts_new_lines(self, db_session: Session) -> None:
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
        today = utcnow().date()
        fiscal_service.create_fiscal_year(
            company_id,
            "FY2062",
            date(today.year, 1, 1),
            date(today.year, 12, 31),
            "USD",
        )

        engine = _build_engine(db_session)
        result = engine.post_direct(
            company_id=company_id,
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=today,
            lines=[
                {
                    "account_id": ar.id,
                    "debit_amount": Decimal("300"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": revenue.id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("300"),
                },
            ],
            currency_code="USD",
        )
        original_lines_before = engine.get_lines(result.journal_entry_id)
        original_snapshot = [
            (line.id, line.debit_amount, line.credit_amount)
            for line in original_lines_before
        ]

        engine.reverse(company_id, result.journal_entry_id, uuid4(), reason="test")

        original_lines_after = engine.get_lines(result.journal_entry_id)
        assert [
            (line.id, line.debit_amount, line.credit_amount)
            for line in original_lines_after
        ] == original_snapshot

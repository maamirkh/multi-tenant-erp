"""Integration tests for the accounting audit log — Phase 4.

Tests:
  - Every journal state change (create/submit/approve/reject/post/reverse)
    produces an audit record
  - Audit records cannot be deleted (no delete method exists at all)

Spec ref: specs/008-accounting-finance/tasks.md T111
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
from tests.fixtures.users_roles_fixtures import grant_permission_to_user


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


class TestAuditRecordedOnEveryStateChange:
    def test_create_submit_approve_post_reverse_all_audited(
        self, db_session: Session
    ) -> None:
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
        creator_id = uuid4()
        approver_id = uuid4()
        grant_permission_to_user(
            db_session,
            company_id=company_id,
            user_id=approver_id,
            permission_code="accounting.journal.approve",
        )
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
            "FY-Audit",
            date(today.year, 1, 1),
            date(today.year, 12, 31),
            "USD",
        )

        engine = _build_engine(db_session)
        audit_repo = AccountingAuditLogRepository(db_session)
        lines = [
            {
                "account_id": ar.id,
                "debit_amount": Decimal("400"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": revenue.id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("400"),
            },
        ]

        draft = engine.create_journal(
            company_id=company_id,
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=today,
            lines=lines,
            currency_code="USD",
            created_by=creator_id,
        )
        engine.submit(company_id, draft.id, creator_id)
        engine.approve(company_id, draft.id, approver_id)
        engine.post(company_id, draft.id, approver_id)
        engine.reverse(company_id, draft.id, approver_id, reason="audit test reversal")

        audit_records = audit_repo.list_for_entity(company_id, "JournalEntry", draft.id)
        actions = [r.action for r in audit_records]
        assert actions == ["CREATED", "SUBMITTED", "APPROVED", "POSTED", "REVERSED"]
        assert all(r.company_id == company_id for r in audit_records)
        assert all(r.entity_type == "JournalEntry" for r in audit_records)

    def test_reject_is_audited(self, db_session: Session) -> None:
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
        rejector_id = uuid4()
        # Regression: reject() was fixed during the pre-Epic-9 hardening
        # audit (2026-08-15) to require accounting.journal.approve — the
        # same permission approve() already requires — since reject is the
        # mirror decision on the same SUBMITTED entry. Grant it here to
        # match the sibling approve-path test above.
        grant_permission_to_user(
            db_session,
            company_id=company_id,
            user_id=rejector_id,
            permission_code="accounting.journal.approve",
        )
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
            "FY-Audit2",
            date(today.year, 1, 1),
            date(today.year, 12, 31),
            "USD",
        )
        engine = _build_engine(db_session)
        audit_repo = AccountingAuditLogRepository(db_session)

        draft = engine.create_journal(
            company_id=company_id,
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=today,
            lines=[
                {
                    "account_id": ar.id,
                    "debit_amount": Decimal("50"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": revenue.id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("50"),
                },
            ],
            currency_code="USD",
        )
        engine.submit(company_id, draft.id, uuid4())
        engine.reject(
            company_id, draft.id, rejector_id, rejection_reason="incorrect account"
        )

        records = audit_repo.list_for_entity(company_id, "JournalEntry", draft.id)
        rejected = [r for r in records if r.action == "REJECTED"]
        assert len(rejected) == 1
        assert rejected[0].reason == "incorrect account"


class TestAuditLogRepositoryHasNoDeleteMethod:
    def test_no_delete_or_update_method_exists(self, db_session: Session) -> None:
        repo = AccountingAuditLogRepository(db_session)
        assert not hasattr(repo, "delete")
        assert not hasattr(repo, "update")

"""Unit tests for self-approval prevention — Phase 5.

Self-approval prevention was implemented and enforced inside
``PostingEngine.approve()`` in Phase 4. This file specifically covers
T130's exact assertion via the Phase 5 ``JournalEntryService`` facade:
same user creates + approves -> raises ``SelfApprovalNotAllowedError``.

Spec ref: specs/008-accounting-finance/tasks.md T130
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.exceptions import SelfApprovalNotAllowedError
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
from tests.fixtures.users_roles_fixtures import grant_permission_to_user


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
def gl_setup(db_session: Session) -> dict[str, Any]:
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
        "FY-Approval",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"company_id": company_id, "ar": ar, "revenue": revenue, "today": today}


class TestSelfApprovalPrevention:
    def test_creator_cannot_approve_own_journal(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
    ) -> None:
        creator_id = uuid4()
        draft = posting_engine.create_journal(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("400"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("400"),
                },
            ],
            currency_code="USD",
            created_by=creator_id,
        )
        posting_engine.submit(gl_setup["company_id"], draft.id, creator_id)

        with pytest.raises(SelfApprovalNotAllowedError):
            journal_service.approve_journal(
                gl_setup["company_id"], draft.id, creator_id
            )

    def test_different_approver_succeeds(
        self,
        journal_service: JournalEntryService,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        db_session: Session,
    ) -> None:
        creator_id = uuid4()
        approver_id = uuid4()
        grant_permission_to_user(
            db_session,
            company_id=gl_setup["company_id"],
            user_id=approver_id,
            permission_code="accounting.journal.approve",
        )
        draft = posting_engine.create_journal(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=gl_setup["today"],
            lines=[
                {
                    "account_id": gl_setup["ar"].id,
                    "debit_amount": Decimal("400"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": gl_setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("400"),
                },
            ],
            currency_code="USD",
            created_by=creator_id,
        )
        posting_engine.submit(gl_setup["company_id"], draft.id, creator_id)

        approved = journal_service.approve_journal(
            gl_setup["company_id"], draft.id, approver_id
        )
        assert approved.status == "APPROVED"

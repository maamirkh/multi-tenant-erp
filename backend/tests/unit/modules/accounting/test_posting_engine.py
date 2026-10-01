"""Unit tests for PostingEngine — Phase 4 (CRITICAL).

CRITICAL: ALL 7 validation steps must be tested individually (tasks.md T107):
  T107a: Balanced journal PASSES
  T107b: Unbalanced journal raises PostingValidationError
  T107c: Inactive account raises PostingValidationError
  T107d: Non-leaf account raises PostingValidationError
  T107e: Locked period raises PostingValidationError
  T107f: Missing cost center (when required) raises PostingValidationError
  T107g: Unapproved journal above threshold raises PostingValidationError

Spec ref: specs/008-accounting-finance/tasks.md T107
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.exceptions import PostingValidationError
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


@pytest.fixture
def account_repo(db_session: Session) -> AccountRepository:
    return AccountRepository(db_session)


@pytest.fixture
def fiscal_service(db_session: Session) -> FiscalCalendarService:
    return FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )


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
def gl_setup(
    account_repo: AccountRepository, fiscal_service: FiscalCalendarService
) -> dict[str, Any]:
    """Company with an AR (asset) account, a Revenue account, and an OPEN fiscal year."""
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
        company_id, "FY2060", date(2060, 1, 1), date(2060, 12, 31), "USD"
    )
    return {"company_id": company_id, "ar": ar, "revenue": revenue, "year": year}


def _lines(ar_id, revenue_id, amount: Decimal = Decimal("1000")):
    return [
        {"account_id": ar_id, "debit_amount": amount, "credit_amount": Decimal("0")},
        {
            "account_id": revenue_id,
            "debit_amount": Decimal("0"),
            "credit_amount": amount,
        },
    ]


class TestT107aBalancedJournalPasses:
    def test_balanced_journal_posts_successfully(
        self, posting_engine: PostingEngine, gl_setup: dict[str, Any]
    ) -> None:
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=date(2060, 3, 15),
            lines=_lines(gl_setup["ar"].id, gl_setup["revenue"].id),
            currency_code="USD",
            actor_id=uuid4(),
        )
        assert result.journal_number is not None
        entry = posting_engine.get_journal(
            gl_setup["company_id"], result.journal_entry_id
        )
        assert entry.status == "POSTED"
        assert entry.is_balanced is True
        assert entry.total_debit_base == entry.total_credit_base == Decimal("1000")


class TestT107bUnbalancedRejected:
    def test_unbalanced_journal_raises(
        self, posting_engine: PostingEngine, gl_setup: dict[str, Any]
    ) -> None:
        with pytest.raises(PostingValidationError, match="Journal must balance"):
            posting_engine.post_direct(
                company_id=gl_setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(2060, 3, 15),
                lines=[
                    {
                        "account_id": gl_setup["ar"].id,
                        "debit_amount": Decimal("100"),
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


class TestT107cInactiveAccountRejected:
    def test_inactive_account_raises(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        account_repo: AccountRepository,
    ) -> None:
        inactive = account_repo.create(
            Account(
                company_id=gl_setup["company_id"],
                account_code="9000",
                account_name="Inactive",
                account_type="EXPENSE",
                is_active=False,
            )
        )
        with pytest.raises(PostingValidationError, match="Invalid account"):
            posting_engine.post_direct(
                company_id=gl_setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(2060, 3, 15),
                lines=_lines(inactive.id, gl_setup["revenue"].id, Decimal("100")),
                currency_code="USD",
            )


class TestT107dNonLeafAccountRejected:
    def test_non_leaf_account_raises(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        account_repo: AccountRepository,
    ) -> None:
        parent = account_repo.create(
            Account(
                company_id=gl_setup["company_id"],
                account_code="2000",
                account_name="Parent",
                account_type="LIABILITY",
                is_leaf=False,
            )
        )
        with pytest.raises(PostingValidationError, match="Invalid account"):
            posting_engine.post_direct(
                company_id=gl_setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(2060, 3, 15),
                lines=_lines(parent.id, gl_setup["revenue"].id, Decimal("100")),
                currency_code="USD",
            )


class TestT107eLockedPeriodRejected:
    def test_locked_period_raises(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        fiscal_service: FiscalCalendarService,
    ) -> None:
        periods = fiscal_service.list_periods(
            gl_setup["company_id"], gl_setup["year"].id
        )
        march = periods[2]
        fiscal_service.lock_period(
            gl_setup["company_id"], march.id, uuid4(), "month-end close"
        )

        with pytest.raises(PostingValidationError, match="Period is locked"):
            posting_engine.post_direct(
                company_id=gl_setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(2060, 3, 15),
                lines=_lines(gl_setup["ar"].id, gl_setup["revenue"].id, Decimal("100")),
                currency_code="USD",
            )

    def test_no_period_defined_raises(
        self, posting_engine: PostingEngine, gl_setup: dict[str, Any]
    ) -> None:
        with pytest.raises(PostingValidationError, match="Period is locked"):
            posting_engine.post_direct(
                company_id=gl_setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(1999, 1, 1),
                lines=_lines(gl_setup["ar"].id, gl_setup["revenue"].id, Decimal("100")),
                currency_code="USD",
            )


class TestT107fMissingCostCenterRejected:
    def test_missing_cost_center_raises_when_required(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        account_repo: AccountRepository,
    ) -> None:
        cc_account = account_repo.create(
            Account(
                company_id=gl_setup["company_id"],
                account_code="5000",
                account_name="Expense requiring CC",
                account_type="EXPENSE",
                requires_cost_center=True,
            )
        )
        with pytest.raises(PostingValidationError, match="Cost center required"):
            posting_engine.post_direct(
                company_id=gl_setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=date(2060, 3, 15),
                lines=_lines(cc_account.id, gl_setup["revenue"].id, Decimal("100")),
                currency_code="USD",
            )

    def test_cost_center_present_passes(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        account_repo: AccountRepository,
    ) -> None:
        cc_account = account_repo.create(
            Account(
                company_id=gl_setup["company_id"],
                account_code="5001",
                account_name="Expense requiring CC 2",
                account_type="EXPENSE",
                requires_cost_center=True,
            )
        )
        lines = [
            {
                "account_id": cc_account.id,
                "debit_amount": Decimal("100"),
                "credit_amount": Decimal("0"),
                "cost_center_id": uuid4(),
            },
            {
                "account_id": gl_setup["revenue"].id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("100"),
            },
        ]
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=date(2060, 3, 15),
            lines=lines,
            currency_code="USD",
        )
        assert result.journal_number is not None


class TestT107gApprovalRequiredAboveThreshold:
    def test_unapproved_above_threshold_raises(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        db_session: Session,
    ) -> None:
        flag_service = AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        )
        flag_service.enable(
            company_id=gl_setup["company_id"],
            flag_key="accounting.approvalworkflow.enabled",
        )
        config_repo = AccountingConfigurationRepository(db_session)
        from modules.accounting.models.foundation import AccountingConfiguration

        config_repo.create(
            AccountingConfiguration(
                company_id=gl_setup["company_id"],
                journal_approval_threshold=Decimal("500"),
            )
        )

        draft = posting_engine.create_journal(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=date(2060, 3, 15),
            lines=_lines(gl_setup["ar"].id, gl_setup["revenue"].id, Decimal("1000")),
            currency_code="USD",
        )
        with pytest.raises(PostingValidationError, match="Approval required"):
            posting_engine.post(gl_setup["company_id"], draft.id, actor_id=uuid4())

    def test_approved_above_threshold_posts(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        db_session: Session,
    ) -> None:
        flag_service = AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        )
        flag_service.enable(
            company_id=gl_setup["company_id"],
            flag_key="accounting.approvalworkflow.enabled",
        )
        config_repo = AccountingConfigurationRepository(db_session)
        from modules.accounting.models.foundation import AccountingConfiguration

        config_repo.create(
            AccountingConfiguration(
                company_id=gl_setup["company_id"],
                journal_approval_threshold=Decimal("500"),
            )
        )

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
            posting_date=date(2060, 3, 15),
            lines=_lines(gl_setup["ar"].id, gl_setup["revenue"].id, Decimal("1000")),
            currency_code="USD",
            created_by=creator_id,
        )
        posting_engine.submit(gl_setup["company_id"], draft.id, creator_id)
        posting_engine.approve(gl_setup["company_id"], draft.id, approver_id)
        result = posting_engine.post(gl_setup["company_id"], draft.id, approver_id)
        assert result.journal_number is not None

    def test_below_threshold_posts_without_approval(
        self,
        posting_engine: PostingEngine,
        gl_setup: dict[str, Any],
        db_session: Session,
    ) -> None:
        flag_service = AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        )
        flag_service.enable(
            company_id=gl_setup["company_id"],
            flag_key="accounting.approvalworkflow.enabled",
        )
        config_repo = AccountingConfigurationRepository(db_session)
        from modules.accounting.models.foundation import AccountingConfiguration

        config_repo.create(
            AccountingConfiguration(
                company_id=gl_setup["company_id"],
                journal_approval_threshold=Decimal("5000"),
            )
        )
        result = posting_engine.post_direct(
            company_id=gl_setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=date(2060, 3, 15),
            lines=_lines(gl_setup["ar"].id, gl_setup["revenue"].id, Decimal("1000")),
            currency_code="USD",
        )
        assert result.journal_number is not None

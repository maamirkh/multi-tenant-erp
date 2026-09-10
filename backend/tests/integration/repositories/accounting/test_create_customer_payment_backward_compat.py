"""[Epic 10, Phase 6, T111] Backward-compatibility regression: every
existing standalone caller of ``PaymentService.create_customer_payment()``
must see identical behavior/return type after it was rewritten (tasks.md
T103) into a thin wrapper of ``stage_customer_payment()`` +
``finalize_customer_payment()`` (plan.md §12.3.1) — including the
above-``payment_approval_threshold`` DRAFT branch's exact prior
behavior, which keeps its own pre-existing early commit unchanged.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service, build_payment_service
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.payments import Payment
from modules.accounting.repositories.banking import BankAccountRepository
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
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import PaymentService


@pytest.fixture
def setup(db_session: Session) -> dict[str, Any]:
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
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-BC-01",
            currency_code="USD",
            gl_account_id=bank_gl.id,
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(company_id=company_id, default_ar_account_id=ar.id)
    )
    return {"company_id": company_id, "bank": bank, "today": today}


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


@pytest.fixture
def ar_service(db_session: Session) -> AccountsReceivableService:
    return build_ar_service(db_session, with_sales_sync=False)


class TestCreateCustomerPaymentBackwardCompat:
    def test_immediate_post_branch_returns_posted_payment_and_result(
        self, payment_service: PaymentService, setup: dict[str, Any]
    ) -> None:
        payment, result = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("500.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        assert isinstance(payment, Payment)
        assert payment.status == "POSTED"
        assert payment.journal_entry_id is not None
        assert result is not None
        assert result.journal_entry_id == payment.journal_entry_id

    def test_credit_ar_transaction_created_and_allocatable(
        self,
        payment_service: PaymentService,
        ar_service: AccountsReceivableService,
        setup: dict[str, Any],
    ) -> None:
        customer_id = uuid4()
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("750.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        ledger = ar_service.get_customer_ledger(setup["company_id"], customer_id)
        # A credit (negative outstanding) exists — visible as a credit
        # balance until allocated, exactly as before this refactor.
        assert ledger.total_outstanding_base == Decimal("-750.00")
        assert payment.status == "POSTED"

    def test_above_threshold_draft_branch_unchanged(
        self,
        payment_service: PaymentService,
        db_session: Session,
        setup: dict[str, Any],
    ) -> None:
        """The pre-existing above-``payment_approval_threshold`` DRAFT
        branch keeps its own early commit unchanged — no GL/AR truth is
        created, and the public method still returns ``(payment, None)``
        exactly as before this refactor (plan.md §12.3.1)."""
        config_repo = AccountingConfigurationRepository(db_session)
        config = config_repo.get_for_company(company_id=setup["company_id"])
        assert config is not None
        config.payment_approval_threshold = Decimal("100.00")
        db_session.add(config)
        db_session.commit()

        AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        ).enable(setup["company_id"], "accounting.approvalworkflow.enabled")

        payment, result = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("500.00"),  # above the 100.00 threshold
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        assert payment.status == "DRAFT"
        assert payment.journal_entry_id is None
        assert result is None

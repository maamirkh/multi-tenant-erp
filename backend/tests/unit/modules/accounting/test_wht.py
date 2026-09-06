"""Unit tests for Withholding Tax (WHT) — Phase 10.

Tests (tasks.md T221): gross 1000, WHT 10% -> payment 900, WHT payable 100;
GL entries correct.

Spec ref: specs/008-accounting-finance/tasks.md T221, spec.md §23.7
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_payment_service
from modules.accounting.exceptions import PostingValidationError, WHTNotEnabledError
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.feature_flag import AccountingFeatureFlag
from modules.accounting.models.foundation import AccountingConfiguration
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
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import PaymentService


@pytest.fixture
def setup(db_session: Session) -> dict:
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

    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2000",
            account_name="AP",
            account_type="LIABILITY",
        )
    )
    wht_payable = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2100",
            account_name="WHT Payable",
            account_type="LIABILITY",
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
            account_number="ACC-0001",
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
        AccountingConfiguration(company_id=company_id, default_ap_account_id=ap.id)
    )

    return {
        "company_id": company_id,
        "ap": ap,
        "wht_payable": wht_payable,
        "bank": bank,
        "today": today,
    }


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


def _enable_wht(db_session: Session, company_id) -> None:
    AccountingFeatureFlagRepository(db_session).create(
        AccountingFeatureFlag(
            company_id=company_id,
            flag_key="accounting.taxwithholding.enabled",
            is_enabled=True,
        )
    )


class TestWHTDeduction:
    def test_gross_1000_wht_10_percent_yields_net_900_and_wht_payable_100(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        _enable_wht(payment_service.db, setup["company_id"])

        payment, result = payment_service.create_supplier_payment(
            company_id=setup["company_id"],
            supplier_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            wht_amount=Decimal("100.00"),
            wht_payable_account_id=setup["wht_payable"].id,
            actor_id=None,
        )

        assert payment.amount_base == Decimal("1000.00")
        assert payment.wht_amount == Decimal("100.00")

        gl_reports = GLReportRepository(payment_service.db)

        ap_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["ap"].id
        )
        assert ap_balance["total_debit"] - ap_balance["total_credit"] == Decimal(
            "1000.00"
        )

        wht_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["wht_payable"].id
        )
        assert wht_balance["total_credit"] - wht_balance["total_debit"] == Decimal(
            "100.00"
        )

        bank_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["bank"].gl_account_id
        )
        assert bank_balance["total_credit"] - bank_balance["total_debit"] == Decimal(
            "900.00"
        )

        assert result.journal_entry_id == payment.journal_entry_id

    def test_wht_certificate_reports_gross_net_and_rate(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        _enable_wht(payment_service.db, setup["company_id"])
        payment, _ = payment_service.create_supplier_payment(
            company_id=setup["company_id"],
            supplier_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            wht_amount=Decimal("100.00"),
            wht_payable_account_id=setup["wht_payable"].id,
            actor_id=None,
        )

        certificate = payment_service.get_wht_certificate(
            setup["company_id"], payment.id
        )
        assert certificate["gross_amount"] == Decimal("1000.00")
        assert certificate["wht_amount"] == Decimal("100.00")
        assert certificate["net_amount"] == Decimal("900.00")
        assert certificate["wht_rate_percent"] == Decimal("10.00")

    def test_wht_without_flag_enabled_raises(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        with pytest.raises(WHTNotEnabledError):
            payment_service.create_supplier_payment(
                company_id=setup["company_id"],
                supplier_id=uuid4(),
                payment_method="BANK_TRANSFER",
                payment_date=setup["today"],
                amount=Decimal("1000.00"),
                currency_code="USD",
                bank_account_id=setup["bank"].id,
                wht_amount=Decimal("100.00"),
                wht_payable_account_id=setup["wht_payable"].id,
                actor_id=None,
            )

    def test_wht_without_payable_account_raises(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        _enable_wht(payment_service.db, setup["company_id"])
        with pytest.raises(PostingValidationError):
            payment_service.create_supplier_payment(
                company_id=setup["company_id"],
                supplier_id=uuid4(),
                payment_method="BANK_TRANSFER",
                payment_date=setup["today"],
                amount=Decimal("1000.00"),
                currency_code="USD",
                bank_account_id=setup["bank"].id,
                wht_amount=Decimal("100.00"),
                actor_id=None,
            )

    def test_supplier_payment_without_wht_has_zero_wht_amount(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        payment, _ = payment_service.create_supplier_payment(
            company_id=setup["company_id"],
            supplier_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("500.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        assert payment.wht_amount == Decimal("0")

        gl_reports = GLReportRepository(payment_service.db)
        bank_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["bank"].gl_account_id
        )
        assert bank_balance["total_credit"] - bank_balance["total_debit"] == Decimal(
            "500.00"
        )

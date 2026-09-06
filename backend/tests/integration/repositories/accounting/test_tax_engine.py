"""Integration tests for the Tax Engine — Phase 11.

Tests (tasks.md T245):
  - Post invoice with VAT code -> verify tax GL entry created
  - Run VAT summary -> verify output == sum of posted tax amounts

Also covers cost center P&L aggregation (plan.md Phase 10 acceptance
criteria: "Cost center P&L aggregates GL entries by cost_center_id") and
the WHT report reading Phase 10's ``Payment.wht_amount`` directly.

Spec ref: specs/008-accounting-finance/tasks.md T245
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_cost_center_service,
    build_payment_service,
    build_posting_engine,
    build_tax_calculator,
    build_tax_service,
)
from modules.accounting.exceptions import PostingValidationError
from modules.accounting.models.coa import Account
from modules.accounting.models.cost import CostCenter
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.tax import TaxCode, TaxRate
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.cost import CostCenterRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.repositories.tax import TaxCodeRepository, TaxRateRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.cost_center_service import CostCenterService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import PaymentService
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.tax_calculator import TaxCalculator
from modules.accounting.services.tax_service import TaxService


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
            account_name="Sales Revenue",
            account_type="REVENUE",
        )
    )
    expense = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5000",
            account_name="Operating Expense",
            account_type="EXPENSE",
        )
    )
    vat_payable = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2200",
            account_name="VAT Payable",
            account_type="LIABILITY",
        )
    )
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2000",
            account_name="AP",
            account_type="LIABILITY",
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
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_ap_account_id=ap.id,
            default_revenue_account_id=revenue.id,
        )
    )

    tax_code_repo = TaxCodeRepository(db_session)
    vat_code = tax_code_repo.create(
        TaxCode(
            company_id=company_id,
            tax_code="VAT-15",
            tax_name="Standard VAT 15%",
            tax_type="VAT",
            applicability="SALES",
            gl_account_id=vat_payable.id,
            is_input_tax_recoverable=False,
        )
    )
    TaxRateRepository(db_session).create(
        TaxRate(
            company_id=company_id,
            tax_code_id=vat_code.id,
            effective_from=date(today.year, 1, 1),
            effective_to=None,
            rate=Decimal("15.0"),
        )
    )

    return {
        "company_id": company_id,
        "ar": ar,
        "revenue": revenue,
        "expense": expense,
        "vat_payable": vat_payable,
        "vat_code": vat_code,
        "today": today,
    }


@pytest.fixture
def posting_engine(db_session: Session) -> PostingEngine:
    return build_posting_engine(db_session)


@pytest.fixture
def tax_calculator(db_session: Session) -> TaxCalculator:
    return build_tax_calculator(db_session)


@pytest.fixture
def tax_service(db_session: Session) -> TaxService:
    return build_tax_service(db_session)


@pytest.fixture
def cost_center_service(db_session: Session) -> CostCenterService:
    return build_cost_center_service(db_session)


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


class TestPostInvoiceWithVATAndSummaryReconciliation:
    def test_post_invoice_with_vat_creates_tax_gl_entry_and_summary_matches(
        self,
        posting_engine: PostingEngine,
        tax_calculator: TaxCalculator,
        tax_service: TaxService,
        setup: dict,
    ) -> None:
        tax_lines = tax_calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["vat_code"].id,
            base_amount=Decimal("1000.00"),
            transaction_date=setup["today"],
        )
        assert len(tax_lines) == 1
        tax_amount = tax_lines[0].tax_amount
        assert tax_amount == Decimal("150.00")

        result = posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="AUTOMATED",
            posting_source="SALES",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["ar"].id,
                    "debit_amount": Decimal("1000.00") + tax_amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("1000.00"),
                },
                {
                    "account_id": setup["vat_payable"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": tax_amount,
                },
            ],
            currency_code="USD",
            description="Sales invoice with VAT",
            source_document_type="SalesInvoice",
            actor_id=None,
        )
        assert result.journal_entry_id is not None

        summary = tax_service.get_vat_summary_report(
            company_id=setup["company_id"],
            period_start=setup["today"],
            period_end=setup["today"],
        )
        assert len(summary["rows"]) == 1
        assert summary["rows"][0]["tax_code"] == "VAT-15"
        assert summary["rows"][0]["output_tax"] == Decimal("150.00")
        assert summary["total_output_tax"] == Decimal("150.00")

    def test_summary_output_equals_sum_of_multiple_posted_tax_entries(
        self,
        posting_engine: PostingEngine,
        tax_calculator: TaxCalculator,
        tax_service: TaxService,
        setup: dict,
    ) -> None:
        total_expected_tax = Decimal("0")
        for base in (Decimal("1000.00"), Decimal("2000.00"), Decimal("500.00")):
            tax_lines = tax_calculator.calculate(
                company_id=setup["company_id"],
                tax_code_or_group_id=setup["vat_code"].id,
                base_amount=base,
                transaction_date=setup["today"],
            )
            tax_amount = tax_lines[0].tax_amount
            total_expected_tax += tax_amount

            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="AUTOMATED",
                posting_source="SALES",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": setup["ar"].id,
                        "debit_amount": base + tax_amount,
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["revenue"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": base,
                    },
                    {
                        "account_id": setup["vat_payable"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": tax_amount,
                    },
                ],
                currency_code="USD",
                source_document_type="SalesInvoice",
                actor_id=None,
            )

        summary = tax_service.get_vat_summary_report(
            company_id=setup["company_id"],
            period_start=setup["today"],
            period_end=setup["today"],
        )
        assert summary["total_output_tax"] == total_expected_tax
        assert total_expected_tax == Decimal("525.00")  # 150 + 300 + 75

    def test_tax_detail_report_lists_every_taxable_transaction(
        self,
        posting_engine: PostingEngine,
        tax_calculator: TaxCalculator,
        tax_service: TaxService,
        setup: dict,
    ) -> None:
        for base in (Decimal("100.00"), Decimal("200.00")):
            tax_amount = tax_calculator.calculate(
                company_id=setup["company_id"],
                tax_code_or_group_id=setup["vat_code"].id,
                base_amount=base,
                transaction_date=setup["today"],
            )[0].tax_amount
            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="AUTOMATED",
                posting_source="SALES",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": setup["ar"].id,
                        "debit_amount": base + tax_amount,
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["revenue"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": base,
                    },
                    {
                        "account_id": setup["vat_payable"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": tax_amount,
                    },
                ],
                currency_code="USD",
                actor_id=None,
            )

        rows = tax_service.get_tax_detail_report(
            company_id=setup["company_id"],
            period_start=setup["today"],
            period_end=setup["today"],
        )
        assert len(rows) == 2
        assert all(row["tax_code"] == "VAT-15" for row in rows)


class TestCostCenterPLAggregation:
    def test_cost_center_pl_aggregates_gl_entries_by_cost_center_id(
        self,
        posting_engine: PostingEngine,
        cost_center_service: CostCenterService,
        setup: dict,
    ) -> None:
        cost_center = CostCenterRepository(posting_engine.db).create(
            CostCenter(
                company_id=setup["company_id"],
                center_code="CC-01",
                center_name="Main Store",
            )
        )

        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["expense"].id,
                    "debit_amount": Decimal("300.00"),
                    "credit_amount": Decimal("0"),
                    "cost_center_id": cost_center.id,
                },
                {
                    "account_id": setup["ar"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("300.00"),
                },
            ],
            currency_code="USD",
            actor_id=None,
        )
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["ar"].id,
                    "debit_amount": Decimal("500.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("500.00"),
                    "cost_center_id": cost_center.id,
                },
            ],
            currency_code="USD",
            actor_id=None,
        )

        report = cost_center_service.get_cost_center_pl_report(
            company_id=setup["company_id"],
            cost_center_id=cost_center.id,
            period_start=setup["today"],
            period_end=setup["today"],
        )
        assert report["total_revenue"] == Decimal("500.00")
        assert report["total_expense"] == Decimal("300.00")
        assert report["net_income"] == Decimal("200.00")

    def test_posting_rejects_missing_cost_center_on_required_account(
        self, posting_engine: PostingEngine, setup: dict
    ) -> None:
        account_repo = AccountRepository(posting_engine.db)
        required_expense = account_repo.create(
            Account(
                company_id=setup["company_id"],
                account_code="5100",
                account_name="Departmental Expense",
                account_type="EXPENSE",
                requires_cost_center=True,
            )
        )

        with pytest.raises(PostingValidationError):
            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": required_expense.id,
                        "debit_amount": Decimal("50.00"),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["ar"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": Decimal("50.00"),
                    },
                ],
                currency_code="USD",
                actor_id=None,
            )


class TestWHTReport:
    def test_wht_report_reads_payment_wht_amount_by_supplier(
        self, payment_service: PaymentService, tax_service: TaxService, setup: dict
    ) -> None:
        from modules.accounting.models.banking import BankAccount
        from modules.accounting.repositories.banking import BankAccountRepository

        bank_gl = AccountRepository(payment_service.db).create(
            Account(
                company_id=setup["company_id"],
                account_code="1000",
                account_name="Bank",
                account_type="ASSET",
            )
        )
        bank = BankAccountRepository(payment_service.db).create(
            BankAccount(
                company_id=setup["company_id"],
                bank_name="Test Bank",
                account_number="ACC-0001",
                currency_code="USD",
                gl_account_id=bank_gl.id,
            )
        )
        wht_payable = AccountRepository(payment_service.db).create(
            Account(
                company_id=setup["company_id"],
                account_code="2100",
                account_name="WHT Payable",
                account_type="LIABILITY",
            )
        )

        from modules.accounting.models.feature_flag import AccountingFeatureFlag
        from modules.accounting.repositories.feature_flag_repository import (
            AccountingFeatureFlagRepository,
        )

        AccountingFeatureFlagRepository(payment_service.db).create(
            AccountingFeatureFlag(
                company_id=setup["company_id"],
                flag_key="accounting.taxwithholding.enabled",
                is_enabled=True,
            )
        )

        supplier_id = uuid4()
        payment_service.create_supplier_payment(
            company_id=setup["company_id"],
            supplier_id=supplier_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="USD",
            bank_account_id=bank.id,
            wht_amount=Decimal("100.00"),
            wht_payable_account_id=wht_payable.id,
            actor_id=None,
        )

        report = tax_service.get_wht_report(
            company_id=setup["company_id"],
            period_start=setup["today"],
            period_end=setup["today"],
        )
        assert len(report["rows"]) == 1
        assert report["rows"][0]["supplier_id"] == supplier_id
        assert report["rows"][0]["wht_amount"] == Decimal("100.00")
        assert report["total_wht"] == Decimal("100.00")

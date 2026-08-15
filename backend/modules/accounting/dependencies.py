"""FastAPI dependency injection functions for the Accounting module.

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend (Epics 1-7).

Spec ref: specs/008-accounting-finance/plan.md — Application Layer
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.accounting.repositories.ai import AccountingAnomalyFlagRepository
from modules.accounting.repositories.ap import (
    APPaymentAllocationRepository,
    APTransactionRepository,
    SupplierLedgerRepository,
    SupplierStatementReconciliationItemRepository,
    SupplierStatementReconciliationRepository,
)
from modules.accounting.repositories.ar import (
    ARPaymentAllocationRepository,
    ARTransactionRepository,
    CustomerCreditHistoryRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.banking import (
    BankAccountRepository,
    BankReconciliationMatchRepository,
    BankReconciliationRepository,
    BankStatementLineRepository,
    BankTransactionRepository,
    ChequeRepository,
)
from modules.accounting.repositories.cash import (
    CashAccountRepository,
    CashReconciliationRepository,
    CashTransactionRepository,
    PettyCashVoucherRepository,
)
from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)
from modules.accounting.repositories.cost import (
    CostCenterRepository,
    DepartmentRepository,
    ProjectRepository,
)
from modules.accounting.repositories.currency import CurrencyRevaluationRunRepository
from modules.accounting.repositories.feature_flag_repository import (
    AccountingFeatureFlagRepository,
)
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import (
    AccountingConfigurationRepository,
    CurrencyRepository,
    ExchangeRateRepository,
)
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
    JournalApprovalRepository,
    JournalEntryRepository,
    JournalLineRepository,
)
from modules.accounting.repositories.payments import (
    PaymentAllocationLineRepository,
    PaymentRefundRepository,
    PaymentRepository,
)
from modules.accounting.repositories.recurring import (
    RecurringJournalInstanceRepository,
    RecurringJournalTemplateLineRepository,
    RecurringJournalTemplateRepository,
)
from modules.accounting.repositories.tax import (
    TaxCodeRepository,
    TaxGroupLineRepository,
    TaxGroupRepository,
    TaxRateRepository,
)
from modules.accounting.services.ai_service import AIReadinessService
from modules.accounting.services.allocation_engine import AllocationEngine
from modules.accounting.services.ap_service import AccountsPayableService
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.bank_service import (
    BankAccountService,
    BankReconciliationService,
)
from modules.accounting.services.cash_service import CashAccountService
from modules.accounting.services.coa_service import ChartOfAccountsService
from modules.accounting.services.configuration_service import (
    AccountingConfigurationService,
)
from modules.accounting.services.cost_center_service import CostCenterService
from modules.accounting.services.currency_revaluation_service import (
    CurrencyRevaluationService,
)
from modules.accounting.services.currency_service import CurrencyService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.financial_statements import FinancialStatementService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.journal_service import JournalEntryService
from modules.accounting.services.kpi_service import FinancialKPIService
from modules.accounting.services.payment_service import PaymentService
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.recurring_journal_service import (
    RecurringJournalService,
)
from modules.accounting.services.report_service import ReportService
from modules.accounting.services.sequence_service import AccountingSequenceService
from modules.accounting.services.tax_calculator import TaxCalculator
from modules.accounting.services.tax_service import TaxService

if TYPE_CHECKING:
    from modules.sales.services.customer_service import CustomerService

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_accounting_feature_flag_repo(
    db: Session = Depends(get_db),
) -> AccountingFeatureFlagRepository:
    return AccountingFeatureFlagRepository(db)


def get_accounting_configuration_repo(
    db: Session = Depends(get_db),
) -> AccountingConfigurationRepository:
    return AccountingConfigurationRepository(db)


def get_currency_repo(db: Session = Depends(get_db)) -> CurrencyRepository:
    return CurrencyRepository(db)


def get_exchange_rate_repo(db: Session = Depends(get_db)) -> ExchangeRateRepository:
    return ExchangeRateRepository(db)


def get_account_repo(db: Session = Depends(get_db)) -> AccountRepository:
    return AccountRepository(db)


def get_account_group_repo(db: Session = Depends(get_db)) -> AccountGroupRepository:
    return AccountGroupRepository(db)


def get_fiscal_year_repo(db: Session = Depends(get_db)) -> FiscalYearRepository:
    return FiscalYearRepository(db)


def get_fiscal_period_repo(db: Session = Depends(get_db)) -> FiscalPeriodRepository:
    return FiscalPeriodRepository(db)


def get_opening_balance_repo(db: Session = Depends(get_db)) -> OpeningBalanceRepository:
    return OpeningBalanceRepository(db)


def get_currency_revaluation_run_repo(
    db: Session = Depends(get_db),
) -> CurrencyRevaluationRunRepository:
    return CurrencyRevaluationRunRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_accounting_feature_flag_service(
    db: Session = Depends(get_db),
) -> AccountingFeatureFlagService:
    return AccountingFeatureFlagService(
        db=db,
        flag_repo=AccountingFeatureFlagRepository(db),
    )


def get_accounting_configuration_service(
    db: Session = Depends(get_db),
) -> AccountingConfigurationService:
    return AccountingConfigurationService(
        db=db,
        config_repo=AccountingConfigurationRepository(db),
    )


def get_currency_service(db: Session = Depends(get_db)) -> CurrencyService:
    return CurrencyService(
        db=db,
        currency_repo=CurrencyRepository(db),
        exchange_rate_repo=ExchangeRateRepository(db),
    )


def get_accounting_sequence_service(
    db: Session = Depends(get_db),
) -> AccountingSequenceService:
    return AccountingSequenceService(db=db)


def get_chart_of_accounts_service(
    db: Session = Depends(get_db),
) -> ChartOfAccountsService:
    return ChartOfAccountsService(
        db=db,
        account_repo=AccountRepository(db),
        group_repo=AccountGroupRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        flag_service=AccountingFeatureFlagService(
            db=db, flag_repo=AccountingFeatureFlagRepository(db)
        ),
    )


def get_fiscal_calendar_service(
    db: Session = Depends(get_db),
) -> FiscalCalendarService:
    return FiscalCalendarService(
        db=db,
        year_repo=FiscalYearRepository(db),
        period_repo=FiscalPeriodRepository(db),
        opening_balance_repo=OpeningBalanceRepository(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )


def build_posting_engine(db: Session) -> PostingEngine:
    """Assemble a ``PostingEngine`` from a raw ``Session``.

    Plain function (not a FastAPI dependency itself) so it can be reused
    both by ``get_posting_engine`` (below, for router endpoints) and by
    ``handlers/integration_handlers.py`` (event-bus callbacks, which run
    outside any FastAPI request and construct their own ``Session`` via
    ``core.database.session.SessionLocal``).
    """
    return PostingEngine(
        db=db,
        journal_repo=JournalEntryRepository(db),
        line_repo=JournalLineRepository(db),
        approval_repo=JournalApprovalRepository(db),
        account_repo=AccountRepository(db),
        fiscal_period_repo=FiscalPeriodRepository(db),
        sequence_service=AccountingSequenceService(db),
        config_repo=AccountingConfigurationRepository(db),
        flag_service=AccountingFeatureFlagService(
            db=db, flag_repo=AccountingFeatureFlagRepository(db)
        ),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )


def get_posting_engine(db: Session = Depends(get_db)) -> PostingEngine:
    return build_posting_engine(db)


def get_journal_entry_repo(db: Session = Depends(get_db)) -> JournalEntryRepository:
    return JournalEntryRepository(db)


def get_gl_report_repo(db: Session = Depends(get_db)) -> GLReportRepository:
    return GLReportRepository(db)


def get_audit_log_repo(db: Session = Depends(get_db)) -> AccountingAuditLogRepository:
    return AccountingAuditLogRepository(db)


def get_journal_entry_service(db: Session = Depends(get_db)) -> JournalEntryService:
    return JournalEntryService(posting_engine=build_posting_engine(db))


def build_recurring_journal_service(db: Session) -> RecurringJournalService:
    """Assemble a ``RecurringJournalService`` from a raw ``Session``.

    Plain function (mirrors ``build_posting_engine``) so ``scheduler.py``'s
    APScheduler job — which runs outside any FastAPI request — can build
    one from its own ``SessionLocal()`` session.
    """
    return RecurringJournalService(
        db=db,
        template_repo=RecurringJournalTemplateRepository(db),
        line_repo=RecurringJournalTemplateLineRepository(db),
        instance_repo=RecurringJournalInstanceRepository(db),
        account_repo=AccountRepository(db),
        posting_engine=build_posting_engine(db),
    )


def get_recurring_journal_service(
    db: Session = Depends(get_db),
) -> RecurringJournalService:
    return build_recurring_journal_service(db)


def build_sales_customer_service(db: Session) -> CustomerService:
    """Assemble Sales' (Epic 7) own ``CustomerService`` from a raw ``Session``.

    Direct cross-module service construction — established precedent for
    this exists between ``modules.companies`` and ``modules.users_roles``
    (see ``ar_service.py`` module docstring). Used so Accounting's credit
    hold can call Sales' ALREADY-EXISTING ``update_credit(credit_status=...)``,
    which both updates the field ``CreditCheckService`` reads live to block
    order approval AND publishes Sales' own credit-hold events — the real,
    working enforcement path, not a duplicated one.
    """
    from modules.sales.repositories.customer import (
        CustomerAddressRepository,
        CustomerContactRepository,
        CustomerRepository,
    )
    from modules.sales.services.customer_service import CustomerService
    from modules.sales.services.sequence_service import SalesSequenceService

    return CustomerService(
        db=db,
        customer_repo=CustomerRepository(db),
        contact_repo=CustomerContactRepository(db),
        address_repo=CustomerAddressRepository(db),
        sequence_service=SalesSequenceService(db),
    )


def build_ar_service(
    db: Session, with_sales_sync: bool = True
) -> AccountsReceivableService:
    """Assemble an ``AccountsReceivableService`` from a raw ``Session``.

    Plain function (mirrors ``build_posting_engine``) so
    ``handlers/integration_handlers.py`` (event-bus callbacks, outside any
    FastAPI request) can build one from its own ``SessionLocal()`` session.

    ``with_sales_sync=False`` omits the Sales ``CustomerService`` dependency
    — used by test fixtures that don't need cross-module credit-hold sync.
    """
    return AccountsReceivableService(
        db=db,
        ledger_repo=CustomerLedgerRepository(db),
        transaction_repo=ARTransactionRepository(db),
        allocation_repo=ARPaymentAllocationRepository(db),
        credit_history_repo=CustomerCreditHistoryRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        posting_engine=build_posting_engine(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
        sales_customer_service=(
            build_sales_customer_service(db) if with_sales_sync else None
        ),
    )


def get_ar_service(db: Session = Depends(get_db)) -> AccountsReceivableService:
    return build_ar_service(db)


def build_ap_service(db: Session) -> AccountsPayableService:
    """Assemble an ``AccountsPayableService`` from a raw ``Session``.

    Plain function (mirrors ``build_ar_service``) so ``scheduler.py``'s
    APScheduler job can build one from its own ``SessionLocal()`` session.
    """
    return AccountsPayableService(
        db=db,
        ledger_repo=SupplierLedgerRepository(db),
        transaction_repo=APTransactionRepository(db),
        allocation_repo=APPaymentAllocationRepository(db),
        reconciliation_repo=SupplierStatementReconciliationRepository(db),
        reconciliation_item_repo=SupplierStatementReconciliationItemRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        posting_engine=build_posting_engine(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )


def get_ap_service(db: Session = Depends(get_db)) -> AccountsPayableService:
    return build_ap_service(db)


def build_bank_account_service(db: Session) -> BankAccountService:
    """Assemble a ``BankAccountService`` from a raw ``Session``."""
    return BankAccountService(
        db=db,
        bank_account_repo=BankAccountRepository(db),
        transaction_repo=BankTransactionRepository(db),
        cheque_repo=ChequeRepository(db),
        posting_engine=build_posting_engine(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )


def get_bank_account_service(db: Session = Depends(get_db)) -> BankAccountService:
    return build_bank_account_service(db)


def build_bank_reconciliation_service(db: Session) -> BankReconciliationService:
    """Assemble a ``BankReconciliationService`` from a raw ``Session``."""
    return BankReconciliationService(
        db=db,
        bank_account_repo=BankAccountRepository(db),
        transaction_repo=BankTransactionRepository(db),
        statement_line_repo=BankStatementLineRepository(db),
        reconciliation_repo=BankReconciliationRepository(db),
        match_repo=BankReconciliationMatchRepository(db),
        posting_engine=build_posting_engine(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )


def get_bank_reconciliation_service(
    db: Session = Depends(get_db),
) -> BankReconciliationService:
    return build_bank_reconciliation_service(db)


def build_cash_account_service(db: Session) -> CashAccountService:
    """Assemble a ``CashAccountService`` from a raw ``Session``."""
    return CashAccountService(
        db=db,
        cash_account_repo=CashAccountRepository(db),
        transaction_repo=CashTransactionRepository(db),
        voucher_repo=PettyCashVoucherRepository(db),
        reconciliation_repo=CashReconciliationRepository(db),
        posting_engine=build_posting_engine(db),
    )


def get_cash_account_service(db: Session = Depends(get_db)) -> CashAccountService:
    return build_cash_account_service(db)


def build_allocation_engine(db: Session) -> AllocationEngine:
    """Assemble an ``AllocationEngine`` from a raw ``Session``."""
    return AllocationEngine(
        db=db,
        payment_repo=PaymentRepository(db),
        allocation_line_repo=PaymentAllocationLineRepository(db),
        ar_transaction_repo=ARTransactionRepository(db),
        ap_transaction_repo=APTransactionRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        posting_engine=build_posting_engine(db),
    )


def get_allocation_engine(db: Session = Depends(get_db)) -> AllocationEngine:
    return build_allocation_engine(db)


def build_payment_service(db: Session) -> PaymentService:
    """Assemble a ``PaymentService`` from a raw ``Session``."""
    return PaymentService(
        db=db,
        payment_repo=PaymentRepository(db),
        allocation_line_repo=PaymentAllocationLineRepository(db),
        refund_repo=PaymentRefundRepository(db),
        ar_transaction_repo=ARTransactionRepository(db),
        ap_transaction_repo=APTransactionRepository(db),
        customer_ledger_repo=CustomerLedgerRepository(db),
        supplier_ledger_repo=SupplierLedgerRepository(db),
        bank_account_repo=BankAccountRepository(db),
        cash_account_repo=CashAccountRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        flag_service=AccountingFeatureFlagService(
            db=db, flag_repo=AccountingFeatureFlagRepository(db)
        ),
        allocation_engine=build_allocation_engine(db),
        posting_engine=build_posting_engine(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )


def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return build_payment_service(db)


def build_tax_calculator(db: Session) -> TaxCalculator:
    """Assemble a ``TaxCalculator`` from a raw ``Session``."""
    return TaxCalculator(
        db=db,
        tax_code_repo=TaxCodeRepository(db),
        tax_rate_repo=TaxRateRepository(db),
        tax_group_repo=TaxGroupRepository(db),
        tax_group_line_repo=TaxGroupLineRepository(db),
    )


def get_tax_calculator(db: Session = Depends(get_db)) -> TaxCalculator:
    return build_tax_calculator(db)


def build_tax_service(db: Session) -> TaxService:
    """Assemble a ``TaxService`` from a raw ``Session``."""
    return TaxService(
        db=db,
        tax_code_repo=TaxCodeRepository(db),
        tax_rate_repo=TaxRateRepository(db),
        tax_group_repo=TaxGroupRepository(db),
        tax_group_line_repo=TaxGroupLineRepository(db),
        payment_repo=PaymentRepository(db),
    )


def get_tax_service(db: Session = Depends(get_db)) -> TaxService:
    return build_tax_service(db)


def build_cost_center_service(db: Session) -> CostCenterService:
    """Assemble a ``CostCenterService`` from a raw ``Session``."""
    return CostCenterService(
        db=db,
        cost_center_repo=CostCenterRepository(db),
        department_repo=DepartmentRepository(db),
        project_repo=ProjectRepository(db),
    )


def get_cost_center_service(db: Session = Depends(get_db)) -> CostCenterService:
    return build_cost_center_service(db)


def build_currency_revaluation_service(db: Session) -> CurrencyRevaluationService:
    """Assemble a ``CurrencyRevaluationService`` from a raw ``Session``."""
    return CurrencyRevaluationService(
        db=db,
        customer_ledger_repo=CustomerLedgerRepository(db),
        supplier_ledger_repo=SupplierLedgerRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        fiscal_period_repo=FiscalPeriodRepository(db),
        run_repo=CurrencyRevaluationRunRepository(db),
        currency_service=CurrencyService(
            db=db,
            currency_repo=CurrencyRepository(db),
            exchange_rate_repo=ExchangeRateRepository(db),
        ),
        posting_engine=build_posting_engine(db),
    )


def get_currency_revaluation_service(
    db: Session = Depends(get_db),
) -> CurrencyRevaluationService:
    return build_currency_revaluation_service(db)


def build_financial_statement_service(db: Session) -> FinancialStatementService:
    """Assemble a ``FinancialStatementService`` from a raw ``Session``."""
    return FinancialStatementService(
        db=db,
        gl_report_repo=GLReportRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        currency_service=CurrencyService(
            db=db,
            currency_repo=CurrencyRepository(db),
            exchange_rate_repo=ExchangeRateRepository(db),
        ),
        fiscal_year_repo=FiscalYearRepository(db),
    )


def get_financial_statement_service(
    db: Session = Depends(get_db),
) -> FinancialStatementService:
    return build_financial_statement_service(db)


def build_report_service(db: Session) -> ReportService:
    """Assemble a ``ReportService`` from a raw ``Session``."""
    return ReportService(
        db=db,
        gl_report_repo=GLReportRepository(db),
        journal_repo=JournalEntryRepository(db),
        ar_service=build_ar_service(db, with_sales_sync=False),
        ap_service=build_ap_service(db),
        bank_service=build_bank_account_service(db),
        cash_service=build_cash_account_service(db),
    )


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    return build_report_service(db)


def build_kpi_service(db: Session) -> FinancialKPIService:
    """Assemble a ``FinancialKPIService`` from a raw ``Session``."""
    return FinancialKPIService(
        db=db,
        gl_report_repo=GLReportRepository(db),
        config_repo=AccountingConfigurationRepository(db),
        customer_ledger_repo=CustomerLedgerRepository(db),
        supplier_ledger_repo=SupplierLedgerRepository(db),
        tax_code_repo=TaxCodeRepository(db),
        fiscal_year_repo=FiscalYearRepository(db),
        fiscal_period_repo=FiscalPeriodRepository(db),
        financial_statements=build_financial_statement_service(db),
    )


def get_kpi_service(db: Session = Depends(get_db)) -> FinancialKPIService:
    return build_kpi_service(db)


def build_ai_service(db: Session) -> AIReadinessService:
    """Assemble an ``AIReadinessService`` from a raw ``Session`` — Phase 17."""
    return AIReadinessService(
        db=db,
        journal_entry_repo=JournalEntryRepository(db),
        fiscal_period_repo=FiscalPeriodRepository(db),
        financial_statement_service=build_financial_statement_service(db),
        anomaly_flag_repo=AccountingAnomalyFlagRepository(db),
    )


def get_ai_service(db: Session = Depends(get_db)) -> AIReadinessService:
    return build_ai_service(db)

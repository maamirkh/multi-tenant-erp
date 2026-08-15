"""Accounting module ORM models.

All models are imported here to ensure Alembic auto-discovery works correctly
when running ``alembic revision --autogenerate``.

Import order follows dependency order (parent before child tables).
"""

from modules.accounting.models.ai import AccountingAnomalyFlag
from modules.accounting.models.ap import (
    APPaymentAllocation,
    APTransaction,
    SupplierLedger,
    SupplierStatementReconciliation,
    SupplierStatementReconciliationItem,
)
from modules.accounting.models.ar import (
    ARPaymentAllocation,
    ARTransaction,
    CustomerCreditHistory,
    CustomerLedger,
)
from modules.accounting.models.banking import (
    BankAccount,
    BankReconciliation,
    BankReconciliationMatch,
    BankStatementLine,
    BankTransaction,
    Cheque,
)
from modules.accounting.models.cash import (
    CashAccount,
    CashReconciliation,
    CashTransaction,
    PettyCashVoucher,
)
from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.models.cost import CostCenter, Department, Project
from modules.accounting.models.currency import CurrencyRevaluationRun
from modules.accounting.models.feature_flag import AccountingFeatureFlag
from modules.accounting.models.fiscal import FiscalPeriod, FiscalYear, OpeningBalance
from modules.accounting.models.foundation import (
    AccountingConfiguration,
    AccountingSequence,
    Currency,
    ExchangeRate,
)
from modules.accounting.models.gl import (
    AccountingAuditLog,
    JournalApproval,
    JournalEntry,
    JournalLine,
)
from modules.accounting.models.payments import (
    Payment,
    PaymentAllocationLine,
    PaymentRefund,
)
from modules.accounting.models.recurring import (
    RecurringJournalInstance,
    RecurringJournalTemplate,
    RecurringJournalTemplateLine,
)
from modules.accounting.models.tax import TaxCode, TaxGroup, TaxGroupLine, TaxRate

__all__ = [
    "APPaymentAllocation",
    "APTransaction",
    "ARPaymentAllocation",
    "ARTransaction",
    "Account",
    "AccountGroup",
    "AccountingAnomalyFlag",
    "AccountingAuditLog",
    "AccountingConfiguration",
    "AccountingFeatureFlag",
    "AccountingSequence",
    "BankAccount",
    "BankReconciliation",
    "BankReconciliationMatch",
    "BankStatementLine",
    "BankTransaction",
    "CashAccount",
    "CashReconciliation",
    "CashTransaction",
    "Cheque",
    "CostCenter",
    "Currency",
    "CurrencyRevaluationRun",
    "CustomerCreditHistory",
    "CustomerLedger",
    "Department",
    "ExchangeRate",
    "FiscalPeriod",
    "FiscalYear",
    "JournalApproval",
    "JournalEntry",
    "JournalLine",
    "OpeningBalance",
    "Payment",
    "PaymentAllocationLine",
    "PaymentRefund",
    "PettyCashVoucher",
    "Project",
    "RecurringJournalInstance",
    "RecurringJournalTemplate",
    "RecurringJournalTemplateLine",
    "SupplierLedger",
    "SupplierStatementReconciliation",
    "SupplierStatementReconciliationItem",
    "TaxCode",
    "TaxGroup",
    "TaxGroupLine",
    "TaxRate",
]

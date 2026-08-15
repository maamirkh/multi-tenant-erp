"""Accounting module constants.

Permission codes follow the pattern ``accounting.<resource>.<action>``
as defined in plan.md §Security Strategy.

Feature flag keys follow the pattern ``accounting.<capability>.enabled``
as defined in quickstart.md §Feature Flags.

All definitions are frozen datastructures to prevent accidental mutation.

Spec ref: specs/008-accounting-finance/spec.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

# ---------------------------------------------------------------------------
# Permission Definitions (plan.md §Security Strategy)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccountingPermissionDefinition:
    """Immutable definition of an accounting module permission."""

    code: str
    label: str
    module: str
    action: str
    description: str


ACCOUNTING_PERMISSIONS: Final[tuple[AccountingPermissionDefinition, ...]] = (
    # --- Chart of Accounts permissions ---
    AccountingPermissionDefinition(
        "accounting.accounts.create",
        "Create Accounts",
        "accounting",
        "accounts.create",
        "Create new chart of accounts entries",
    ),
    AccountingPermissionDefinition(
        "accounting.accounts.read",
        "View Accounts",
        "accounting",
        "accounts.read",
        "View chart of accounts",
    ),
    AccountingPermissionDefinition(
        "accounting.accounts.update",
        "Edit Accounts",
        "accounting",
        "accounts.update",
        "Update chart of accounts entries",
    ),
    AccountingPermissionDefinition(
        "accounting.accounts.deactivate",
        "Deactivate Accounts",
        "accounting",
        "accounts.deactivate",
        "Deactivate accounts with no current-year activity",
    ),
    AccountingPermissionDefinition(
        "accounting.accounts.import",
        "Import Accounts",
        "accounting",
        "accounts.import",
        "Bulk import chart of accounts via CSV",
    ),
    AccountingPermissionDefinition(
        "accounting.systemaccounts.configure",
        "Configure System Accounts",
        "accounting",
        "systemaccounts.configure",
        "Designate AR, AP, Bank, Cash, Tax, Retained Earnings control accounts",
    ),
    # --- Fiscal Calendar permissions ---
    AccountingPermissionDefinition(
        "accounting.fiscalyear.create",
        "Create Fiscal Years",
        "accounting",
        "fiscalyear.create",
        "Create and configure fiscal years",
    ),
    AccountingPermissionDefinition(
        "accounting.fiscalyear.close",
        "Close Fiscal Year",
        "accounting",
        "fiscalyear.close",
        "Execute year-end close process",
    ),
    AccountingPermissionDefinition(
        "accounting.period.lock",
        "Lock Period",
        "accounting",
        "period.lock",
        "Lock a fiscal period to prevent postings",
    ),
    AccountingPermissionDefinition(
        "accounting.period.unlock",
        "Unlock Period",
        "accounting",
        "period.unlock",
        "Unlock a locked fiscal period (Controller/CFO only)",
    ),
    # --- Journal / GL permissions ---
    AccountingPermissionDefinition(
        "accounting.journal.create",
        "Create Journals",
        "accounting",
        "journal.create",
        "Create manual journal entries",
    ),
    AccountingPermissionDefinition(
        "accounting.journal.approve",
        "Approve Journals",
        "accounting",
        "journal.approve",
        "Approve journal entries pending approval",
    ),
    AccountingPermissionDefinition(
        "accounting.journal.post",
        "Post Journals",
        "accounting",
        "journal.post",
        "Post approved journal entries to the GL",
    ),
    AccountingPermissionDefinition(
        "accounting.journal.reverse",
        "Reverse Journals",
        "accounting",
        "journal.reverse",
        "Reverse a posted journal entry",
    ),
    AccountingPermissionDefinition(
        "accounting.reports.gl.read",
        "View General Ledger",
        "accounting",
        "reports.gl.read",
        "View the general ledger report",
    ),
    # --- AR permissions ---
    AccountingPermissionDefinition(
        "accounting.ar.writeoff",
        "Write Off Receivables",
        "accounting",
        "ar.writeoff",
        "Write off uncollectable receivables",
    ),
    AccountingPermissionDefinition(
        "accounting.ar.credithold.place",
        "Place Credit Hold",
        "accounting",
        "ar.credithold.place",
        "Place a customer on credit hold",
    ),
    AccountingPermissionDefinition(
        "accounting.ar.credithold.release",
        "Release Credit Hold",
        "accounting",
        "ar.credithold.release",
        "Release a customer credit hold",
    ),
    # --- AP permissions ---
    AccountingPermissionDefinition(
        "accounting.ap.reconcile",
        "Reconcile Supplier Statements",
        "accounting",
        "ap.reconcile",
        "Reconcile supplier statements against the AP ledger",
    ),
    # --- Payment permissions ---
    AccountingPermissionDefinition(
        "accounting.payment.create",
        "Create Payments",
        "accounting",
        "payment.create",
        "Record customer receipts and supplier disbursements",
    ),
    AccountingPermissionDefinition(
        "accounting.payment.approve",
        "Approve Payments",
        "accounting",
        "payment.approve",
        "Approve payments pending authorization",
    ),
    # --- Banking permissions ---
    AccountingPermissionDefinition(
        "accounting.bank.reconcile",
        "Reconcile Bank Accounts",
        "accounting",
        "bank.reconcile",
        "Perform bank reconciliation",
    ),
    # --- Tax permissions ---
    AccountingPermissionDefinition(
        "accounting.tax.configure",
        "Configure Tax",
        "accounting",
        "tax.configure",
        "Configure tax codes, rates, and groups",
    ),
    # --- Reporting permissions ---
    AccountingPermissionDefinition(
        "accounting.reports.view",
        "View Financial Reports",
        "accounting",
        "reports.view",
        "View financial statements and management reports",
    ),
    AccountingPermissionDefinition(
        "accounting.reports.export",
        "Export Financial Reports",
        "accounting",
        "reports.export",
        "Export financial statements to PDF/Excel",
    ),
    # --- Settings permissions ---
    AccountingPermissionDefinition(
        "accounting.settings.read",
        "View Accounting Settings",
        "accounting",
        "settings.read",
        "View accounting module configuration",
    ),
    AccountingPermissionDefinition(
        "accounting.settings.update",
        "Edit Accounting Settings",
        "accounting",
        "settings.update",
        "Update accounting configuration, currencies, exchange rates",
    ),
)

ACCOUNTING_PERMISSION_BY_CODE: Final[dict[str, AccountingPermissionDefinition]] = {
    p.code: p for p in ACCOUNTING_PERMISSIONS
}


# ---------------------------------------------------------------------------
# Feature Flag Keys (quickstart.md §Feature Flags)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureFlagDefinition:
    """Immutable definition of a feature flag."""

    key: str
    label: str
    description: str
    default_enabled: bool


ACCOUNTING_FEATURE_FLAGS: Final[tuple[FeatureFlagDefinition, ...]] = (
    FeatureFlagDefinition(
        key="accounting.multicurrency.enabled",
        label="Multi-Currency Accounting",
        description="Enable multi-currency operations and exchange rate revaluation",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="accounting.costcenters.enabled",
        label="Cost Center Accounting",
        description="Enable cost center, department, and project dimensions on postings",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="accounting.approvalworkflow.enabled",
        label="Journal Approval Workflow",
        description="Require approval for journal/payment entries above threshold",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="accounting.taxwithholding.enabled",
        label="Withholding Tax",
        description="Enable WHT calculation on supplier payments",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="accounting.ai.enabled",
        label="AI Financial Assistant",
        description="Enable AI-powered financial insights (future)",
        default_enabled=False,
    ),
    FeatureFlagDefinition(
        key="accounting.bankreconciliation.enabled",
        label="Bank Reconciliation",
        description="Enable the bank reconciliation module",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="accounting.recurringjournals.enabled",
        label="Recurring Journals",
        description="Enable recurring journal templates and scheduled execution",
        default_enabled=True,
    ),
    FeatureFlagDefinition(
        key="accounting.bulkimport.enabled",
        label="Bulk COA Import",
        description="Enable bulk chart-of-accounts CSV import",
        default_enabled=True,
    ),
)

ACCOUNTING_FLAG_BY_KEY: Final[dict[str, FeatureFlagDefinition]] = {
    f.key: f for f in ACCOUNTING_FEATURE_FLAGS
}

# Set of keys that default to enabled — used for seeding
ACCOUNTING_DEFAULT_ENABLED_FLAGS: Final[frozenset[str]] = frozenset(
    f.key for f in ACCOUNTING_FEATURE_FLAGS if f.default_enabled
)


# ---------------------------------------------------------------------------
# Enums (data-model.md §2 Aggregate Roots, §8 State Machines)
# ---------------------------------------------------------------------------


class AccountType(str, Enum):
    """Top-level chart-of-accounts classification. Spec ref: data-model.md §2.1."""

    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class AccountGroupType(str, Enum):
    """Classification of an account group — mirrors AccountType for grouping."""

    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class JournalEntryStatus(str, Enum):
    """JournalEntry lifecycle state. Spec ref: data-model.md §8.1."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    POSTED = "POSTED"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"


class JournalType(str, Enum):
    """Journal entry classification. Spec ref: data-model.md §2.3."""

    STANDARD = "STANDARD"
    ADJUSTING = "ADJUSTING"
    REVERSING = "REVERSING"
    RECURRING_INSTANCE = "RECURRING_INSTANCE"
    OPENING_BALANCE = "OPENING_BALANCE"
    CLOSING = "CLOSING"
    AUTOMATED = "AUTOMATED"


class PostingSource(str, Enum):
    """Origin of a posted journal entry. Spec ref: data-model.md §2.3."""

    MANUAL = "MANUAL"
    SALES = "SALES"
    PURCHASE = "PURCHASE"
    INVENTORY = "INVENTORY"
    BANK = "BANK"
    CASH = "CASH"
    PAYMENT = "PAYMENT"
    RECURRING = "RECURRING"
    SYSTEM = "SYSTEM"


class FiscalYearStatus(str, Enum):
    """FiscalYear lifecycle state. Spec ref: data-model.md §2.2."""

    SETUP = "SETUP"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class FiscalPeriodStatus(str, Enum):
    """FiscalPeriod lifecycle state. Spec ref: data-model.md §8.2."""

    OPEN = "OPEN"
    LOCKED = "LOCKED"
    CLOSED = "CLOSED"


class ARTransactionType(str, Enum):
    """AR transaction classification. Spec ref: data-model.md §2.4."""

    INVOICE = "INVOICE"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"
    PAYMENT = "PAYMENT"
    ADVANCE = "ADVANCE"
    ADJUSTMENT = "ADJUSTMENT"
    WRITE_OFF = "WRITE_OFF"


class ARTransactionStatus(str, Enum):
    """AR transaction status. Spec ref: data-model.md §8.4."""

    OPEN = "OPEN"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    DISPUTED = "DISPUTED"
    WRITTEN_OFF = "WRITTEN_OFF"


class APTransactionType(str, Enum):
    """AP transaction classification — mirrors ARTransactionType. Spec ref: data-model.md §2.5."""

    BILL = "BILL"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"
    PAYMENT = "PAYMENT"
    ADVANCE = "ADVANCE"
    ADJUSTMENT = "ADJUSTMENT"


class APTransactionStatus(str, Enum):
    """AP transaction status — mirrors ARTransactionStatus."""

    OPEN = "OPEN"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    DISPUTED = "DISPUTED"


class PaymentType(str, Enum):
    """Payment direction/purpose classification. Spec ref: data-model.md §2.8."""

    CUSTOMER_RECEIPT = "CUSTOMER_RECEIPT"
    SUPPLIER_DISBURSEMENT = "SUPPLIER_DISBURSEMENT"
    ADVANCE_RECEIPT = "ADVANCE_RECEIPT"
    ADVANCE_PAYMENT = "ADVANCE_PAYMENT"


class PaymentMethod(str, Enum):
    """Payment method. Spec ref: data-model.md §2.8."""

    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    CARD = "CARD"
    ONLINE = "ONLINE"


class PaymentStatus(str, Enum):
    """Payment lifecycle state. Spec ref: data-model.md §2.8."""

    DRAFT = "DRAFT"
    POSTED = "POSTED"
    ALLOCATED = "ALLOCATED"
    CANCELLED = "CANCELLED"


class PaymentPartyType(str, Enum):
    """Payment counterparty classification. Spec ref: data-model.md §2.8."""

    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"


class SupplierReconciliationStatus(str, Enum):
    """SupplierStatementReconciliation session state. Spec ref: tasks.md T159."""

    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ReconciliationMatchStatus(str, Enum):
    """SupplierStatementReconciliationItem match outcome. Spec ref: tasks.md T160."""

    MATCHED = "MATCHED"
    UNMATCHED_GL = "UNMATCHED_GL"
    UNMATCHED_STATEMENT = "UNMATCHED_STATEMENT"
    DISPUTED = "DISPUTED"


class BankTransactionType(str, Enum):
    """BankTransaction classification. Spec ref: tasks.md T176."""

    RECEIPT = "RECEIPT"
    PAYMENT = "PAYMENT"
    TRANSFER = "TRANSFER"
    BANK_CHARGE = "BANK_CHARGE"


class BankReconciliationStatus(str, Enum):
    """BankReconciliation session state. Spec ref: data-model.md §8.3."""

    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    LOCKED = "LOCKED"


class BankReconciliationMatchType(str, Enum):
    """BankReconciliationMatch origin. Spec ref: tasks.md T179."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class ChequeStatus(str, Enum):
    """Cheque lifecycle state. Spec ref: data-model.md §8.5."""

    ISSUED = "ISSUED"
    PRESENTED = "PRESENTED"
    CLEARED = "CLEARED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class CashTransactionType(str, Enum):
    """CashTransaction classification. Spec ref: tasks.md T193."""

    RECEIPT = "RECEIPT"
    PAYMENT = "PAYMENT"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class CashReconciliationStatus(str, Enum):
    """CashReconciliation session state. Spec ref: tasks.md T195.

    Simpler than ``BankReconciliationStatus`` — cash reconciliation is a
    single-shot operation (record count + post difference) rather than a
    multi-step matching session, so there is no IN_PROGRESS state.
    """

    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class TaxType(str, Enum):
    """Tax code classification. Spec ref: data-model.md §2.9."""

    SALES_TAX = "SALES_TAX"
    VAT = "VAT"
    GST = "GST"
    WITHHOLDING = "WITHHOLDING"
    COMPOUND = "COMPOUND"
    EXEMPT = "EXEMPT"
    ZERO_RATED = "ZERO_RATED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class TaxApplicability(str, Enum):
    """Which transaction side a TaxCode/TaxGroup applies to. Spec ref: spec.md §23.3."""

    SALES = "SALES"
    PURCHASES = "PURCHASES"
    BOTH = "BOTH"


class RoundingRule(str, Enum):
    """Decimal rounding mode applied to a calculated tax amount.
    Spec ref: spec.md §23.3 ("Rounding rule").
    """

    HALF_UP = "HALF_UP"
    HALF_EVEN = "HALF_EVEN"
    DOWN = "DOWN"
    UP = "UP"


class CreditStatus(str, Enum):
    """Customer credit status. Spec ref: data-model.md §8.6."""

    GOOD = "GOOD"
    WARNING = "WARNING"
    EXCEEDED = "EXCEEDED"
    HOLD = "HOLD"


class ApprovalStatus(str, Enum):
    """JournalApproval decision. Spec ref: data-model.md §2.3 JournalApproval."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExchangeRateType(str, Enum):
    """Exchange rate quotation type. Spec ref: data-model.md §2 ExchangeRate."""

    SPOT = "SPOT"
    AVERAGE = "AVERAGE"
    CLOSING = "CLOSING"
    HISTORICAL = "HISTORICAL"


class RecurringFrequency(str, Enum):
    """Recurring journal template schedule frequency. Spec ref: spec.md §15.4."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"


class RecurringInstanceStatus(str, Enum):
    """RecurringJournalInstance execution outcome. Spec ref: tasks.md T117."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class CustomerCreditHistoryEventType(str, Enum):
    """CustomerCreditHistory audit event type. Spec ref: tasks.md T135."""

    LIMIT_CHANGED = "LIMIT_CHANGED"
    HOLD_PLACED = "HOLD_PLACED"
    HOLD_RELEASED = "HOLD_RELEASED"
    STATUS_CHANGED = "STATUS_CHANGED"


class AgingBucket(str, Enum):
    """AR/AP aging bucket. Spec ref: spec.md §18.3."""

    CURRENT = "CURRENT"
    DAYS_1_30 = "DAYS_1_30"
    DAYS_31_60 = "DAYS_31_60"
    DAYS_61_90 = "DAYS_61_90"
    DAYS_91_120 = "DAYS_91_120"
    DAYS_120_PLUS = "DAYS_120_PLUS"


# ---------------------------------------------------------------------------
# Sequence type identifiers (used by AccountingSequenceService)
# ---------------------------------------------------------------------------

SEQUENCE_TYPES: Final[tuple[str, ...]] = ("JOURNAL",)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MODULE_NAME: Final[str] = "accounting"
MODULE_VERSION: Final[str] = "1.0.0"
SPEC_VERSION: Final[str] = "1.0.0"

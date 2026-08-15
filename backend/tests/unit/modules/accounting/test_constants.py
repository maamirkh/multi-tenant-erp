"""Unit tests for accounting module constants.

Tests:
  - Permission codes are unique and follow the accounting.* convention
  - Feature flag keys are unique and follow the accounting.* convention
  - Lookup dicts contain all entries
  - Default enabled flag set is correct
  - Enum values match spec.md / data-model.md definitions

Spec ref: specs/008-accounting-finance/tasks.md T045
"""

from __future__ import annotations

from modules.accounting.constants import (
    ACCOUNTING_DEFAULT_ENABLED_FLAGS,
    ACCOUNTING_FEATURE_FLAGS,
    ACCOUNTING_FLAG_BY_KEY,
    ACCOUNTING_PERMISSION_BY_CODE,
    ACCOUNTING_PERMISSIONS,
    MODULE_NAME,
    MODULE_VERSION,
    SEQUENCE_TYPES,
    AccountType,
    ARTransactionStatus,
    ARTransactionType,
    BankReconciliationStatus,
    ChequeStatus,
    CreditStatus,
    FiscalPeriodStatus,
    FiscalYearStatus,
    JournalEntryStatus,
    JournalType,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    PostingSource,
    TaxType,
)


class TestAccountingPermissions:
    """Test permission constant integrity."""

    def test_permission_codes_are_unique(self) -> None:
        codes = [p.code for p in ACCOUNTING_PERMISSIONS]
        assert len(codes) == len(
            set(codes)
        ), f"Duplicate codes: {[c for c in codes if codes.count(c) > 1]}"

    def test_all_permissions_follow_naming_convention(self) -> None:
        for p in ACCOUNTING_PERMISSIONS:
            assert p.code.startswith(
                "accounting."
            ), f"Permission '{p.code}' does not start with 'accounting.'"

    def test_all_permissions_have_module_accounting(self) -> None:
        for p in ACCOUNTING_PERMISSIONS:
            assert (
                p.module == "accounting"
            ), f"Permission '{p.code}' has module='{p.module}'"

    def test_lookup_dict_contains_all_permissions(self) -> None:
        assert len(ACCOUNTING_PERMISSION_BY_CODE) == len(ACCOUNTING_PERMISSIONS)
        for p in ACCOUNTING_PERMISSIONS:
            assert p.code in ACCOUNTING_PERMISSION_BY_CODE

    def test_at_least_20_permissions_defined(self) -> None:
        """plan.md §Security Strategy requires 20+ accounting permissions."""
        assert len(ACCOUNTING_PERMISSIONS) >= 20

    def test_all_permissions_have_required_fields(self) -> None:
        for p in ACCOUNTING_PERMISSIONS:
            assert p.code, "Empty code"
            assert p.label, "Empty label"
            assert p.action, "Empty action"
            assert p.description, "Empty description"


class TestAccountingFeatureFlags:
    """Test feature flag constant integrity."""

    def test_flag_keys_are_unique(self) -> None:
        keys = [f.key for f in ACCOUNTING_FEATURE_FLAGS]
        assert len(keys) == len(
            set(keys)
        ), f"Duplicate keys: {[k for k in keys if keys.count(k) > 1]}"

    def test_all_flags_follow_naming_convention(self) -> None:
        for f in ACCOUNTING_FEATURE_FLAGS:
            assert f.key.startswith(
                "accounting."
            ), f"Flag '{f.key}' does not start with 'accounting.'"

    def test_lookup_dict_contains_all_flags(self) -> None:
        assert len(ACCOUNTING_FLAG_BY_KEY) == len(ACCOUNTING_FEATURE_FLAGS)
        for f in ACCOUNTING_FEATURE_FLAGS:
            assert f.key in ACCOUNTING_FLAG_BY_KEY

    def test_8_feature_flags_defined(self) -> None:
        """quickstart.md §Feature Flags lists exactly 8 accounting flags."""
        assert len(ACCOUNTING_FEATURE_FLAGS) == 8

    def test_default_enabled_flags_subset(self) -> None:
        all_keys = {f.key for f in ACCOUNTING_FEATURE_FLAGS}
        assert ACCOUNTING_DEFAULT_ENABLED_FLAGS.issubset(all_keys)

    def test_default_enabled_flags_match(self) -> None:
        expected = {f.key for f in ACCOUNTING_FEATURE_FLAGS if f.default_enabled}
        assert ACCOUNTING_DEFAULT_ENABLED_FLAGS == expected

    def test_expected_default_enabled_flags(self) -> None:
        """Per quickstart.md: bankreconciliation, recurringjournals, bulkimport
        default to True; all others default to False."""
        expected = {
            "accounting.bankreconciliation.enabled",
            "accounting.recurringjournals.enabled",
            "accounting.bulkimport.enabled",
        }
        assert ACCOUNTING_DEFAULT_ENABLED_FLAGS == expected

    def test_all_flags_have_required_fields(self) -> None:
        for f in ACCOUNTING_FEATURE_FLAGS:
            assert f.key, "Empty key"
            assert f.label, "Empty label"
            assert f.description, "Empty description"


class TestSequenceTypes:
    """Test sequence type constants."""

    def test_journal_sequence_type_defined(self) -> None:
        assert "JOURNAL" in SEQUENCE_TYPES


class TestEnums:
    """Test enum definitions match spec.md / data-model.md."""

    def test_account_type_values(self) -> None:
        assert {e.value for e in AccountType} == {
            "ASSET",
            "LIABILITY",
            "EQUITY",
            "REVENUE",
            "EXPENSE",
        }

    def test_journal_entry_status_values(self) -> None:
        assert {e.value for e in JournalEntryStatus} == {
            "DRAFT",
            "SUBMITTED",
            "APPROVED",
            "POSTED",
            "REJECTED",
            "REVERSED",
        }

    def test_journal_type_values(self) -> None:
        assert {e.value for e in JournalType} == {
            "STANDARD",
            "ADJUSTING",
            "REVERSING",
            "RECURRING_INSTANCE",
            "OPENING_BALANCE",
            "CLOSING",
            "AUTOMATED",
        }

    def test_posting_source_values(self) -> None:
        assert {e.value for e in PostingSource} == {
            "MANUAL",
            "SALES",
            "PURCHASE",
            "INVENTORY",
            "BANK",
            "CASH",
            "PAYMENT",
            "RECURRING",
            "SYSTEM",
        }

    def test_fiscal_year_status_values(self) -> None:
        assert {e.value for e in FiscalYearStatus} == {"SETUP", "OPEN", "CLOSED"}

    def test_fiscal_period_status_values(self) -> None:
        assert {e.value for e in FiscalPeriodStatus} == {"OPEN", "LOCKED", "CLOSED"}

    def test_ar_transaction_type_values(self) -> None:
        assert {e.value for e in ARTransactionType} == {
            "INVOICE",
            "CREDIT_NOTE",
            "DEBIT_NOTE",
            "PAYMENT",
            "ADVANCE",
            "ADJUSTMENT",
            "WRITE_OFF",
        }

    def test_ar_transaction_status_values(self) -> None:
        assert {e.value for e in ARTransactionStatus} == {
            "OPEN",
            "PARTIALLY_PAID",
            "PAID",
            "OVERDUE",
            "DISPUTED",
            "WRITTEN_OFF",
        }

    def test_payment_type_values(self) -> None:
        assert {e.value for e in PaymentType} == {
            "CUSTOMER_RECEIPT",
            "SUPPLIER_DISBURSEMENT",
            "ADVANCE_RECEIPT",
            "ADVANCE_PAYMENT",
        }

    def test_payment_method_values(self) -> None:
        assert {e.value for e in PaymentMethod} == {
            "CASH",
            "BANK_TRANSFER",
            "CHEQUE",
            "CARD",
            "ONLINE",
        }

    def test_payment_status_values(self) -> None:
        assert {e.value for e in PaymentStatus} == {
            "DRAFT",
            "POSTED",
            "ALLOCATED",
            "CANCELLED",
        }

    def test_bank_reconciliation_status_values(self) -> None:
        assert {e.value for e in BankReconciliationStatus} == {
            "DRAFT",
            "IN_PROGRESS",
            "COMPLETED",
            "LOCKED",
        }

    def test_cheque_status_values(self) -> None:
        assert {e.value for e in ChequeStatus} == {
            "ISSUED",
            "PRESENTED",
            "CLEARED",
            "CANCELLED",
            "STALE",
        }

    def test_tax_type_values(self) -> None:
        assert {e.value for e in TaxType} == {
            "SALES_TAX",
            "VAT",
            "GST",
            "WITHHOLDING",
            "COMPOUND",
            "EXEMPT",
            "ZERO_RATED",
            "OUT_OF_SCOPE",
        }

    def test_credit_status_values(self) -> None:
        assert {e.value for e in CreditStatus} == {
            "GOOD",
            "WARNING",
            "EXCEEDED",
            "HOLD",
        }


class TestModuleConstants:
    """Test module-level constants."""

    def test_module_name(self) -> None:
        assert MODULE_NAME == "accounting"

    def test_module_version(self) -> None:
        assert MODULE_VERSION == "1.0.0"

"""Accounting module domain exceptions.

All exceptions inherit from ``ApplicationException`` via the module-level
``AccountingException`` base so the global FastAPI exception handler converts
them to typed ``ErrorResponse`` JSON automatically (Constitution §21).

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure Python.

Phase 1 introduced ``ExchangeRateNotFoundError``. Phase 2 (Chart of Accounts)
adds account/COA-specific errors. Later phases add ``PostingValidationError``,
``PeriodLockedError``, and others as those domains are implemented.
"""

from __future__ import annotations

from core.exceptions.base import (
    ApplicationException,
    ConflictException,
    NotFoundException,
)


class AccountingException(ApplicationException):
    """Base exception for all Accounting module errors."""

    def __init__(
        self,
        message: str,
        code: str = "ACCOUNTING_ERROR",
        details: dict[str, object] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(
            message=message, code=code, details=details, http_status=http_status
        )


class ExchangeRateNotFoundError(NotFoundException):
    """Raised when no exchange rate can be resolved for a currency pair/date.

    Per research.md Decision 8, this is raised only after both the exact-date
    lookup and the 7-day fallback lookback fail to find a rate.
    """

    def __init__(
        self,
        from_currency_code: str,
        to_currency_code: str,
        rate_date: str,
    ) -> None:
        super().__init__(
            message=(
                f"No exchange rate found for {from_currency_code}->"
                f"{to_currency_code} on or before {rate_date}."
            ),
            details={
                "from_currency_code": from_currency_code,
                "to_currency_code": to_currency_code,
                "rate_date": rate_date,
            },
        )


# ── Chart of Accounts (Phase 2) ─────────────────────────────────────────────


class AccountNotFoundError(NotFoundException):
    """Raised when a referenced Account does not exist for this company."""

    def __init__(
        self, account_id: str | None = None, account_code: str | None = None
    ) -> None:
        identifier = account_code or account_id or "?"
        super().__init__(
            message=f"Account '{identifier}' not found.",
            details={"account_id": account_id, "account_code": account_code},
        )


class AccountGroupNotFoundError(NotFoundException):
    """Raised when a referenced AccountGroup does not exist for this company."""

    def __init__(self, group_id: str | None = None) -> None:
        super().__init__(
            message=f"Account group '{group_id}' not found.",
            details={"account_group_id": group_id},
        )


class DuplicateAccountCodeError(ConflictException):
    """Raised when creating/updating an account with a code already in use.

    Spec ref: spec.md §13.5 — account codes are unique within a company.
    """

    def __init__(self, account_code: str) -> None:
        super().__init__(
            message=f"Account code '{account_code}' already exists for this company.",
            details={"account_code": account_code},
        )


class NonLeafPostingError(AccountingException):
    """Raised when a posting attempt targets a non-leaf (parent/group) account.

    Spec ref: spec.md FR-008 — only leaf accounts accept GL postings.
    """

    def __init__(self, account_code: str) -> None:
        super().__init__(
            message=f"Account '{account_code}' is not a leaf account and cannot accept postings.",
            code="ACCOUNT_NOT_LEAF",
            details={"account_code": account_code},
            http_status=422,
        )


class AccountDeactivationBlockedError(AccountingException):
    """Raised when an account cannot be deactivated.

    Two blocking conditions (spec.md §13.6, plan.md Phase 2 acceptance criteria):
      - The account has active child accounts.
      - The account has GL activity in the current open fiscal year.
    """

    def __init__(self, account_code: str, reason: str) -> None:
        super().__init__(
            message=f"Cannot deactivate account '{account_code}': {reason}",
            code="ACCOUNT_DEACTIVATION_BLOCKED",
            details={"account_code": account_code, "reason": reason},
            http_status=422,
        )


class InvalidSystemAccountTypeError(AccountingException):
    """Raised when a system account is configured with an incompatible account type.

    E.g. designating an EXPENSE-type account as the AR control account.
    Spec ref: plan.md Phase 2 acceptance criteria — "System account
    configuration validated: AR/AP/Bank/Cash/Retained Earnings must be
    correctly typed accounts".
    """

    def __init__(
        self, role: str, account_code: str, expected_type: str, actual_type: str
    ) -> None:
        super().__init__(
            message=(
                f"Cannot set '{account_code}' as the {role} account: "
                f"expected type {expected_type}, got {actual_type}."
            ),
            code="INVALID_SYSTEM_ACCOUNT_TYPE",
            details={
                "role": role,
                "account_code": account_code,
                "expected_type": expected_type,
                "actual_type": actual_type,
            },
            http_status=422,
        )


# ── Fiscal Calendar (Phase 3) ───────────────────────────────────────────────


class FiscalYearNotFoundError(NotFoundException):
    """Raised when a referenced FiscalYear does not exist for this company."""

    def __init__(
        self, fiscal_year_id: str | None = None, fiscal_year_name: str | None = None
    ) -> None:
        identifier = fiscal_year_name or fiscal_year_id or "?"
        super().__init__(
            message=f"Fiscal year '{identifier}' not found.",
            details={
                "fiscal_year_id": fiscal_year_id,
                "fiscal_year_name": fiscal_year_name,
            },
        )


class DuplicateFiscalYearError(ConflictException):
    """Raised when creating a fiscal year with a name already in use for this company."""

    def __init__(self, fiscal_year_name: str) -> None:
        super().__init__(
            message=f"Fiscal year '{fiscal_year_name}' already exists for this company.",
            details={"fiscal_year_name": fiscal_year_name},
        )


class FiscalPeriodNotFoundError(NotFoundException):
    """Raised when a referenced FiscalPeriod does not exist for this company."""

    def __init__(self, fiscal_period_id: str | None = None) -> None:
        super().__init__(
            message=f"Fiscal period '{fiscal_period_id}' not found.",
            details={"fiscal_period_id": fiscal_period_id},
        )


class InvalidFiscalPeriodTransitionError(AccountingException):
    """Raised when a FiscalPeriod status transition is not permitted.

    Valid transitions (spec.md §16.2, data-model.md §2.2):
      OPEN -> LOCKED, LOCKED -> OPEN, LOCKED -> CLOSED (year-end close only).
    CLOSED is terminal — no outgoing transition is ever valid.
    """

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            message=(
                f"Cannot transition fiscal period from {current_status} to "
                f"{target_status}."
            ),
            code="INVALID_PERIOD_TRANSITION",
            details={"current_status": current_status, "target_status": target_status},
            http_status=422,
        )


class PeriodLockedError(AccountingException):
    """Raised when a posting is attempted against a LOCKED/CLOSED fiscal period.

    This is the exact validation the PostingEngine (Phase 4, spec.md §14
    Step 3) will call before allowing any journal to post — implemented now
    against ``FiscalPeriodRepository`` since it depends only on Phase 3 data.
    """

    def __init__(self, posting_date: str, period_status: str | None = None) -> None:
        reason = (
            f"period status is {period_status}"
            if period_status is not None
            else "no fiscal period is defined for this date"
        )
        super().__init__(
            message=f"Period is locked for posting date {posting_date} ({reason}).",
            code="PERIOD_LOCKED",
            details={"posting_date": posting_date, "period_status": period_status},
            http_status=422,
        )


class OpeningBalanceImbalancedError(AccountingException):
    """Raised when a batch of opening balances does not sum debit == credit.

    Spec ref: spec.md §16.3 — "The system validates that total opening
    debits equal total opening credits."
    """

    def __init__(self, total_debit: str, total_credit: str) -> None:
        super().__init__(
            message=(
                f"Opening balances do not balance: total debit {total_debit} != "
                f"total credit {total_credit}."
            ),
            code="OPENING_BALANCE_IMBALANCED",
            details={"total_debit": total_debit, "total_credit": total_credit},
            http_status=422,
        )


class PostingValidationError(AccountingException):
    """Raised by ``PostingEngine`` when any of its validation steps fail.

    Spec ref: spec.md §15.3 Entry Validation Rules; tasks.md T093 Steps 1-5.
    The ``message`` passed in must match the exact wording tasks.md
    specifies for each step (e.g. "Journal must balance") since it is
    surfaced directly to the API client and asserted on in tests.
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message=message,
            code="POSTING_VALIDATION_ERROR",
            details=details,
            http_status=422,
        )


class JournalEntryNotFoundError(NotFoundException):
    """Raised when a referenced JournalEntry does not exist for this company."""

    def __init__(
        self, journal_entry_id: str | None = None, journal_number: str | None = None
    ) -> None:
        identifier = journal_number or journal_entry_id or "?"
        super().__init__(
            message=f"Journal entry '{identifier}' not found.",
            details={
                "journal_entry_id": journal_entry_id,
                "journal_number": journal_number,
            },
        )


class InvalidJournalStateTransitionError(AccountingException):
    """Raised when a JournalEntry status transition is not permitted.

    Spec ref: spec.md §15.2 Journal Entry Lifecycle; tasks.md T094.
    """

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            message=(
                f"Cannot transition journal entry from {current_status} to "
                f"{target_status}."
            ),
            code="INVALID_JOURNAL_TRANSITION",
            details={"current_status": current_status, "target_status": target_status},
            http_status=422,
        )


class SelfApprovalNotAllowedError(AccountingException):
    """Raised when a journal's creator attempts to approve their own entry.

    Plan ref: plan.md Phase 4 Acceptance Criteria — "Self-approval rejected:
    user who created journal cannot be the sole approver."
    """

    def __init__(self, journal_number: str | None) -> None:
        super().__init__(
            message=(
                f"Journal entry '{journal_number or '?'}' cannot be approved by "
                "its own creator."
            ),
            code="SELF_APPROVAL_NOT_ALLOWED",
            details={"journal_number": journal_number},
            http_status=422,
        )


class ApprovalPermissionDeniedError(AccountingException):
    """Raised when the acting user lacks the required accounting approval
    permission (Phase 14 SoD — spec.md §33 Permission Matrix, tasks.md T276).
    """

    def __init__(self, permission_code: str) -> None:
        super().__init__(
            message=(
                f"You do not have the '{permission_code}' permission required "
                "to perform this approval."
            ),
            code="APPROVAL_PERMISSION_DENIED",
            details={"permission_code": permission_code},
            http_status=403,
        )


class JournalNotReversibleError(AccountingException):
    """Raised when attempting to reverse a journal entry that is not POSTED.

    Spec ref: spec.md §15.5 — "Any posted journal entry can be reversed."
    """

    def __init__(self, journal_number: str | None, current_status: str) -> None:
        super().__init__(
            message=(
                f"Journal entry '{journal_number or '?'}' cannot be reversed: "
                f"status is {current_status}, must be POSTED."
            ),
            code="JOURNAL_NOT_REVERSIBLE",
            details={
                "journal_number": journal_number,
                "current_status": current_status,
            },
            http_status=422,
        )


class YearEndCloseBlockedError(AccountingException):
    """Raised when year-end close is attempted before all periods are LOCKED.

    Invariant: data-model.md §2.2 — "Year-end close cannot proceed until
    all periods in the year are LOCKED."
    """

    def __init__(self, fiscal_year_name: str, open_period_names: list[str]) -> None:
        super().__init__(
            message=(
                f"Cannot execute year-end close for '{fiscal_year_name}': "
                f"period(s) not locked: {', '.join(open_period_names)}."
            ),
            code="YEAR_END_CLOSE_BLOCKED",
            details={
                "fiscal_year_name": fiscal_year_name,
                "open_period_names": open_period_names,
            },
            http_status=422,
        )


# ── Recurring Journal Entries (Phase 5) ─────────────────────────────────────


class RecurringTemplateNotFoundError(NotFoundException):
    """Raised when a referenced RecurringJournalTemplate does not exist for this company."""

    def __init__(self, template_id: str | None = None) -> None:
        super().__init__(
            message=f"Recurring journal template '{template_id}' not found.",
            details={"template_id": template_id},
        )


# ── Accounts Receivable (Phase 6) ────────────────────────────────────────────


class CustomerLedgerNotFoundError(NotFoundException):
    """Raised when a customer has no CustomerLedger for this company yet."""

    def __init__(self, customer_id: str | None = None) -> None:
        super().__init__(
            message=f"No customer ledger found for customer '{customer_id}'.",
            details={"customer_id": customer_id},
        )


class ARTransactionNotFoundError(NotFoundException):
    """Raised when a referenced ARTransaction does not exist for this company."""

    def __init__(self, ar_transaction_id: str | None = None) -> None:
        super().__init__(
            message=f"AR transaction '{ar_transaction_id}' not found.",
            details={"ar_transaction_id": ar_transaction_id},
        )


class WriteOffNotAllowedError(AccountingException):
    """Raised when a write-off is attempted on an AR transaction that is not
    eligible (already PAID/WRITTEN_OFF, or has a positive outstanding
    amount mismatch with the requested write-off amount).
    """

    def __init__(self, ar_transaction_id: str, current_status: str) -> None:
        super().__init__(
            message=(
                f"AR transaction '{ar_transaction_id}' cannot be written off: "
                f"status is {current_status}."
            ),
            code="WRITE_OFF_NOT_ALLOWED",
            details={
                "ar_transaction_id": ar_transaction_id,
                "current_status": current_status,
            },
            http_status=422,
        )


class ARReconciliationError(AccountingException):
    """Raised when the AR control account GL balance does not reconcile to
    the sum of open CustomerLedger balances (tasks.md T140).

    This is a financial-integrity backstop, not an expected user-facing
    error — it indicates a bug, not invalid input.
    """

    def __init__(self, ar_ledger_sum: str, gl_balance: str) -> None:
        super().__init__(
            message=(
                f"AR reconciliation failed: CustomerLedger sum ({ar_ledger_sum}) != "
                f"AR control account GL balance ({gl_balance})."
            ),
            code="AR_RECONCILIATION_ERROR",
            details={"ar_ledger_sum": ar_ledger_sum, "gl_balance": gl_balance},
            http_status=500,
        )


# ── Accounts Payable (Phase 7) ───────────────────────────────────────────────


class SupplierLedgerNotFoundError(NotFoundException):
    """Raised when a referenced SupplierLedger does not exist for this company."""

    def __init__(self, supplier_id: str | None = None) -> None:
        super().__init__(
            message=f"Supplier ledger for supplier '{supplier_id}' not found.",
            details={"supplier_id": supplier_id},
        )


class APTransactionNotFoundError(NotFoundException):
    """Raised when a referenced APTransaction does not exist for this company."""

    def __init__(self, ap_transaction_id: str | None = None) -> None:
        super().__init__(
            message=f"AP transaction '{ap_transaction_id}' not found.",
            details={"ap_transaction_id": ap_transaction_id},
        )


class SupplierReconciliationNotFoundError(NotFoundException):
    """Raised when a referenced SupplierStatementReconciliation does not exist."""

    def __init__(self, reconciliation_id: str | None = None) -> None:
        super().__init__(
            message=f"Supplier reconciliation '{reconciliation_id}' not found.",
            details={"reconciliation_id": reconciliation_id},
        )


class APReconciliationError(AccountingException):
    """Raised when the AP control account GL balance does not reconcile to
    the sum of open SupplierLedger balances (tasks.md T165) — mirrors
    ``ARReconciliationError``.

    This is a financial-integrity backstop, not an expected user-facing
    error — it indicates a bug, not invalid input.
    """

    def __init__(self, ap_ledger_sum: str, gl_balance: str) -> None:
        super().__init__(
            message=(
                f"AP reconciliation failed: SupplierLedger sum ({ap_ledger_sum}) != "
                f"AP control account GL balance ({gl_balance})."
            ),
            code="AP_RECONCILIATION_ERROR",
            details={"ap_ledger_sum": ap_ledger_sum, "gl_balance": gl_balance},
            http_status=500,
        )


# ── Banking (Phase 8) ────────────────────────────────────────────────────────


class BankAccountNotFoundError(NotFoundException):
    """Raised when a referenced BankAccount does not exist for this company."""

    def __init__(self, bank_account_id: str | None = None) -> None:
        super().__init__(
            message=f"Bank account '{bank_account_id}' not found.",
            details={"bank_account_id": bank_account_id},
        )


class BankReconciliationNotFoundError(NotFoundException):
    """Raised when a referenced BankReconciliation does not exist for this company."""

    def __init__(self, reconciliation_id: str | None = None) -> None:
        super().__init__(
            message=f"Bank reconciliation '{reconciliation_id}' not found.",
            details={"reconciliation_id": reconciliation_id},
        )


class ChequeNotFoundError(NotFoundException):
    """Raised when a referenced Cheque does not exist for this company."""

    def __init__(self, cheque_id: str | None = None) -> None:
        super().__init__(
            message=f"Cheque '{cheque_id}' not found.",
            details={"cheque_id": cheque_id},
        )


class ReconciliationLockedError(AccountingException):
    """Raised when a modification is attempted on a LOCKED BankReconciliation
    (data-model.md §8.3: "A completed reconciliation is locked — no
    modifications to matched items").
    """

    def __init__(self, reconciliation_id: str) -> None:
        super().__init__(
            message=f"Bank reconciliation '{reconciliation_id}' is locked and cannot be modified.",
            code="RECONCILIATION_LOCKED",
            details={"reconciliation_id": reconciliation_id},
            http_status=422,
        )


class ReconciliationNotBalancedError(AccountingException):
    """Raised when completing a reconciliation whose statement/GL difference
    is not zero (data-model.md §8.3: difference "must be 0 to complete").
    """

    def __init__(self, reconciliation_id: str, difference: str) -> None:
        super().__init__(
            message=(
                f"Bank reconciliation '{reconciliation_id}' cannot be completed: "
                f"difference ({difference}) is not zero."
            ),
            code="RECONCILIATION_NOT_BALANCED",
            details={"reconciliation_id": reconciliation_id, "difference": difference},
            http_status=422,
        )


# ── Cash Management (Phase 9) ───────────────────────────────────────────────


class CashAccountNotFoundError(NotFoundException):
    """Raised when a referenced CashAccount does not exist for this company."""

    def __init__(self, cash_account_id: str | None = None) -> None:
        super().__init__(
            message=f"Cash account '{cash_account_id}' not found.",
            details={"cash_account_id": cash_account_id},
        )


class PettyCashVoucherNotFoundError(NotFoundException):
    """Raised when a referenced PettyCashVoucher does not exist for this company."""

    def __init__(self, voucher_id: str | None = None) -> None:
        super().__init__(
            message=f"Petty cash voucher '{voucher_id}' not found.",
            details={"voucher_id": voucher_id},
        )


class CashReconciliationNotFoundError(NotFoundException):
    """Raised when a referenced CashReconciliation does not exist for this company."""

    def __init__(self, reconciliation_id: str | None = None) -> None:
        super().__init__(
            message=f"Cash reconciliation '{reconciliation_id}' not found.",
            details={"reconciliation_id": reconciliation_id},
        )


class VoucherAlreadyReplenishedError(AccountingException):
    """Raised when replenishment is attempted on a PettyCashVoucher already
    linked to a prior replenishment journal entry (data-model.md §2.7 invariant:
    each voucher may only fund one replenishment).
    """

    def __init__(self, voucher_id: str) -> None:
        super().__init__(
            message=f"Petty cash voucher '{voucher_id}' has already been replenished.",
            code="VOUCHER_ALREADY_REPLENISHED",
            details={"voucher_id": voucher_id},
            http_status=422,
        )


# ── Payments (Phase 10) ──────────────────────────────────────────────────────


class PaymentNotFoundError(NotFoundException):
    """Raised when a referenced Payment does not exist for this company."""

    def __init__(self, payment_id: str | None = None) -> None:
        super().__init__(
            message=f"Payment '{payment_id}' not found.",
            details={"payment_id": payment_id},
        )


class PaymentRefundNotFoundError(NotFoundException):
    """Raised when a referenced PaymentRefund does not exist for this company."""

    def __init__(self, refund_id: str | None = None) -> None:
        super().__init__(
            message=f"Payment refund '{refund_id}' not found.",
            details={"refund_id": refund_id},
        )


class AllocationExceedsOutstandingError(AccountingException):
    """Raised when an allocation line's amount exceeds either the target
    transaction's outstanding balance or the payment's remaining unallocated
    balance (data-model.md §2.8 invariant: "Sum(allocations) ≤ payment_amount";
    §4.3 responsibility #1/#2).
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="ALLOCATION_EXCEEDS_OUTSTANDING",
            http_status=422,
        )


class PaymentCancellationNotAllowedError(AccountingException):
    """Raised when cancellation is attempted on a Payment that has active
    allocations or is already cancelled (data-model.md §2.8 invariant:
    "A cancelled payment cannot be allocated").
    """

    def __init__(self, payment_id: str, reason: str) -> None:
        super().__init__(
            message=f"Payment '{payment_id}' cannot be cancelled: {reason}",
            code="PAYMENT_CANCELLATION_NOT_ALLOWED",
            details={"payment_id": payment_id},
            http_status=422,
        )


class WHTNotEnabledError(AccountingException):
    """Raised when a WHT amount is supplied but the
    ``accounting.taxwithholding.enabled`` feature flag is off for this company.
    """

    def __init__(self) -> None:
        super().__init__(
            message="Withholding tax is not enabled for this company.",
            code="WHT_NOT_ENABLED",
            http_status=422,
        )


# ── Tax Engine & Cost Centers (Phase 11) ────────────────────────────────────


class TaxCodeNotFoundError(NotFoundException):
    """Raised when a referenced TaxCode does not exist for this company."""

    def __init__(self, tax_code_id: str | None = None) -> None:
        super().__init__(
            message=f"Tax code '{tax_code_id}' not found.",
            details={"tax_code_id": tax_code_id},
        )


class TaxGroupNotFoundError(NotFoundException):
    """Raised when a referenced TaxGroup does not exist for this company."""

    def __init__(self, tax_group_id: str | None = None) -> None:
        super().__init__(
            message=f"Tax group '{tax_group_id}' not found.",
            details={"tax_group_id": tax_group_id},
        )


class TaxRateOverlapError(AccountingException):
    """Raised when a new/updated TaxRate's effective date range overlaps an
    existing rate for the same TaxCode (data-model.md §2.9 invariant:
    "A tax code's effective date ranges cannot overlap for the same code").
    """

    def __init__(self, tax_code_id: str) -> None:
        super().__init__(
            message=f"Tax rate effective date range overlaps an existing rate for tax code '{tax_code_id}'.",
            code="TAX_RATE_OVERLAP",
            details={"tax_code_id": tax_code_id},
            http_status=422,
        )


class CostCenterNotFoundError(NotFoundException):
    """Raised when a referenced CostCenter does not exist for this company."""

    def __init__(self, cost_center_id: str | None = None) -> None:
        super().__init__(
            message=f"Cost center '{cost_center_id}' not found.",
            details={"cost_center_id": cost_center_id},
        )


class DepartmentNotFoundError(NotFoundException):
    """Raised when a referenced Department does not exist for this company."""

    def __init__(self, department_id: str | None = None) -> None:
        super().__init__(
            message=f"Department '{department_id}' not found.",
            details={"department_id": department_id},
        )


class ProjectNotFoundError(NotFoundException):
    """Raised when a referenced Project does not exist for this company."""

    def __init__(self, project_id: str | None = None) -> None:
        super().__init__(
            message=f"Project '{project_id}' not found.",
            details={"project_id": project_id},
        )


# ── Multi-Currency & Exchange Rates (Phase 12) ──────────────────────────────


class CurrencyRevaluationRunNotFoundError(NotFoundException):
    """Raised when a referenced CurrencyRevaluationRun does not exist for this company."""

    def __init__(self, run_id: str | None = None) -> None:
        super().__init__(
            message=f"Currency revaluation run '{run_id}' not found.",
            details={"run_id": run_id},
        )


# ── AI ERP Readiness (Phase 17) ─────────────────────────────────────────────


class AccountingFeatureDisabledError(AccountingException):
    """Raised when an endpoint gated by an accounting feature flag is called
    while that flag is disabled for the company (e.g. ``accounting.ai.enabled``
    for the Phase 17 AI readiness endpoints). Mirrors the exact convention
    already established by ``InventoryFeatureDisabledError``
    (``modules/inventory/exceptions.py``) — a dedicated ``FEATURE_DISABLED``
    / 403 rather than a generic 4xx, distinct from ``ApprovalPermissionDeniedError``
    (RBAC denial) and ``WHTNotEnabledError`` (a business-rule 422, not a
    hard access gate).
    """

    def __init__(self, feature_key: str, message: str | None = None) -> None:
        super().__init__(
            message=message
            or f"Feature '{feature_key}' is not enabled for this company.",
            code="FEATURE_DISABLED",
            details={"feature_key": feature_key},
            http_status=403,
        )


class JournalEntryNotFoundForAnomalyFlagError(NotFoundException):
    """Raised when ``POST /accounting/ai/anomaly-report`` references a
    journal_entry_id that does not exist (or isn't POSTED) for this company.
    """

    def __init__(self, journal_entry_id: str) -> None:
        super().__init__(
            message=f"Journal entry '{journal_entry_id}' not found or not posted.",
            details={"journal_entry_id": journal_entry_id},
        )

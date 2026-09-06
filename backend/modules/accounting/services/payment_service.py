"""PaymentService — Payment Processing — Phase 10.

Customer receipts, supplier disbursements, advances, refunds, cancellation,
and WHT. Allocation itself is delegated to ``AllocationEngine``.

Every payment posts its own base GL movement immediately (DR Bank/Cash / CR
AR-control for a customer receipt; DR AP-control / CR Bank/Cash for a
supplier disbursement — or the designated advance/deposit account instead
of the AR/AP control account for ADVANCE_RECEIPT/ADVANCE_PAYMENT, per
spec.md §22.4) and creates a paired "credit" AR/APTransaction (negative
outstanding) in the same atomic transaction — see allocation_engine.py's
module docstring for why this single mechanism also covers overpayments
and advances without further special-casing.

Spec ref: specs/008-accounting-finance/spec.md §22 Payments
Tasks ref: specs/008-accounting-finance/tasks.md T208-T211
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import (
    ARTransactionStatus,
    PaymentPartyType,
    PaymentType,
)
from modules.accounting.exceptions import (
    ApprovalPermissionDeniedError,
    BankAccountNotFoundError,
    CashAccountNotFoundError,
    InvalidJournalStateTransitionError,
    PaymentCancellationNotAllowedError,
    PaymentNotFoundError,
    PaymentRefundNotFoundError,
    PostingValidationError,
    SelfApprovalNotAllowedError,
    WHTNotEnabledError,
)
from modules.accounting.models.ap import APTransaction
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import (
    Payment,
    PaymentAllocationLine,
    PaymentRefund,
)
from modules.accounting.repositories.ap import (
    APTransactionRepository,
    SupplierLedgerRepository,
)
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.cash import CashAccountRepository
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.payments import (
    PaymentAllocationLineRepository,
    PaymentRefundRepository,
    PaymentRepository,
)
from modules.accounting.services.allocation_engine import AllocationEngine
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.permission_check import user_has_accounting_permission
from modules.accounting.services.posting_engine import PostingEngine, PostingResult

_WHT_FLAG_KEY = "accounting.taxwithholding.enabled"
_APPROVAL_FLAG_KEY = "accounting.approvalworkflow.enabled"


@dataclass
class DraftPaymentResult:
    """Sentinel returned by ``stage_customer_payment()`` for the pre-
    existing above-payment_approval_threshold DRAFT branch (plan.md
    §12.3.1) — no GL/AR truth exists yet, so there is nothing for a
    caller to bundle with it. That branch keeps its existing early
    commit unchanged."""

    payment: Payment


@dataclass
class StagedCustomerPayment:
    """Flush-only result of ``stage_customer_payment()``'s immediate-
    post branch (plan.md §12.3.1). The GL entry, ``Payment``, and credit
    ``ARTransaction`` exist in the session, fully built, but not
    committed. Pass to ``finalize_customer_payment()`` to commit."""

    payment: Payment
    journal_entry: JournalEntry
    journal_number: str
    posted_at: datetime


class PaymentService:
    """Application service for customer/supplier payment processing."""

    def __init__(
        self,
        db: Session,
        payment_repo: PaymentRepository,
        allocation_line_repo: PaymentAllocationLineRepository,
        refund_repo: PaymentRefundRepository,
        ar_transaction_repo: ARTransactionRepository,
        ap_transaction_repo: APTransactionRepository,
        customer_ledger_repo: CustomerLedgerRepository,
        supplier_ledger_repo: SupplierLedgerRepository,
        bank_account_repo: BankAccountRepository,
        cash_account_repo: CashAccountRepository,
        config_repo: AccountingConfigurationRepository,
        flag_service: AccountingFeatureFlagService,
        allocation_engine: AllocationEngine,
        posting_engine: PostingEngine,
        audit_service: AuditLogService,
    ) -> None:
        self.db = db
        self._payments = payment_repo
        self._allocation_lines = allocation_line_repo
        self._refunds = refund_repo
        self._ar_transactions = ar_transaction_repo
        self._ap_transactions = ap_transaction_repo
        self._customer_ledgers = customer_ledger_repo
        self._supplier_ledgers = supplier_ledger_repo
        self._bank_accounts = bank_account_repo
        self._cash_accounts = cash_account_repo
        self._config_repo = config_repo
        self._flags = flag_service
        self._allocation_engine = allocation_engine
        self._engine = posting_engine
        self._audit = audit_service

    @staticmethod
    def _payment_snapshot(payment: Payment) -> dict[str, Any]:
        return {
            "status": payment.status,
            "amount_base": str(payment.amount_base),
            "party_type": payment.party_type,
            "party_id": str(payment.party_id),
        }

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_payment(self, company_id: UUID, payment_id: UUID) -> Payment:
        payment = self._payments.get_by_id_or_none(id=payment_id, company_id=company_id)
        if payment is None:
            raise PaymentNotFoundError(payment_id=str(payment_id))
        return payment

    def list_unallocated_payments(
        self, company_id: UUID, party_type: str | None = None
    ) -> list[Payment]:
        """Payments with a nonzero remaining credit balance (tasks.md T219:
        "list of payments not yet fully allocated").

        ``Payment.status`` alone cannot answer this: ``AllocationEngine.
        allocate()`` flips status to ALLOCATED on the FIRST allocation
        line applied, whether or not that fully consumes the payment — a
        payment allocated for only part of its amount (an overpayment,
        spec.md 22.5) still has status ALLOCATED. The only authoritative
        signal is the paired AR/APTransaction credit record's
        ``outstanding_amount`` (0 once fully consumed).
        """
        candidates = self._payments.find_non_cancelled(
            company_id, party_type=party_type
        )
        result: list[Payment] = []
        for payment in candidates:
            txn_repo = (
                self._ar_transactions
                if payment.party_type == PaymentPartyType.CUSTOMER.value
                else self._ap_transactions
            )
            credit_transaction = txn_repo.find_by_source_document(
                company_id=company_id,
                source_document_type="Payment",
                source_document_id=payment.id,
            )
            if (
                credit_transaction is not None
                and credit_transaction.outstanding_amount != 0
            ):
                result.append(payment)
        return result

    def list_customer_payments(
        self, company_id: UUID, customer_id: UUID
    ) -> list[Payment]:
        return self._payments.find_by_party(
            company_id, PaymentPartyType.CUSTOMER.value, customer_id
        )

    def list_supplier_payments(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[Payment]:
        return self._payments.find_by_party(
            company_id, PaymentPartyType.SUPPLIER.value, supplier_id
        )

    def list_allocation_lines(
        self, company_id: UUID, payment_id: UUID
    ) -> list[PaymentAllocationLine]:
        return self._allocation_lines.find_by_payment(company_id, payment_id)

    # ------------------------------------------------------------------
    # Customer receipts
    # ------------------------------------------------------------------

    def create_customer_payment(
        self,
        company_id: UUID,
        customer_id: UUID,
        payment_method: str,
        payment_date: date,
        amount: Decimal,
        currency_code: str,
        exchange_rate: Decimal = Decimal("1"),
        payment_type: str = PaymentType.CUSTOMER_RECEIPT.value,
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
        advance_account_id: UUID | None = None,
        reference: str | None = None,
        notes: str | None = None,
        cheque_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[Payment, PostingResult | None]:
        """Thin, 100%-backward-compatible wrapper of
        ``stage_customer_payment()`` + ``finalize_customer_payment()``
        (plan.md §12.3.1) — identical behavior/return type for every
        existing standalone caller."""
        staged = self.stage_customer_payment(
            company_id=company_id,
            customer_id=customer_id,
            payment_method=payment_method,
            payment_date=payment_date,
            amount=amount,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            payment_type=payment_type,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            advance_account_id=advance_account_id,
            reference=reference,
            notes=notes,
            cheque_id=cheque_id,
            actor_id=actor_id,
        )
        if isinstance(staged, DraftPaymentResult):
            return staged.payment, None
        return self.finalize_customer_payment(staged, actor_id)

    def stage_customer_payment(
        self,
        company_id: UUID,
        customer_id: UUID,
        payment_method: str,
        payment_date: date,
        amount: Decimal,
        currency_code: str,
        exchange_rate: Decimal = Decimal("1"),
        payment_type: str = PaymentType.CUSTOMER_RECEIPT.value,
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
        advance_account_id: UUID | None = None,
        reference: str | None = None,
        notes: str | None = None,
        cheque_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> StagedCustomerPayment | DraftPaymentResult:
        """Stage a customer payment (plan.md §12.3.1) — flush only, no
        commit for the immediate-post branch (mirrors ``ar_service.py``'s
        ``stage_adjustment()``). The pre-existing above-threshold DRAFT
        branch is unchanged (self-contained, no Accounting truth created
        yet) and keeps its own early commit, returning
        ``DraftPaymentResult`` instead.

        The caller may stage further writes into the same session (e.g.
        Installments' ``InstallmentAllocationReference`` rows) before
        calling ``finalize_customer_payment()``, which performs the sole
        commit for everything staged since this call.
        """
        if amount <= 0:
            raise PostingValidationError("Payment amount must be positive.")
        debit_account_id = self._resolve_payment_account(
            company_id, bank_account_id, cash_account_id
        )

        config = self._get_config(company_id)
        is_advance = payment_type == PaymentType.ADVANCE_RECEIPT.value
        amount_base = amount * exchange_rate

        # T274: payments above payment_approval_threshold are created DRAFT
        # (pending approval) — no GL/AR impact until approve_payment() runs.
        # The Payment row already carries every field needed to reconstruct
        # the journal lines at approval time (see approve_payment()). This
        # check MUST run before the default_ar_account_id/advance_account_id
        # validation below — a DRAFT payment doesn't need the GL credit
        # account resolved until approval, so a company that hasn't finished
        # configuring its AR control account yet can still queue payments
        # for approval (bug found during Phase 14 live verification: the
        # validation was previously unconditional, so payments above
        # threshold failed outright instead of going DRAFT whenever AR
        # control account setup was incomplete).
        threshold = config.payment_approval_threshold if config else None
        if (
            threshold is not None
            and amount_base > threshold
            and self._flags.is_enabled(company_id, _APPROVAL_FLAG_KEY)
        ):
            if is_advance and advance_account_id is None:
                raise PostingValidationError(
                    "advance_account_id is required for advance receipts."
                )
            pending = Payment(
                company_id=company_id,
                payment_type=payment_type,
                payment_method=payment_method,
                payment_date=payment_date,
                currency_code=currency_code,
                exchange_rate=exchange_rate,
                amount_foreign=amount,
                amount_base=amount_base,
                bank_account_id=bank_account_id,
                cash_account_id=cash_account_id,
                advance_account_id=advance_account_id,
                party_type=PaymentPartyType.CUSTOMER.value,
                party_id=customer_id,
                reference=reference,
                notes=notes,
                journal_entry_id=None,
                cheque_id=cheque_id,
                status="DRAFT",
                created_by=actor_id,
            )
            self.db.add(pending)
            self.db.flush()
            self._audit.record(
                company_id=company_id,
                entity_type="Payment",
                entity_id=pending.id,
                action="CREATED",
                actor_id=actor_id,
                after=self._payment_snapshot(pending),
                reason="Above payment_approval_threshold — pending approval",
            )
            self.db.commit()
            self.db.refresh(pending)
            return DraftPaymentResult(payment=pending)

        if is_advance:
            if advance_account_id is None:
                raise PostingValidationError(
                    "advance_account_id is required for advance receipts."
                )
            credit_account_id = advance_account_id
        else:
            if config.default_ar_account_id is None:
                raise PostingValidationError(
                    "Cannot post customer payment: default AR control account is not configured."
                )
            credit_account_id = config.default_ar_account_id

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PAYMENT",
            posting_date=payment_date,
            lines=[
                {
                    "account_id": debit_account_id,
                    "debit_amount": amount_base,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": credit_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount_base,
                },
            ],
            currency_code=currency_code,
            reference=reference,
            description=(
                "Customer advance receipt" if is_advance else "Customer payment receipt"
            ),
            source_document_type="CustomerPayment",
            source_document_id=None,
            actor_id=actor_id,
        )

        payment = Payment(
            company_id=company_id,
            payment_type=payment_type,
            payment_method=payment_method,
            payment_date=payment_date,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=amount,
            amount_base=amount_base,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            party_type=PaymentPartyType.CUSTOMER.value,
            party_id=customer_id,
            reference=reference,
            notes=notes,
            journal_entry_id=entry.id,
            cheque_id=cheque_id,
            status="POSTED",
            created_by=actor_id,
        )
        self.db.add(payment)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="Payment",
            entity_id=payment.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._payment_snapshot(payment),
        )

        ledger = self._get_or_create_customer_ledger(company_id, customer_id)
        credit_transaction = ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type="ADVANCE" if is_advance else "PAYMENT",
            transaction_date=payment_date,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=-amount,
            amount_base=-amount_base,
            outstanding_amount=-amount_base,
            status=ARTransactionStatus.OPEN.value,
            source_document_type="Payment",
            source_document_id=payment.id,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(credit_transaction)
        self.db.flush()
        self._recompute_customer_ledger_balance(company_id, ledger.id)

        return StagedCustomerPayment(
            payment=payment,
            journal_entry=entry,
            journal_number=journal_number,
            posted_at=posted_at,
        )

    def finalize_customer_payment(
        self, staged: StagedCustomerPayment, actor_id: UUID | None
    ) -> tuple[Payment, PostingResult]:
        """The sole commit point for ``stage_customer_payment()``'s
        immediate-post branch — thin wrapper over
        ``PostingEngine.finalize_and_publish()`` (plan.md §12.3.1)."""
        result = self._engine.finalize_and_publish(
            staged.journal_entry, staged.journal_number, staged.posted_at, actor_id
        )
        self.db.refresh(staged.payment)
        return staged.payment, result

    # ------------------------------------------------------------------
    # Supplier disbursements
    # ------------------------------------------------------------------

    def create_supplier_payment(
        self,
        company_id: UUID,
        supplier_id: UUID,
        payment_method: str,
        payment_date: date,
        amount: Decimal,
        currency_code: str,
        exchange_rate: Decimal = Decimal("1"),
        payment_type: str = PaymentType.SUPPLIER_DISBURSEMENT.value,
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
        advance_account_id: UUID | None = None,
        wht_amount: Decimal = Decimal("0"),
        wht_payable_account_id: UUID | None = None,
        reference: str | None = None,
        notes: str | None = None,
        cheque_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[Payment, PostingResult | None]:
        if amount <= 0:
            raise PostingValidationError("Payment amount must be positive.")
        if wht_amount < 0:
            raise PostingValidationError("wht_amount cannot be negative.")
        if wht_amount >= amount:
            raise PostingValidationError(
                "wht_amount must be less than the gross payment amount."
            )
        if wht_amount > 0:
            if not self._flags.is_enabled(company_id, _WHT_FLAG_KEY):
                raise WHTNotEnabledError()
            if wht_payable_account_id is None:
                raise PostingValidationError(
                    "wht_payable_account_id is required when wht_amount > 0."
                )

        credit_cash_account_id = self._resolve_payment_account(
            company_id, bank_account_id, cash_account_id
        )

        config = self._get_config(company_id)
        is_advance = payment_type == PaymentType.ADVANCE_PAYMENT.value
        amount_base = amount * exchange_rate
        wht_base = wht_amount * exchange_rate
        net_cash_base = amount_base - wht_base

        # T274: payments above payment_approval_threshold are created DRAFT
        # (pending approval) — no GL/AP impact until approve_payment() runs.
        # Must run before the default_ap_account_id/advance_account_id
        # validation below — see the matching comment in
        # create_customer_payment() for why (Phase 14 live-verification bug).
        threshold = config.payment_approval_threshold if config else None
        if (
            threshold is not None
            and amount_base > threshold
            and self._flags.is_enabled(company_id, _APPROVAL_FLAG_KEY)
        ):
            if is_advance and advance_account_id is None:
                raise PostingValidationError(
                    "advance_account_id is required for advance payments."
                )
            pending = Payment(
                company_id=company_id,
                payment_type=payment_type,
                payment_method=payment_method,
                payment_date=payment_date,
                currency_code=currency_code,
                exchange_rate=exchange_rate,
                amount_foreign=amount,
                amount_base=amount_base,
                bank_account_id=bank_account_id,
                cash_account_id=cash_account_id,
                advance_account_id=advance_account_id,
                party_type=PaymentPartyType.SUPPLIER.value,
                party_id=supplier_id,
                reference=reference,
                notes=notes,
                journal_entry_id=None,
                cheque_id=cheque_id,
                wht_amount=wht_base,
                wht_payable_account_id=wht_payable_account_id,
                status="DRAFT",
                created_by=actor_id,
            )
            self.db.add(pending)
            self.db.flush()
            self._audit.record(
                company_id=company_id,
                entity_type="Payment",
                entity_id=pending.id,
                action="CREATED",
                actor_id=actor_id,
                after=self._payment_snapshot(pending),
                reason="Above payment_approval_threshold — pending approval",
            )
            self.db.commit()
            self.db.refresh(pending)
            return pending, None

        if is_advance:
            if advance_account_id is None:
                raise PostingValidationError(
                    "advance_account_id is required for advance payments."
                )
            debit_account_id = advance_account_id
        else:
            if config.default_ap_account_id is None:
                raise PostingValidationError(
                    "Cannot post supplier payment: default AP control account is not configured."
                )
            debit_account_id = config.default_ap_account_id

        lines: list[dict[str, Any]] = [
            {
                "account_id": debit_account_id,
                "debit_amount": amount_base,
                "credit_amount": Decimal("0"),
            },
        ]
        if wht_amount > 0:
            lines.append(
                {
                    "account_id": credit_cash_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": net_cash_base,
                }
            )
            lines.append(
                {
                    "account_id": wht_payable_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": wht_base,
                }
            )
        else:
            lines.append(
                {
                    "account_id": credit_cash_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount_base,
                }
            )

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PAYMENT",
            posting_date=payment_date,
            lines=lines,
            currency_code=currency_code,
            reference=reference,
            description=(
                "Supplier advance payment"
                if is_advance
                else "Supplier payment disbursement"
            ),
            source_document_type="SupplierPayment",
            source_document_id=None,
            actor_id=actor_id,
        )

        payment = Payment(
            company_id=company_id,
            payment_type=payment_type,
            payment_method=payment_method,
            payment_date=payment_date,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=amount,
            amount_base=amount_base,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            party_type=PaymentPartyType.SUPPLIER.value,
            party_id=supplier_id,
            reference=reference,
            notes=notes,
            journal_entry_id=entry.id,
            cheque_id=cheque_id,
            wht_amount=wht_base,
            status="POSTED",
            created_by=actor_id,
        )
        self.db.add(payment)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="Payment",
            entity_id=payment.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._payment_snapshot(payment),
        )

        ledger = self._get_or_create_supplier_ledger(company_id, supplier_id)
        credit_transaction = APTransaction(
            company_id=company_id,
            supplier_ledger_id=ledger.id,
            transaction_type="ADVANCE" if is_advance else "PAYMENT",
            transaction_date=payment_date,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=-amount,
            amount_base=-amount_base,
            outstanding_amount=-amount_base,
            status=ARTransactionStatus.OPEN.value,
            source_document_type="Payment",
            source_document_id=payment.id,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(credit_transaction)
        self.db.flush()
        self._recompute_supplier_ledger_balance(company_id, ledger.id)

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(payment)
        return payment, result

    # ------------------------------------------------------------------
    # Approval workflow (T274) — for payments created DRAFT above
    # payment_approval_threshold. Mirrors PostingEngine's journal
    # approve()/reject() pattern: self-approval blocked, SoD permission
    # required, immutable audit trail either way.
    # ------------------------------------------------------------------

    def approve_payment(
        self, company_id: UUID, payment_id: UUID, approver_id: UUID | None
    ) -> tuple[Payment, PostingResult]:
        """Approve a DRAFT (pending-approval) payment and post its GL entry.

        Raises:
            PaymentNotFoundError
            InvalidJournalStateTransitionError: payment is not DRAFT.
            SelfApprovalNotAllowedError: ``approver_id`` created this payment.
            ApprovalPermissionDeniedError: approver lacks the permission.
        """
        payment = self.get_payment(company_id, payment_id)
        if payment.status != "DRAFT":
            raise InvalidJournalStateTransitionError(payment.status, "POSTED")
        if (
            payment.created_by is not None
            and approver_id is not None
            and payment.created_by == approver_id
        ):
            raise SelfApprovalNotAllowedError(str(payment.id))

        is_customer = payment.party_type == PaymentPartyType.CUSTOMER.value
        permission_code = (
            "accounting.payment.customer.approve"
            if is_customer
            else "accounting.payment.supplier.approve"
        )
        if not user_has_accounting_permission(
            self.db, company_id, approver_id, permission_code
        ):
            raise ApprovalPermissionDeniedError(permission_code)

        before = self._payment_snapshot(payment)
        config = self._get_config(company_id)
        amount = payment.amount_foreign
        amount_base = payment.amount_base
        is_advance = payment.payment_type in (
            PaymentType.ADVANCE_RECEIPT.value,
            PaymentType.ADVANCE_PAYMENT.value,
        )

        if is_customer:
            debit_account_id = self._resolve_payment_account(
                company_id, payment.bank_account_id, payment.cash_account_id
            )
            if is_advance:
                if payment.advance_account_id is None:
                    raise PostingValidationError(
                        "advance_account_id is required for advance receipts."
                    )
                credit_account_id = payment.advance_account_id
            else:
                if config.default_ar_account_id is None:
                    raise PostingValidationError(
                        "Cannot post customer payment: default AR control account is not configured."
                    )
                credit_account_id = config.default_ar_account_id
            lines: list[dict[str, Any]] = [
                {
                    "account_id": debit_account_id,
                    "debit_amount": amount_base,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": credit_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount_base,
                },
            ]
            description = (
                "Customer advance receipt" if is_advance else "Customer payment receipt"
            )
            source_document_type = "CustomerPayment"
        else:
            credit_cash_account_id = self._resolve_payment_account(
                company_id, payment.bank_account_id, payment.cash_account_id
            )
            if is_advance:
                if payment.advance_account_id is None:
                    raise PostingValidationError(
                        "advance_account_id is required for advance payments."
                    )
                debit_account_id = payment.advance_account_id
            else:
                if config.default_ap_account_id is None:
                    raise PostingValidationError(
                        "Cannot post supplier payment: default AP control account is not configured."
                    )
                debit_account_id = config.default_ap_account_id
            wht_base = payment.wht_amount or Decimal("0")
            net_cash_base = amount_base - wht_base
            lines = [
                {
                    "account_id": debit_account_id,
                    "debit_amount": amount_base,
                    "credit_amount": Decimal("0"),
                },
            ]
            if wht_base > 0:
                lines.append(
                    {
                        "account_id": credit_cash_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": net_cash_base,
                    }
                )
                lines.append(
                    {
                        "account_id": payment.wht_payable_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": wht_base,
                    }
                )
            else:
                lines.append(
                    {
                        "account_id": credit_cash_account_id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": amount_base,
                    }
                )
            description = (
                "Supplier advance payment"
                if is_advance
                else "Supplier payment disbursement"
            )
            source_document_type = "SupplierPayment"

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PAYMENT",
            posting_date=payment.payment_date,
            lines=lines,
            currency_code=payment.currency_code,
            reference=payment.reference,
            description=description,
            source_document_type=source_document_type,
            source_document_id=None,
            actor_id=approver_id,
        )

        payment.journal_entry_id = entry.id
        payment.status = "POSTED"
        self.db.flush()

        if is_customer:
            ledger = self._get_or_create_customer_ledger(company_id, payment.party_id)
            credit_transaction: ARTransaction | APTransaction = ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="ADVANCE" if is_advance else "PAYMENT",
                transaction_date=payment.payment_date,
                currency_code=payment.currency_code,
                exchange_rate=payment.exchange_rate,
                amount_foreign=-amount,
                amount_base=-amount_base,
                outstanding_amount=-amount_base,
                status=ARTransactionStatus.OPEN.value,
                source_document_type="Payment",
                source_document_id=payment.id,
                journal_entry_id=entry.id,
                created_by=approver_id,
            )
            self.db.add(credit_transaction)
            self.db.flush()
            self._recompute_customer_ledger_balance(company_id, ledger.id)
        else:
            ledger = self._get_or_create_supplier_ledger(company_id, payment.party_id)
            credit_transaction = APTransaction(
                company_id=company_id,
                supplier_ledger_id=ledger.id,
                transaction_type="ADVANCE" if is_advance else "PAYMENT",
                transaction_date=payment.payment_date,
                currency_code=payment.currency_code,
                exchange_rate=payment.exchange_rate,
                amount_foreign=-amount,
                amount_base=-amount_base,
                outstanding_amount=-amount_base,
                status=ARTransactionStatus.OPEN.value,
                source_document_type="Payment",
                source_document_id=payment.id,
                journal_entry_id=entry.id,
                created_by=approver_id,
            )
            self.db.add(credit_transaction)
            self.db.flush()
            self._recompute_supplier_ledger_balance(company_id, ledger.id)

        self._audit.record(
            company_id=company_id,
            entity_type="Payment",
            entity_id=payment.id,
            action="APPROVED",
            actor_id=approver_id,
            before=before,
            after=self._payment_snapshot(payment),
        )

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, approver_id
        )
        self.db.refresh(payment)
        return payment, result

    def reject_payment(
        self,
        company_id: UUID,
        payment_id: UUID,
        actor_id: UUID | None,
        rejection_reason: str,
    ) -> Payment:
        """Reject a DRAFT (pending-approval) payment. No GL/AR/AP impact ever occurs."""
        payment = self.get_payment(company_id, payment_id)
        if payment.status != "DRAFT":
            raise InvalidJournalStateTransitionError(payment.status, "REJECTED")

        # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14):
        # reject is the mirror decision of approve_payment() on the same
        # DRAFT payment and had no permission check at all, letting any
        # company member reject a payment that only an approver-permission
        # holder could approve. Reuses the same permission code as approve
        # for the matching party type.
        is_customer = payment.party_type == PaymentPartyType.CUSTOMER.value
        permission_code = (
            "accounting.payment.customer.approve"
            if is_customer
            else "accounting.payment.supplier.approve"
        )
        if not user_has_accounting_permission(
            self.db, company_id, actor_id, permission_code
        ):
            raise ApprovalPermissionDeniedError(permission_code)

        before = self._payment_snapshot(payment)
        payment.status = "REJECTED"
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="Payment",
            entity_id=payment.id,
            action="REJECTED",
            actor_id=actor_id,
            before=before,
            after=self._payment_snapshot(payment),
            reason=rejection_reason,
        )
        self.db.commit()
        self.db.refresh(payment)
        return payment

    # ------------------------------------------------------------------
    # Allocation (delegated) / reallocation
    # ------------------------------------------------------------------

    def allocate_payment(
        self,
        company_id: UUID,
        payment_id: UUID,
        allocation_lines: list[dict[str, Any]],
        actor_id: UUID | None,
    ) -> list[PaymentAllocationLine]:
        return self._allocation_engine.allocate(
            company_id, payment_id, allocation_lines, actor_id
        )

    def reallocate_payment(
        self,
        company_id: UUID,
        payment_id: UUID,
        new_allocation_lines: list[dict[str, Any]],
        actor_id: UUID | None,
    ) -> list[PaymentAllocationLine]:
        """Reverse every existing allocation line for this payment, then
        apply ``new_allocation_lines`` via the same ``AllocationEngine``
        (data-model.md §4.3: "Re-allocation: reverse and redo").
        """
        payment = self.get_payment(company_id, payment_id)
        is_customer = payment.party_type == PaymentPartyType.CUSTOMER.value
        txn_repo = self._ar_transactions if is_customer else self._ap_transactions

        existing_lines = self._allocation_lines.find_by_payment(company_id, payment.id)
        credit_transaction = txn_repo.find_by_source_document(
            company_id=company_id,
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        if credit_transaction is None:
            raise PostingValidationError(
                f"Payment '{payment_id}' has no associated ledger credit transaction."
            )
        credit_transaction = txn_repo.get_by_id_locked(
            id=credit_transaction.id, company_id=company_id
        )
        if credit_transaction is None:
            raise PostingValidationError(
                f"Payment '{payment_id}' credit transaction not found."
            )

        for line in existing_lines:
            transaction_id = (
                line.ar_transaction_id if is_customer else line.ap_transaction_id
            )
            if transaction_id is None:
                continue
            transaction = txn_repo.get_by_id_locked(
                id=transaction_id, company_id=company_id
            )
            if transaction is None:
                continue

            total_reduction = (
                line.allocated_amount_foreign * transaction.exchange_rate
                + line.discount_amount
            )
            transaction.outstanding_amount = (
                transaction.outstanding_amount + total_reduction
            )
            transaction.status = self._derive_status(
                transaction.outstanding_amount, transaction.amount_base
            )
            self.db.add(transaction)

            credit_transaction.outstanding_amount = (
                credit_transaction.outstanding_amount - line.allocated_amount_base
            )
            credit_transaction.status = self._derive_status(
                credit_transaction.outstanding_amount, credit_transaction.amount_base
            )
            self.db.add(credit_transaction)

            line.is_deleted = True
            line.deleted_at = utcnow()
            self.db.add(line)
            self.db.flush()

            if line.gain_loss_journal_entry_id is not None:
                self._engine.reverse(
                    company_id=company_id,
                    journal_id=line.gain_loss_journal_entry_id,
                    actor_id=actor_id,
                    reason="Reallocation reversal",
                )
            else:
                self.db.commit()

        payment.status = "POSTED"
        self.db.add(payment)
        self.db.commit()

        return self._allocation_engine.allocate(
            company_id, payment.id, new_allocation_lines, actor_id
        )

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel_payment(
        self, company_id: UUID, payment_id: UUID, reason: str, actor_id: UUID | None
    ) -> Payment:
        payment = self.get_payment(company_id, payment_id)
        if payment.status == "CANCELLED":
            raise PaymentCancellationNotAllowedError(
                str(payment_id), "already cancelled"
            )

        # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14):
        # cancelling a POSTED payment calls PostingEngine.reverse() below,
        # the exact same GL-reversal operation gated by
        # accounting.journal.reverse on POST /journals/{id}/reverse — this
        # method had no check at all, letting a user without that
        # permission achieve an equivalent GL reversal indirectly.
        if payment.journal_entry_id is not None and not user_has_accounting_permission(
            self.db, company_id, actor_id, "accounting.journal.reverse"
        ):
            raise ApprovalPermissionDeniedError("accounting.journal.reverse")

        is_customer = payment.party_type == PaymentPartyType.CUSTOMER.value
        txn_repo = self._ar_transactions if is_customer else self._ap_transactions
        credit_transaction = txn_repo.find_by_source_document(
            company_id=company_id,
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        if credit_transaction is not None:
            credit_transaction = txn_repo.get_by_id_locked(
                id=credit_transaction.id, company_id=company_id
            )
        if (
            credit_transaction is not None
            and credit_transaction.outstanding_amount != -payment.amount_base
        ):
            raise PaymentCancellationNotAllowedError(
                str(payment_id), "has active allocations"
            )

        payment.status = "CANCELLED"
        self.db.add(payment)

        if credit_transaction is not None:
            credit_transaction.is_deleted = True
            credit_transaction.deleted_at = utcnow()
            self.db.add(credit_transaction)
        self.db.flush()

        if payment.journal_entry_id is not None:
            self._engine.reverse(
                company_id=company_id,
                journal_id=payment.journal_entry_id,
                actor_id=actor_id,
                reason=reason,
            )
        else:
            self.db.commit()

        self.db.refresh(payment)
        return payment

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    def process_refund(
        self,
        company_id: UUID,
        payment_id: UUID,
        refund_date: date,
        amount: Decimal,
        reason: str,
        bank_account_id: UUID | None = None,
        cash_account_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[PaymentRefund, PostingResult]:
        if amount <= 0:
            raise PostingValidationError("Refund amount must be positive.")
        payment = self.get_payment(company_id, payment_id)
        is_customer = payment.party_type == PaymentPartyType.CUSTOMER.value

        # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14):
        # this posts a brand-new, immediately-finalized GL entry moving
        # real cash and had no permission check at all, unlike every other
        # step of the money-movement lifecycle (create/approve_payment).
        # Reuses the same approve-tier permission as approve_payment.
        permission_code = (
            "accounting.payment.customer.approve"
            if is_customer
            else "accounting.payment.supplier.approve"
        )
        if not user_has_accounting_permission(
            self.db, company_id, actor_id, permission_code
        ):
            raise ApprovalPermissionDeniedError(permission_code)

        txn_repo = self._ar_transactions if is_customer else self._ap_transactions

        credit_transaction = txn_repo.find_by_source_document(
            company_id=company_id,
            source_document_type="Payment",
            source_document_id=payment.id,
        )
        if credit_transaction is None:
            raise PostingValidationError(
                f"Payment '{payment_id}' has no refundable credit balance."
            )
        credit_transaction = txn_repo.get_by_id_locked(
            id=credit_transaction.id, company_id=company_id
        )
        if credit_transaction is None or amount > abs(
            credit_transaction.outstanding_amount
        ):
            raise PostingValidationError(
                f"Refund amount ({amount}) exceeds the payment's remaining unallocated balance."
            )

        cash_gl_account_id = self._resolve_payment_account(
            company_id, bank_account_id, cash_account_id
        )
        config = self._get_config(company_id)
        control_account_id = (
            config.default_ar_account_id
            if is_customer
            else config.default_ap_account_id
        )
        if control_account_id is None:
            raise PostingValidationError(
                "Cannot post refund: default AR/AP control account is not configured."
            )

        if is_customer:
            lines = [
                {
                    "account_id": control_account_id,
                    "debit_amount": amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": cash_gl_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount,
                },
            ]
        else:
            lines = [
                {
                    "account_id": cash_gl_account_id,
                    "debit_amount": amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": control_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount,
                },
            ]

        entry, journal_number, posted_at = self._engine.stage_direct_posting(
            company_id=company_id,
            journal_type="AUTOMATED",
            posting_source="PAYMENT",
            posting_date=refund_date,
            lines=lines,
            currency_code=payment.currency_code,
            description=f"Payment refund: {reason}",
            source_document_type="PaymentRefund",
            source_document_id=payment.id,
            actor_id=actor_id,
        )

        credit_transaction.outstanding_amount = (
            credit_transaction.outstanding_amount + amount
        )
        credit_transaction.status = self._derive_status(
            credit_transaction.outstanding_amount, credit_transaction.amount_base
        )
        self.db.add(credit_transaction)

        refund = PaymentRefund(
            company_id=company_id,
            original_payment_id=payment.id,
            refund_date=refund_date,
            amount=amount,
            reason=reason,
            bank_account_id=bank_account_id,
            cash_account_id=cash_account_id,
            journal_entry_id=entry.id,
            created_by=actor_id,
        )
        self.db.add(refund)
        self.db.flush()

        result = self._engine.finalize_and_publish(
            entry, journal_number, posted_at, actor_id
        )
        self.db.refresh(refund)
        return refund, result

    def get_refund(self, company_id: UUID, refund_id: UUID) -> PaymentRefund:
        refund = self._refunds.get_by_id_or_none(id=refund_id, company_id=company_id)
        if refund is None:
            raise PaymentRefundNotFoundError(refund_id=str(refund_id))
        return refund

    # ------------------------------------------------------------------
    # WHT
    # ------------------------------------------------------------------

    def get_wht_certificate(self, company_id: UUID, payment_id: UUID) -> dict[str, Any]:
        payment = self.get_payment(company_id, payment_id)
        if payment.wht_amount <= 0:
            raise PostingValidationError(
                f"Payment '{payment_id}' has no withholding tax deducted."
            )
        gross = payment.amount_base
        net = gross - payment.wht_amount
        rate = (payment.wht_amount / gross * 100) if gross != 0 else Decimal("0")
        return {
            "payment_id": payment.id,
            "party_id": payment.party_id,
            "payment_date": payment.payment_date,
            "currency_code": payment.currency_code,
            "gross_amount": gross,
            "wht_amount": payment.wht_amount,
            "net_amount": net,
            "wht_rate_percent": rate,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_payment_account(
        self,
        company_id: UUID,
        bank_account_id: UUID | None,
        cash_account_id: UUID | None,
    ) -> UUID:
        if (bank_account_id is None) == (cash_account_id is None):
            raise PostingValidationError(
                "Exactly one of bank_account_id or cash_account_id is required."
            )
        if bank_account_id is not None:
            bank_account = self._bank_accounts.get_by_id_or_none(
                id=bank_account_id, company_id=company_id
            )
            if bank_account is None:
                raise BankAccountNotFoundError(bank_account_id=str(bank_account_id))
            return bank_account.gl_account_id
        assert cash_account_id is not None  # narrowed by the XOR check above
        cash_account = self._cash_accounts.get_by_id_or_none(
            id=cash_account_id, company_id=company_id
        )
        if cash_account is None:
            raise CashAccountNotFoundError(cash_account_id=str(cash_account_id))
        return cash_account.gl_account_id

    def _get_config(self, company_id: UUID) -> Any:
        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None:
            raise PostingValidationError(
                "Cannot process payment: accounting configuration is not set up for this company."
            )
        return config

    def _get_or_create_customer_ledger(
        self, company_id: UUID, customer_id: UUID
    ) -> Any:
        ledger = self._customer_ledgers.find_by_customer(company_id, customer_id)
        if ledger is not None:
            return ledger
        from modules.accounting.models.ar import CustomerLedger

        new_ledger = CustomerLedger(company_id=company_id, customer_id=customer_id)
        self.db.add(new_ledger)
        self.db.flush()
        return new_ledger

    def _get_or_create_supplier_ledger(
        self, company_id: UUID, supplier_id: UUID
    ) -> Any:
        ledger = self._supplier_ledgers.find_by_supplier(company_id, supplier_id)
        if ledger is not None:
            return ledger
        from modules.accounting.models.ap import SupplierLedger

        new_ledger = SupplierLedger(company_id=company_id, supplier_id=supplier_id)
        self.db.add(new_ledger)
        self.db.flush()
        return new_ledger

    def _recompute_customer_ledger_balance(
        self, company_id: UUID, customer_ledger_id: UUID
    ) -> None:
        ledger = self._customer_ledgers.get_by_id(
            id=customer_ledger_id, company_id=company_id
        )
        open_transactions = self._customer_ledgers.get_open_transactions(
            company_id, ledger.id
        )
        ledger.total_outstanding_base = sum(
            (t.outstanding_amount for t in open_transactions), Decimal("0")
        )
        self.db.add(ledger)

    def _recompute_supplier_ledger_balance(
        self, company_id: UUID, supplier_ledger_id: UUID
    ) -> None:
        ledger = self._supplier_ledgers.get_by_id(
            id=supplier_ledger_id, company_id=company_id
        )
        open_transactions = self._supplier_ledgers.get_open_transactions(
            company_id, ledger.id
        )
        ledger.total_outstanding_base = sum(
            (t.outstanding_amount for t in open_transactions), Decimal("0")
        )
        self.db.add(ledger)

    @staticmethod
    def _derive_status(
        outstanding_amount: Decimal, original_amount_base: Decimal
    ) -> str:
        if outstanding_amount == 0:
            return ARTransactionStatus.PAID.value
        if outstanding_amount == original_amount_base:
            return ARTransactionStatus.OPEN.value
        return ARTransactionStatus.PARTIALLY_PAID.value

"""Repositories for Payment Processing entities — Phase 10.

  PaymentRepository              — payment CRUD + party/date/unallocated scans
  PaymentAllocationLineRepository — allocation-line CRUD
  PaymentRefundRepository        — refund CRUD

Spec ref: specs/008-accounting-finance/tasks.md T204-T206
Data model: specs/008-accounting-finance/data-model.md line 508 (PaymentRepository)
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.payments import (
    Payment,
    PaymentAllocationLine,
    PaymentRefund,
)
from modules.accounting.repositories import BaseAccountingRepository


class PaymentRepository(BaseAccountingRepository[Payment]):
    """Data-access layer for the ``accounting_payments`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Payment)

    def find_by_party(
        self, company_id: UUID, party_type: str, party_id: UUID
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.company_id == company_id)
            .where(Payment.party_type == party_type)
            .where(Payment.party_id == party_id)
            .where(Payment.is_deleted == False)  # noqa: E712
            .order_by(Payment.payment_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_date_range(
        self, company_id: UUID, from_date: date, to_date: date
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.company_id == company_id)
            .where(Payment.payment_date >= from_date)
            .where(Payment.payment_date <= to_date)
            .where(Payment.is_deleted == False)  # noqa: E712
            .order_by(Payment.payment_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_wht_payments(
        self, company_id: UUID, from_date: date, to_date: date
    ) -> list[Payment]:
        """Supplier payments with withholding tax deducted (Phase 11's
        ``TaxService.get_wht_report()`` — spec.md §23.8 Withholding Tax
        Report). Excludes cancelled payments — a cancelled payment's WHT
        deduction was reversed along with the rest of its GL entry.
        """
        stmt = (
            select(Payment)
            .where(Payment.company_id == company_id)
            .where(Payment.payment_date >= from_date)
            .where(Payment.payment_date <= to_date)
            .where(Payment.wht_amount > 0)
            .where(Payment.status != "CANCELLED")
            .where(Payment.is_deleted == False)  # noqa: E712
            .order_by(Payment.payment_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_non_cancelled(
        self, company_id: UUID, party_type: str | None = None
    ) -> list[Payment]:
        """Every non-cancelled payment (POSTED or ALLOCATED) — the candidate
        set for ``PaymentService.list_unallocated_payments()`` to further
        filter down by actual remaining credit balance. status alone cannot
        distinguish "not yet allocated at all" from "fully consumed" once a
        payment has any allocation applied (both are ALLOCATED) — that
        distinction requires the paired AR/APTransaction's outstanding
        balance, which lives outside this repository's table.
        """
        stmt = (
            select(Payment)
            .where(Payment.company_id == company_id)
            .where(Payment.status != "CANCELLED")
            .where(Payment.is_deleted == False)  # noqa: E712
            .order_by(Payment.payment_date)
        )
        if party_type is not None:
            stmt = stmt.where(Payment.party_type == party_type)
        return list(self.db.execute(stmt).scalars().all())


class PaymentAllocationLineRepository(BaseAccountingRepository[PaymentAllocationLine]):
    """Data-access layer for the ``accounting_payment_allocation_lines`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PaymentAllocationLine)

    def find_by_payment(
        self, company_id: UUID, payment_id: UUID
    ) -> list[PaymentAllocationLine]:
        stmt = (
            select(PaymentAllocationLine)
            .where(PaymentAllocationLine.company_id == company_id)
            .where(PaymentAllocationLine.payment_id == payment_id)
            .where(PaymentAllocationLine.is_deleted == False)  # noqa: E712
            .order_by(PaymentAllocationLine.allocated_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_ar_transaction(
        self, company_id: UUID, ar_transaction_id: UUID
    ) -> list[PaymentAllocationLine]:
        stmt = (
            select(PaymentAllocationLine)
            .where(PaymentAllocationLine.company_id == company_id)
            .where(PaymentAllocationLine.ar_transaction_id == ar_transaction_id)
            .where(PaymentAllocationLine.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_ap_transaction(
        self, company_id: UUID, ap_transaction_id: UUID
    ) -> list[PaymentAllocationLine]:
        stmt = (
            select(PaymentAllocationLine)
            .where(PaymentAllocationLine.company_id == company_id)
            .where(PaymentAllocationLine.ap_transaction_id == ap_transaction_id)
            .where(PaymentAllocationLine.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class PaymentRefundRepository(BaseAccountingRepository[PaymentRefund]):
    """Data-access layer for the ``accounting_payment_refunds`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PaymentRefund)

    def find_by_payment(
        self, company_id: UUID, original_payment_id: UUID
    ) -> list[PaymentRefund]:
        stmt = (
            select(PaymentRefund)
            .where(PaymentRefund.company_id == company_id)
            .where(PaymentRefund.original_payment_id == original_payment_id)
            .where(PaymentRefund.is_deleted == False)  # noqa: E712
            .order_by(PaymentRefund.refund_date)
        )
        return list(self.db.execute(stmt).scalars().all())

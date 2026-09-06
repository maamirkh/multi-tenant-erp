"""Repositories for Phase 2 Supplier enrichment entities.

Covers:
  - CreditLimitRepository    — credit limit per supplier
  - BankDetailsRepository    — bank details (Finance Manager restricted)
  - SupplierRatingRepository — rating records
  - SupplierDocumentRepository — compliance documents
  - SupplierLeadTimeRepository — lead times

All repositories enforce company_id isolation via BasePurchaseRepository.

Spec ref: specs/006-purchase-management/data-model.md §Supplier Aggregate (Phases 2–3)
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.purchase.models.supplier_enrichment import (
    BankDetails,
    CreditLimit,
    SupplierDocument,
    SupplierLeadTime,
    SupplierRating,
)
from modules.purchase.repositories import BasePurchaseRepository


class CreditLimitRepository(BasePurchaseRepository[CreditLimit]):
    """Data-access layer for the ``credit_limits`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CreditLimit)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> CreditLimit | None:
        """Return the active credit limit for a supplier, or None."""
        stmt = (
            select(CreditLimit)
            .where(CreditLimit.company_id == company_id)
            .where(CreditLimit.supplier_id == str(supplier_id))
            .where(CreditLimit.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()


class BankDetailsRepository(BasePurchaseRepository[BankDetails]):
    """Data-access layer for the ``bank_details`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=BankDetails)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[BankDetails]:
        """Return all active bank details records for a supplier."""
        stmt = (
            select(BankDetails)
            .where(BankDetails.company_id == company_id)
            .where(BankDetails.supplier_id == str(supplier_id))
            .where(BankDetails.is_deleted == False)  # noqa: E712
            .order_by(BankDetails.is_primary.desc(), BankDetails.bank_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def clear_primary(self, company_id: UUID, supplier_id: UUID) -> None:
        """Set is_primary=False for all bank details of a supplier."""
        records = self.get_for_supplier(company_id=company_id, supplier_id=supplier_id)
        for r in records:
            if r.is_primary:
                r.is_primary = False
        self.db.flush()


class SupplierRatingRepository(BasePurchaseRepository[SupplierRating]):
    """Data-access layer for the ``supplier_ratings`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierRating)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> SupplierRating | None:
        """Return the active rating record for a supplier, or None."""
        stmt = (
            select(SupplierRating)
            .where(SupplierRating.company_id == company_id)
            .where(SupplierRating.supplier_id == str(supplier_id))
            .where(SupplierRating.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()


class SupplierDocumentRepository(BasePurchaseRepository[SupplierDocument]):
    """Data-access layer for the ``supplier_documents`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierDocument)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[SupplierDocument]:
        """Return all active documents for a supplier."""
        stmt = (
            select(SupplierDocument)
            .where(SupplierDocument.company_id == company_id)
            .where(SupplierDocument.supplier_id == str(supplier_id))
            .where(SupplierDocument.is_deleted == False)  # noqa: E712
            .order_by(
                SupplierDocument.expiry_date.asc().nulls_last(),
                SupplierDocument.document_type,
            )
        )
        return list(self.db.execute(stmt).scalars().all())


class SupplierLeadTimeRepository(BasePurchaseRepository[SupplierLeadTime]):
    """Data-access layer for the ``supplier_lead_times`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierLeadTime)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[SupplierLeadTime]:
        """Return all active lead time records for a supplier."""
        stmt = (
            select(SupplierLeadTime)
            .where(SupplierLeadTime.company_id == company_id)
            .where(SupplierLeadTime.supplier_id == str(supplier_id))
            .where(SupplierLeadTime.is_deleted == False)  # noqa: E712
            .order_by(SupplierLeadTime.product_id.asc().nulls_first())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_for_supplier_product(
        self, company_id: UUID, supplier_id: UUID, product_id: UUID | None
    ) -> SupplierLeadTime | None:
        """Return lead time for a specific supplier+product combination, or None."""
        stmt = (
            select(SupplierLeadTime)
            .where(SupplierLeadTime.company_id == company_id)
            .where(SupplierLeadTime.supplier_id == str(supplier_id))
            .where(SupplierLeadTime.is_deleted == False)  # noqa: E712
        )
        if product_id is None:
            stmt = stmt.where(SupplierLeadTime.product_id.is_(None))
        else:
            stmt = stmt.where(SupplierLeadTime.product_id == str(product_id))
        return self.db.execute(stmt).scalars().one_or_none()

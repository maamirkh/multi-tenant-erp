"""Repositories for purchase master data entities.

Covers:
  - SupplierCategoryRepository  — tree CRUD with hierarchy queries
  - PaymentTermsRepository       — code-unique payment terms
  - PurchaseReasonCodeRepository — typed reason codes
  - PurchasePolicyRepository     — company-level policy (singleton per company)

All repositories enforce company_id isolation via BasePurchaseRepository.

Spec ref: specs/006-purchase-management/data-model.md §Master Data Entities
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.purchase.models.policy import PurchasePolicy
from modules.purchase.models.supplier import (
    PaymentTerms,
    PurchaseReasonCode,
    SupplierCategory,
)
from modules.purchase.repositories import BasePurchaseRepository

logger = logging.getLogger(__name__)


class SupplierCategoryRepository(BasePurchaseRepository[SupplierCategory]):
    """Data-access layer for the ``supplier_categories`` table.

    Provides tree-aware queries:
      - ``get_by_code``    — lookup by (company_id, code)
      - ``get_children``   — direct children of a parent category
      - ``get_roots``      — root categories (parent_id IS NULL)
      - ``get_ancestors``  — walk up the tree from a category
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierCategory)

    def get_by_code(self, company_id: UUID, code: str) -> SupplierCategory | None:
        """Return the category with the given code for this company, or None."""
        stmt = (
            select(SupplierCategory)
            .where(SupplierCategory.company_id == company_id)
            .where(SupplierCategory.code == code)
            .where(SupplierCategory.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_children(self, company_id: UUID, parent_id: UUID) -> list[SupplierCategory]:
        """Return direct children of the given parent category."""
        stmt = (
            select(SupplierCategory)
            .where(SupplierCategory.company_id == company_id)
            .where(SupplierCategory.parent_id == str(parent_id))
            .where(SupplierCategory.is_deleted == False)  # noqa: E712
            .order_by(SupplierCategory.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_roots(self, company_id: UUID) -> list[SupplierCategory]:
        """Return all root categories (parent_id IS NULL) for a company."""
        stmt = (
            select(SupplierCategory)
            .where(SupplierCategory.company_id == company_id)
            .where(SupplierCategory.parent_id == None)  # noqa: E711
            .where(SupplierCategory.is_deleted == False)  # noqa: E712
            .order_by(SupplierCategory.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_status(self, company_id: UUID, status: str) -> list[SupplierCategory]:
        """Return all categories filtered by status for a company."""
        stmt = (
            select(SupplierCategory)
            .where(SupplierCategory.company_id == company_id)
            .where(SupplierCategory.status == status)
            .where(SupplierCategory.is_deleted == False)  # noqa: E712
            .order_by(SupplierCategory.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_ancestors(
        self, company_id: UUID, category_id: UUID
    ) -> list[SupplierCategory]:
        """Walk up the tree and return ancestors from root to parent.

        Returns an empty list for root categories.
        """
        ancestors: list[SupplierCategory] = []
        current = self.get_by_id_or_none(id=category_id, company_id=company_id)
        if current is None:
            return ancestors

        visited: set[str] = {str(category_id)}
        while current.parent_id is not None:
            if current.parent_id in visited:
                logger.warning(
                    "Circular reference detected in category tree for company_id=%s",
                    company_id,
                )
                break
            visited.add(current.parent_id)
            parent = self.get_by_id_or_none(
                id=UUID(current.parent_id), company_id=company_id
            )
            if parent is None:
                break
            ancestors.insert(0, parent)
            current = parent

        return ancestors


class PaymentTermsRepository(BasePurchaseRepository[PaymentTerms]):
    """Data-access layer for the ``payment_terms`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PaymentTerms)

    def get_by_code(self, company_id: UUID, code: str) -> PaymentTerms | None:
        """Return the payment terms with the given code for this company, or None."""
        stmt = (
            select(PaymentTerms)
            .where(PaymentTerms.company_id == company_id)
            .where(PaymentTerms.code == code)
            .where(PaymentTerms.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active(self, company_id: UUID) -> list[PaymentTerms]:
        """Return all active payment terms for a company."""
        stmt = (
            select(PaymentTerms)
            .where(PaymentTerms.company_id == company_id)
            .where(PaymentTerms.is_active == True)  # noqa: E712
            .where(PaymentTerms.is_deleted == False)  # noqa: E712
            .order_by(PaymentTerms.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class PurchaseReasonCodeRepository(BasePurchaseRepository[PurchaseReasonCode]):
    """Data-access layer for the ``purchase_reason_codes`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PurchaseReasonCode)

    def get_by_code(
        self, company_id: UUID, code: str, reason_type: str
    ) -> PurchaseReasonCode | None:
        """Return the reason code matching (company_id, code, reason_type), or None."""
        stmt = (
            select(PurchaseReasonCode)
            .where(PurchaseReasonCode.company_id == company_id)
            .where(PurchaseReasonCode.code == code)
            .where(PurchaseReasonCode.reason_type == reason_type)
            .where(PurchaseReasonCode.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_type(
        self, company_id: UUID, reason_type: str
    ) -> list[PurchaseReasonCode]:
        """Return all active reason codes of the given type for a company."""
        stmt = (
            select(PurchaseReasonCode)
            .where(PurchaseReasonCode.company_id == company_id)
            .where(PurchaseReasonCode.reason_type == reason_type)
            .where(PurchaseReasonCode.is_active == True)  # noqa: E712
            .where(PurchaseReasonCode.is_deleted == False)  # noqa: E712
            .order_by(PurchaseReasonCode.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class PurchasePolicyRepository(BasePurchaseRepository[PurchasePolicy]):
    """Data-access layer for the ``purchase_policies`` table.

    One policy record per company. Uses upsert semantics for policy management.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PurchasePolicy)

    def get_for_company(self, company_id: UUID) -> PurchasePolicy | None:
        """Return the procurement policy for this company, or None if not yet configured."""
        stmt = (
            select(PurchasePolicy)
            .where(PurchasePolicy.company_id == company_id)
            .where(PurchasePolicy.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

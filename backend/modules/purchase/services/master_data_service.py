"""Master data application services for purchase Phase 0.

Services:
  - SupplierCategoryService  — CRUD for the supplier category tree
  - PaymentTermsService      — CRUD for payment terms master
  - PurchaseReasonCodeService — CRUD for typed reason codes

All services enforce company_id isolation via their respective repositories.

Spec ref: specs/006-purchase-management/data-model.md §Master Data Entities
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.purchase.constants import SUPPLIER_CATEGORY_MAX_DEPTH
from modules.purchase.models.supplier import (
    PaymentTerms,
    PurchaseReasonCode,
    SupplierCategory,
)
from modules.purchase.repositories.master import (
    PaymentTermsRepository,
    PurchaseReasonCodeRepository,
    SupplierCategoryRepository,
)

logger = logging.getLogger(__name__)

VALID_REASON_TYPES = ("RETURN", "CANCELLATION", "REJECTION", "GENERAL")


class SupplierCategoryService:
    """Application service for supplier category tree management.

    Enforces:
      - Code uniqueness per company
      - Parent must belong to same company
      - No circular parent references
      - Tree depth ≤ SUPPLIER_CATEGORY_MAX_DEPTH
    """

    def __init__(self, db: Session, category_repo: SupplierCategoryRepository) -> None:
        self.db = db
        self._repo = category_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        parent_id: UUID | None = None,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> SupplierCategory:
        """Create a new supplier category.

        Raises:
            ConflictException:   If code already exists for this company.
            NotFoundException:   If parent_id is provided but not found.
            ValueError:          If tree depth would exceed the maximum.
        """
        existing = self._repo.get_by_code(company_id=company_id, code=code)
        if existing is not None:
            raise ConflictException(
                message=f"Supplier category code '{code}' already exists.",
                details={"code": code},
            )

        if parent_id is not None:
            parent = self._repo.get_by_id_or_none(id=parent_id, company_id=company_id)
            if parent is None:
                raise NotFoundException(
                    message=f"Parent category '{parent_id}' not found.",
                    details={"parent_id": str(parent_id)},
                )

            # Check depth constraint
            ancestors = self._repo.get_ancestors(
                company_id=company_id, category_id=parent_id
            )
            # depth = len(ancestors) + 1 (for parent) + 1 (for new child)
            new_depth = len(ancestors) + 2
            if new_depth > SUPPLIER_CATEGORY_MAX_DEPTH:
                raise ValueError(
                    f"Cannot create category: maximum tree depth of "
                    f"{SUPPLIER_CATEGORY_MAX_DEPTH} would be exceeded. "
                    f"Current depth at parent: {len(ancestors) + 1}."
                )

        category = SupplierCategory(
            company_id=company_id,
            code=code,
            name=name,
            parent_id=str(parent_id) if parent_id is not None else None,
            description=description,
            status="active",
            created_by=actor_id,
        )
        result = self._repo.create(category)
        logger.info("SupplierCategory created: code=%s company=%s", code, company_id)
        return result

    def update(
        self,
        category_id: UUID,
        company_id: UUID,
        name: str | None = None,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> SupplierCategory:
        """Update mutable fields of a supplier category."""
        category = self._repo.get_by_id(id=category_id, company_id=company_id)

        if name is not None:
            category.name = name
        if description is not None:
            category.description = description

        return self._repo.update(category)

    def deactivate(self, category_id: UUID, company_id: UUID) -> SupplierCategory:
        """Deactivate a supplier category."""
        category = self._repo.get_by_id(id=category_id, company_id=company_id)
        category.status = "inactive"
        return self._repo.update(category)

    def activate(self, category_id: UUID, company_id: UUID) -> SupplierCategory:
        """Reactivate a supplier category."""
        category = self._repo.get_by_id(id=category_id, company_id=company_id)
        category.status = "active"
        return self._repo.update(category)

    def delete(self, category_id: UUID, company_id: UUID) -> None:
        """Soft-delete a supplier category.

        Note: Does not cascade-delete children; children retain their parent_id
        but become orphaned in the tree. Callers should check for children first.
        """
        children = self._repo.get_children(company_id=company_id, parent_id=category_id)
        if children:
            raise ConflictException(
                message="Cannot delete a category that has active sub-categories.",
                details={"children_count": len(children)},
            )
        self._repo.soft_delete(id=category_id, company_id=company_id)


class PaymentTermsService:
    """Application service for payment terms master management."""

    def __init__(self, db: Session, terms_repo: PaymentTermsRepository) -> None:
        self.db = db
        self._repo = terms_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        net_days: int,
        discount_days: int | None = None,
        discount_percent: float | None = None,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> PaymentTerms:
        """Create new payment terms.

        Raises:
            ConflictException: If code already exists for this company.
            ValueError:        If net_days < 0 or discount constraints violated.
        """
        if net_days < 0:
            raise ValueError("net_days must be >= 0.")

        existing = self._repo.get_by_code(company_id=company_id, code=code)
        if existing is not None:
            raise ConflictException(
                message=f"Payment terms code '{code}' already exists.",
                details={"code": code},
            )

        from decimal import Decimal

        terms = PaymentTerms(
            company_id=company_id,
            code=code,
            name=name,
            net_days=net_days,
            discount_days=discount_days,
            discount_percent=(
                Decimal(str(discount_percent)) if discount_percent is not None else None
            ),
            description=description,
            is_active=True,
            created_by=actor_id,
        )
        return self._repo.create(terms)

    def update(
        self,
        terms_id: UUID,
        company_id: UUID,
        name: str | None = None,
        net_days: int | None = None,
        discount_days: int | None = None,
        discount_percent: float | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> PaymentTerms:
        """Update payment terms."""
        terms = self._repo.get_by_id(id=terms_id, company_id=company_id)

        if name is not None:
            terms.name = name
        if net_days is not None:
            if net_days < 0:
                raise ValueError("net_days must be >= 0.")
            terms.net_days = net_days
        if discount_days is not None:
            terms.discount_days = discount_days
        if discount_percent is not None:
            from decimal import Decimal

            terms.discount_percent = Decimal(str(discount_percent))
        if description is not None:
            terms.description = description
        if is_active is not None:
            terms.is_active = is_active

        return self._repo.update(terms)

    def delete(self, terms_id: UUID, company_id: UUID) -> None:
        """Soft-delete payment terms."""
        self._repo.soft_delete(id=terms_id, company_id=company_id)


class PurchaseReasonCodeService:
    """Application service for purchase reason code management."""

    def __init__(self, db: Session, reason_repo: PurchaseReasonCodeRepository) -> None:
        self.db = db
        self._repo = reason_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        reason_type: str,
        actor_id: UUID | None = None,
    ) -> PurchaseReasonCode:
        """Create a new purchase reason code.

        Raises:
            ValueError:        If reason_type is not valid.
            ConflictException: If code already exists for (company_id, reason_type).
        """
        if reason_type not in VALID_REASON_TYPES:
            raise ValueError(
                f"Invalid reason_type: '{reason_type}'. Valid: {VALID_REASON_TYPES}"
            )

        existing = self._repo.get_by_code(
            company_id=company_id, code=code, reason_type=reason_type
        )
        if existing is not None:
            raise ConflictException(
                message=f"Reason code '{code}' of type '{reason_type}' already exists.",
                details={"code": code, "reason_type": reason_type},
            )

        rc = PurchaseReasonCode(
            company_id=company_id,
            code=code,
            name=name,
            reason_type=reason_type,
            is_active=True,
            created_by=actor_id,
        )
        return self._repo.create(rc)

    def update(
        self,
        code_id: UUID,
        company_id: UUID,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> PurchaseReasonCode:
        """Update a reason code."""
        rc = self._repo.get_by_id(id=code_id, company_id=company_id)

        if name is not None:
            rc.name = name
        if is_active is not None:
            rc.is_active = is_active

        return self._repo.update(rc)

    def delete(self, code_id: UUID, company_id: UUID) -> None:
        """Soft-delete a reason code."""
        self._repo.soft_delete(id=code_id, company_id=company_id)

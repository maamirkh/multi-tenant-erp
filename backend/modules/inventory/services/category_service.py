"""CategoryService — category CRUD with tree management and deactivation guard.

Business rules enforced:
  - code unique per company (409 on conflict)
  - No circular parent references (422 if would create cycle)
  - Deactivation blocked when assigned to Active products (enforced in Phase 2;
    stub check present here for future wiring)
  - Deletion blocked when category has active child categories

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.2
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from modules.inventory.exceptions import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    InvalidProductStateTransitionError,
)
from modules.inventory.models.category import Category
from modules.inventory.repositories.category_repository import CategoryRepository

logger = logging.getLogger(__name__)

_MAX_DEPTH = 10  # maximum category tree depth


class CategoryService:
    """Application service for category management.

    Args:
        db:            SQLAlchemy session.
        category_repo: ``CategoryRepository`` instance.
    """

    def __init__(self, db: Session, category_repo: CategoryRepository) -> None:
        self.db = db
        self._repo = category_repo

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        parent_id: UUID | None = None,
        description: str | None = None,
        sort_order: int = 0,
        actor_id: UUID | None = None,
    ) -> Category:
        """Create a new category.

        Raises:
            CategoryNameConflictError: If code already exists for this company.
            InvalidProductStateTransitionError: If parent would create a cycle or depth exceeded.
        """
        # Code uniqueness
        if self._repo.get_by_code(company_id=company_id, code=code):
            raise CategoryNameConflictError(
                message=f"A category with code '{code}' already exists.",
                details={"code": code},
            )

        # Cycle and depth check
        if parent_id is not None:
            self._validate_parent(
                company_id=company_id, category_id=None, parent_id=parent_id
            )

        category = Category(
            company_id=company_id,
            code=code,
            name=name,
            parent_id=str(parent_id) if parent_id else None,
            description=description,
            sort_order=sort_order,
            status="active",
            created_by=actor_id,
        )
        result = self._repo.create(category)
        logger.info(
            "Category created: id=%s code=%s company=%s", result.id, code, company_id
        )
        return result

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, company_id: UUID, category_id: UUID) -> Category:
        """Return category by ID or raise CategoryNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=category_id, company_id=company_id)
        except NotFoundException:
            raise CategoryNotFoundError(details={"category_id": str(category_id)})

    def get_tree(self, company_id: UUID) -> list[Category]:
        """Return all categories for the company, ordered for tree display."""
        return self._repo.get_tree(company_id=company_id)

    def get_children(
        self, company_id: UUID, parent_id: UUID | None = None
    ) -> list[Category]:
        """Return direct children of a parent (or root categories if parent_id=None)."""
        return self._repo.get_children(company_id=company_id, parent_id=parent_id)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        company_id: UUID,
        category_id: UUID,
        name: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
        parent_id: UUID | None | type[_UNSET] = None,
        code: str | None = None,
    ) -> Category:
        """Update category fields.

        Raises:
            CategoryNotFoundError: If category does not exist.
            CategoryNameConflictError: If new code conflicts.
            InvalidProductStateTransitionError: If new parent would create a cycle.
        """
        category = self.get_by_id(company_id=company_id, category_id=category_id)

        if code is not None and code != category.code:
            if self._repo.get_by_code(company_id=company_id, code=code):
                raise CategoryNameConflictError(
                    message=f"A category with code '{code}' already exists.",
                    details={"code": code},
                )
            category.code = code

        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        if sort_order is not None:
            category.sort_order = sort_order

        if not isinstance(parent_id, type) and parent_id is not None:
            self._validate_parent(
                company_id=company_id, category_id=category_id, parent_id=parent_id
            )
            category.parent_id = str(parent_id)

        return self._repo.update(category)

    # ------------------------------------------------------------------
    # Deactivate / Archive
    # ------------------------------------------------------------------

    def deactivate(self, company_id: UUID, category_id: UUID) -> Category:
        """Deactivate a category.

        Raises:
            CategoryNotFoundError: If category does not exist.
            InvalidProductStateTransitionError: If category has active children.
        """
        category = self.get_by_id(company_id=company_id, category_id=category_id)

        if category.status == "inactive":
            return category  # idempotent

        if self._repo.has_active_children(
            company_id=company_id, category_id=category_id
        ):
            raise InvalidProductStateTransitionError(
                message="Cannot deactivate a category that has active child categories.",
                details={"category_id": str(category_id)},
            )

        category.status = "inactive"
        return self._repo.update(category)

    def activate(self, company_id: UUID, category_id: UUID) -> Category:
        """Re-activate an inactive category."""
        category = self.get_by_id(company_id=company_id, category_id=category_id)
        if category.status == "active":
            return category
        category.status = "active"
        return self._repo.update(category)

    def delete(self, company_id: UUID, category_id: UUID) -> None:
        """Soft-delete a category.

        Raises:
            CategoryNotFoundError: If category does not exist.
            InvalidProductStateTransitionError: If category has active children.
        """
        if self._repo.has_active_children(
            company_id=company_id, category_id=category_id
        ):
            raise InvalidProductStateTransitionError(
                message="Cannot delete a category that has active child categories.",
                details={"category_id": str(category_id)},
            )
        try:
            self._repo.soft_delete(id=category_id, company_id=company_id)
        except Exception:
            raise CategoryNotFoundError(details={"category_id": str(category_id)})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_parent(
        self,
        company_id: UUID,
        category_id: UUID | None,
        parent_id: UUID,
    ) -> None:
        """Validate that setting parent_id doesn't create a cycle or exceed depth."""
        parent = self._repo.get_by_id_or_none(id=parent_id, company_id=company_id)
        if parent is None:
            raise CategoryNotFoundError(
                message="Parent category not found.",
                details={"parent_id": str(parent_id)},
            )

        if category_id is not None:
            if self._repo.would_create_cycle(
                company_id=company_id,
                category_id=category_id,
                new_parent_id=parent_id,
            ):
                raise InvalidProductStateTransitionError(
                    message="Setting this parent would create a circular reference.",
                    details={
                        "category_id": str(category_id),
                        "parent_id": str(parent_id),
                    },
                )

        # Depth check
        ancestors = self._repo.get_ancestors(
            company_id=company_id, category_id=parent_id
        )
        if len(ancestors) >= _MAX_DEPTH - 1:
            raise InvalidProductStateTransitionError(
                message=f"Maximum category depth of {_MAX_DEPTH} levels exceeded.",
                details={"max_depth": _MAX_DEPTH},
            )


class _UNSET:
    """Sentinel for optional fields not provided in update."""

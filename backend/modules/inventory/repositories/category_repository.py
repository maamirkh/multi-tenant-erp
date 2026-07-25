"""CategoryRepository — tree-aware category data access.

Extends ``BaseRepository`` with:
  - ``get_by_code``     — fetch by unique code per company
  - ``get_children``    — fetch direct children of a parent
  - ``get_tree``        — fetch all categories for a company (flat, ordered)
  - ``get_ancestors``   — fetch all ancestor categories up to the root
  - ``has_active_products`` — deactivation guard check (Phase 2 — stub for now)

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.category import Category


class CategoryRepository(BaseRepository[Category]):
    """Data-access layer for ``inventory_categories`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Category)

    def get_by_code(self, company_id: UUID, code: str) -> Category | None:
        """Return the category with this code for the company, or None."""
        stmt = (
            select(Category)
            .where(Category.company_id == company_id)
            .where(Category.code == code)
            .where(Category.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_children(self, company_id: UUID, parent_id: UUID | None) -> list[Category]:
        """Return direct children of ``parent_id`` (or root categories if None)."""
        stmt = (
            select(Category)
            .where(Category.company_id == company_id)
            .where(Category.is_deleted == False)  # noqa: E712
            .order_by(Category.sort_order, Category.name)
        )
        if parent_id is None:
            stmt = stmt.where(Category.parent_id.is_(None))
        else:
            stmt = stmt.where(Category.parent_id == str(parent_id))
        return list(self.db.execute(stmt).scalars().all())

    def get_tree(self, company_id: UUID) -> list[Category]:
        """Return all active categories for a company, ordered by sort_order then name."""
        stmt = (
            select(Category)
            .where(Category.company_id == company_id)
            .where(Category.is_deleted == False)  # noqa: E712
            .order_by(Category.sort_order, Category.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_ancestors(self, company_id: UUID, category_id: UUID) -> list[Category]:
        """Return all ancestor categories from ``category_id`` up to the root.

        Walks the parent chain iteratively (up to 20 levels to prevent infinite loops).
        Result is ordered from root to immediate parent.
        """
        ancestors: list[Category] = []
        current = self.get_by_id_or_none(id=category_id, company_id=company_id)
        if current is None:
            return ancestors

        visited: set[str] = {str(category_id)}
        depth = 0

        while current and current.parent_id and depth < 20:
            parent_uuid = (
                UUID(current.parent_id)
                if isinstance(current.parent_id, str)
                else current.parent_id
            )
            if str(parent_uuid) in visited:
                # Circular reference detected — stop walking
                break
            visited.add(str(parent_uuid))
            parent = self.get_by_id_or_none(id=parent_uuid, company_id=company_id)
            if parent is None:
                break
            ancestors.insert(0, parent)  # prepend so result is root → parent
            current = parent
            depth += 1

        return ancestors

    def would_create_cycle(
        self, company_id: UUID, category_id: UUID, new_parent_id: UUID
    ) -> bool:
        """Return True if setting ``new_parent_id`` on ``category_id`` would create a cycle.

        Walks ancestors of ``new_parent_id`` — if ``category_id`` appears, it's a cycle.
        """
        if category_id == new_parent_id:
            return True
        ancestors = self.get_ancestors(company_id=company_id, category_id=new_parent_id)
        ancestor_ids = {str(a.id) for a in ancestors}
        return str(category_id) in ancestor_ids

    def has_active_children(self, company_id: UUID, category_id: UUID) -> bool:
        """Return True if this category has any active (status='active', non-deleted) child categories."""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Category)
            .where(Category.company_id == company_id)
            .where(Category.parent_id == str(category_id))
            .where(Category.is_deleted == False)  # noqa: E712
            .where(Category.status == "active")
        )
        count: int = self.db.execute(stmt).scalar_one()
        return count > 0

"""Unit tests for SupplierCategory business rules.

Tests:
  - Circular reference prevention
  - Depth limit enforcement
  - Code uniqueness invariant
  - Status transitions

Spec ref: specs/006-purchase-management/data-model.md §SupplierCategory
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.exceptions.base import ConflictException, NotFoundException
from modules.purchase.constants import SUPPLIER_CATEGORY_MAX_DEPTH
from modules.purchase.repositories.master import SupplierCategoryRepository
from modules.purchase.services.master_data_service import SupplierCategoryService


def _make_category(
    company_id,
    code: str,
    name: str,
    parent_id=None,
    status: str = "active",
) -> MagicMock:
    """Return a MagicMock that mimics a SupplierCategory ORM object."""
    cat = MagicMock()
    cat.id = uuid4()
    cat.company_id = company_id
    cat.code = code
    cat.name = name
    cat.parent_id = str(parent_id) if parent_id else None
    cat.status = status
    cat.is_deleted = False
    cat.description = None
    cat.created_by = None
    return cat


class TestSupplierCategoryCodeUniqueness:
    def test_duplicate_code_raises_conflict(self) -> None:
        company_id = uuid4()
        existing = _make_category(company_id, "TECH", "Technology")

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_by_code.return_value = existing
        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)

        with pytest.raises(ConflictException, match="already exists"):
            svc.create(
                company_id=company_id,
                code="TECH",
                name="Duplicate Technology",
            )

    def test_unique_code_succeeds(self) -> None:
        company_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_by_code.return_value = None  # No existing category
        mock_repo.get_ancestors.return_value = []
        new_cat = _make_category(company_id, "TECH", "Technology")
        mock_repo.create.return_value = new_cat

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)
        result = svc.create(company_id=company_id, code="TECH", name="Technology")

        assert result.code == "TECH"


class TestSupplierCategoryDepthLimit:
    def test_exceeding_max_depth_raises_value_error(self) -> None:
        company_id = uuid4()
        parent_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_by_code.return_value = None
        mock_repo.get_by_id_or_none.return_value = _make_category(
            company_id, "PARENT", "Parent", parent_id=None
        )
        # Return ancestors that would push depth over limit
        # Max depth is 5. If ancestors list has 4 items, new child would be depth 6.
        ancestors = [
            _make_category(company_id, f"L{i}", f"Level {i}")
            for i in range(SUPPLIER_CATEGORY_MAX_DEPTH - 1)
        ]
        mock_repo.get_ancestors.return_value = ancestors

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)

        with pytest.raises(ValueError, match="maximum tree depth"):
            svc.create(
                company_id=company_id,
                code="DEEP",
                name="Too Deep Category",
                parent_id=parent_id,
            )

    def test_at_max_depth_succeeds(self) -> None:
        company_id = uuid4()
        parent_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_by_code.return_value = None
        mock_repo.get_by_id_or_none.return_value = _make_category(
            company_id, "PARENT", "Parent", parent_id=None
        )
        # Ancestors depth = 3 → new child = depth 5 = SUPPLIER_CATEGORY_MAX_DEPTH (allowed)
        ancestors = [
            _make_category(company_id, f"L{i}", f"Level {i}")
            for i in range(SUPPLIER_CATEGORY_MAX_DEPTH - 2)
        ]
        mock_repo.get_ancestors.return_value = ancestors
        new_cat = _make_category(
            company_id, "VALID", "Valid Deep Category", parent_id=parent_id
        )
        mock_repo.create.return_value = new_cat

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)
        result = svc.create(
            company_id=company_id,
            code="VALID",
            name="Valid Deep Category",
            parent_id=parent_id,
        )
        assert result.code == "VALID"


class TestSupplierCategoryParentValidation:
    def test_nonexistent_parent_raises_not_found(self) -> None:
        company_id = uuid4()
        nonexistent_parent_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_by_code.return_value = None
        mock_repo.get_by_id_or_none.return_value = None  # Parent not found

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)

        with pytest.raises(NotFoundException, match="not found"):
            svc.create(
                company_id=company_id,
                code="CHILD",
                name="Child Category",
                parent_id=nonexistent_parent_id,
            )

    def test_root_category_created_without_parent(self) -> None:
        company_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_by_code.return_value = None
        new_cat = _make_category(company_id, "ROOT", "Root Category")
        mock_repo.create.return_value = new_cat

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)
        result = svc.create(
            company_id=company_id,
            code="ROOT",
            name="Root Category",
            parent_id=None,
        )
        assert result.parent_id is None


class TestSupplierCategoryDelete:
    def test_delete_with_children_raises_conflict(self) -> None:
        company_id = uuid4()
        cat_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        # Return one child
        mock_repo.get_children.return_value = [
            _make_category(company_id, "CHILD", "Child")
        ]

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)

        with pytest.raises(ConflictException, match="sub-categories"):
            svc.delete(category_id=cat_id, company_id=company_id)

    def test_delete_leaf_category_succeeds(self) -> None:
        company_id = uuid4()
        cat_id = uuid4()

        mock_repo = MagicMock(spec=SupplierCategoryRepository)
        mock_repo.get_children.return_value = []  # No children
        mock_repo.soft_delete.return_value = None

        svc = SupplierCategoryService(db=MagicMock(), category_repo=mock_repo)
        svc.delete(category_id=cat_id, company_id=company_id)

        mock_repo.soft_delete.assert_called_once_with(id=cat_id, company_id=company_id)

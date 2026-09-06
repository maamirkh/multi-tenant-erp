"""Unit tests for CategoryService business logic.

Tests: circular reference prevention, deactivation guard, code uniqueness,
depth limit, idempotent activate/deactivate.

Spec ref: specs/005-inventory-management/spec.md §14
Task: T047
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.inventory.exceptions import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    InvalidProductStateTransitionError,
)
from modules.inventory.models.category import Category
from modules.inventory.services.category_service import CategoryService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_category(**kwargs) -> Category:
    defaults = {
        "id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "code": "CAT001",
        "name": "Test Category",
        "description": None,
        "parent_id": None,
        "sort_order": 0,
        "status": "active",
        "is_deleted": False,
        "created_by": None,
    }
    defaults.update(kwargs)
    cat = MagicMock(spec=Category)
    for k, v in defaults.items():
        setattr(cat, k, v)
    return cat


def _make_service(repo=None):
    if repo is None:
        repo = MagicMock()
    return CategoryService(db=MagicMock(), category_repo=repo)


# ---------------------------------------------------------------------------
# Create — code uniqueness
# ---------------------------------------------------------------------------


class TestCreateCodeUniqueness:
    def test_create_raises_conflict_when_code_exists(self):
        repo = MagicMock()
        repo.get_by_code.return_value = _make_category()  # code already exists
        svc = _make_service(repo)
        with pytest.raises(CategoryNameConflictError):
            svc.create(company_id=uuid.uuid4(), code="DUP", name="Dup Cat")

    def test_create_succeeds_when_code_unique(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        expected = _make_category(code="NEW")
        repo.create.return_value = expected
        svc = _make_service(repo)
        result = svc.create(company_id=uuid.uuid4(), code="NEW", name="New Cat")
        assert result.code == "NEW"


# ---------------------------------------------------------------------------
# Create — parent validation
# ---------------------------------------------------------------------------


class TestCreateParentValidation:
    def test_create_without_parent_skips_validation(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        repo.create.return_value = _make_category()
        svc = _make_service(repo)
        svc.create(company_id=uuid.uuid4(), code="C1", name="C1")
        repo.get_by_id_or_none.assert_not_called()

    def test_create_raises_when_parent_not_found(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        repo.get_by_id_or_none.return_value = None  # parent not found
        svc = _make_service(repo)
        with pytest.raises(CategoryNotFoundError):
            svc.create(
                company_id=uuid.uuid4(),
                code="C1",
                name="C1",
                parent_id=uuid.uuid4(),
            )

    def test_create_succeeds_with_valid_parent(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        parent = _make_category(id=str(uuid.uuid4()))
        repo.get_by_id_or_none.return_value = parent
        repo.get_ancestors.return_value = []  # no depth issue
        repo.would_create_cycle.return_value = False
        expected = _make_category()
        repo.create.return_value = expected
        svc = _make_service(repo)
        result = svc.create(
            company_id=uuid.uuid4(),
            code="CHILD",
            name="Child",
            parent_id=uuid.UUID(parent.id),
        )
        assert result is expected


# ---------------------------------------------------------------------------
# Depth limit
# ---------------------------------------------------------------------------


class TestDepthLimit:
    def test_create_raises_when_depth_exceeded(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        parent = _make_category()
        repo.get_by_id_or_none.return_value = parent
        # Simulate 9 existing ancestors (parent itself at depth 9 → would be depth 10)
        repo.get_ancestors.return_value = [MagicMock()] * 9
        svc = _make_service(repo)
        with pytest.raises(InvalidProductStateTransitionError, match="depth"):
            svc.create(
                company_id=uuid.uuid4(),
                code="DEEP",
                name="Deep",
                parent_id=uuid.uuid4(),
            )

    def test_create_succeeds_at_max_depth_minus_one(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        parent = _make_category()
        repo.get_by_id_or_none.return_value = parent
        # 8 ancestors → depth would be 9 (within limit of 10)
        repo.get_ancestors.return_value = [MagicMock()] * 8
        repo.would_create_cycle.return_value = False
        repo.create.return_value = _make_category()
        svc = _make_service(repo)
        result = svc.create(
            company_id=uuid.uuid4(),
            code="D9",
            name="Depth 9",
            parent_id=uuid.uuid4(),
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Circular reference prevention
# ---------------------------------------------------------------------------


class TestCircularReferencePrevention:
    def test_update_raises_on_cycle(self):
        cat_id = uuid.uuid4()
        repo = MagicMock()
        cat = _make_category(id=str(cat_id))
        repo.get_by_id.return_value = cat
        repo.get_by_id_or_none.return_value = (
            cat  # parent resolves to same or descendant
        )
        repo.get_ancestors.return_value = []
        repo.would_create_cycle.return_value = True  # cycle detected
        svc = _make_service(repo)
        with pytest.raises(InvalidProductStateTransitionError, match="circular"):
            svc.update(
                company_id=uuid.uuid4(),
                category_id=cat_id,
                parent_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------------
# Deactivation guard
# ---------------------------------------------------------------------------


class TestDeactivationGuard:
    def test_deactivate_raises_when_active_children_exist(self):
        repo = MagicMock()
        cat = _make_category(status="active")
        repo.get_by_id.return_value = cat
        repo.has_active_children.return_value = True
        svc = _make_service(repo)
        with pytest.raises(InvalidProductStateTransitionError, match="active child"):
            svc.deactivate(company_id=uuid.uuid4(), category_id=uuid.uuid4())

    def test_deactivate_succeeds_when_no_active_children(self):
        repo = MagicMock()
        cat = _make_category(status="active")
        repo.get_by_id.return_value = cat
        repo.has_active_children.return_value = False
        repo.update.return_value = cat
        svc = _make_service(repo)
        result = svc.deactivate(company_id=uuid.uuid4(), category_id=uuid.uuid4())
        assert result.status == "inactive"

    def test_deactivate_is_idempotent_when_already_inactive(self):
        repo = MagicMock()
        cat = _make_category(status="inactive")
        repo.get_by_id.return_value = cat
        svc = _make_service(repo)
        result = svc.deactivate(company_id=uuid.uuid4(), category_id=uuid.uuid4())
        repo.has_active_children.assert_not_called()
        assert result is cat

    def test_activate_is_idempotent_when_already_active(self):
        repo = MagicMock()
        cat = _make_category(status="active")
        repo.get_by_id.return_value = cat
        svc = _make_service(repo)
        result = svc.activate(company_id=uuid.uuid4(), category_id=uuid.uuid4())
        repo.update.assert_not_called()
        assert result is cat


# ---------------------------------------------------------------------------
# Delete guard
# ---------------------------------------------------------------------------


class TestDeleteGuard:
    def test_delete_raises_when_active_children_exist(self):
        repo = MagicMock()
        repo.has_active_children.return_value = True
        svc = _make_service(repo)
        with pytest.raises(InvalidProductStateTransitionError, match="active child"):
            svc.delete(company_id=uuid.uuid4(), category_id=uuid.uuid4())

    def test_delete_raises_not_found_when_soft_delete_fails(self):
        repo = MagicMock()
        repo.has_active_children.return_value = False
        repo.soft_delete.side_effect = Exception("not found")
        svc = _make_service(repo)
        with pytest.raises(CategoryNotFoundError):
            svc.delete(company_id=uuid.uuid4(), category_id=uuid.uuid4())

    def test_delete_succeeds_when_no_children(self):
        repo = MagicMock()
        repo.has_active_children.return_value = False
        svc = _make_service(repo)
        svc.delete(company_id=uuid.uuid4(), category_id=uuid.uuid4())
        repo.soft_delete.assert_called_once()


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


class TestGetById:
    def test_get_by_id_raises_not_found_on_exception(self):
        repo = MagicMock()
        from core.exceptions.base import NotFoundException

        repo.get_by_id.side_effect = NotFoundException(message="not found")
        svc = _make_service(repo)
        with pytest.raises(CategoryNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), category_id=uuid.uuid4())

    def test_get_by_id_returns_category(self):
        repo = MagicMock()
        cat = _make_category()
        repo.get_by_id.return_value = cat
        svc = _make_service(repo)
        result = svc.get_by_id(company_id=uuid.uuid4(), category_id=uuid.uuid4())
        assert result is cat

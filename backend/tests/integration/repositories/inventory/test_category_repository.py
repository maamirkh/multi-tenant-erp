"""Integration tests for CategoryRepository.

Tests: tree query, parent/child operations, tenant isolation, soft-delete,
ancestor walk, cycle detection, active children check.

Task: T049
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.inventory.models.category import Category
from modules.inventory.repositories.category_repository import CategoryRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo(db: Session) -> CategoryRepository:
    return CategoryRepository(db)


def _make_category(
    db: Session,
    company_id: uuid.UUID | None = None,
    code: str = "CAT",
    name: str = "Category",
    parent_id: uuid.UUID | str | None = None,
    status: str = "active",
) -> Category:
    cid = company_id or uuid.uuid4()
    cat = Category(
        company_id=cid,
        code=code,
        name=name,
        parent_id=str(parent_id) if parent_id is not None else None,
        sort_order=0,
        status=status,
    )
    return _repo(db).create(cat)


# ---------------------------------------------------------------------------
# create + get_by_id
# ---------------------------------------------------------------------------


class TestCreateAndGetById:
    def test_create_returns_category_with_id(self, db_session: Session) -> None:
        cat = _make_category(db_session, code="C001", name="Root")
        assert cat.id is not None
        assert cat.code == "C001"
        assert cat.status == "active"

    def test_get_by_id_returns_category(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="C001", name="Root")
        repo = _repo(db_session)
        found = repo.get_by_id(id=cat.id, company_id=cid)
        assert found.id == cat.id

    def test_get_by_id_or_none_returns_none_for_missing(
        self, db_session: Session
    ) -> None:
        repo = _repo(db_session)
        result = repo.get_by_id_or_none(id=uuid.uuid4(), company_id=uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_get_by_id_returns_none_for_wrong_company(
        self, db_session: Session
    ) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="C001")
        repo = _repo(db_session)
        result = repo.get_by_id_or_none(
            id=cat.id,
            company_id=uuid.uuid4(),  # different company
        )
        assert result is None

    def test_get_by_code_isolates_by_company(self, db_session: Session) -> None:
        cid_a = uuid.uuid4()
        cid_b = uuid.uuid4()
        _make_category(db_session, company_id=cid_a, code="SAME")
        _make_category(db_session, company_id=cid_b, code="SAME")
        repo = _repo(db_session)
        a_cat = repo.get_by_code(company_id=cid_a, code="SAME")
        b_cat = repo.get_by_code(company_id=cid_b, code="SAME")
        assert a_cat is not None
        assert b_cat is not None
        assert a_cat.id != b_cat.id

    def test_get_tree_isolates_by_company(self, db_session: Session) -> None:
        cid_a = uuid.uuid4()
        cid_b = uuid.uuid4()
        _make_category(db_session, company_id=cid_a, code="A1", name="A root")
        _make_category(db_session, company_id=cid_b, code="B1", name="B root")
        repo = _repo(db_session)
        tree_a = repo.get_tree(company_id=cid_a)
        assert len(tree_a) == 1


# ---------------------------------------------------------------------------
# get_by_code
# ---------------------------------------------------------------------------


class TestGetByCode:
    def test_returns_none_when_not_found(self, db_session: Session) -> None:
        repo = _repo(db_session)
        result = repo.get_by_code(company_id=uuid.uuid4(), code="NOTEXIST")
        assert result is None

    def test_returns_category_when_found(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="FOUND")
        repo = _repo(db_session)
        result = repo.get_by_code(company_id=cid, code="FOUND")
        assert result is not None
        assert result.id == cat.id


# ---------------------------------------------------------------------------
# Parent / child relationships
# ---------------------------------------------------------------------------


class TestParentChildRelationships:
    def test_get_children_returns_direct_children_only(
        self, db_session: Session
    ) -> None:
        cid = uuid.uuid4()
        root = _make_category(db_session, company_id=cid, code="ROOT", name="Root")
        child1 = _make_category(
            db_session, company_id=cid, code="C1", name="Child1", parent_id=root.id
        )
        child2 = _make_category(
            db_session, company_id=cid, code="C2", name="Child2", parent_id=root.id
        )
        grandchild = _make_category(
            db_session, company_id=cid, code="G1", name="GChild", parent_id=child1.id
        )
        repo = _repo(db_session)
        children = repo.get_children(company_id=cid, parent_id=root.id)
        child_ids = {c.id for c in children}
        assert child1.id in child_ids
        assert child2.id in child_ids
        assert grandchild.id not in child_ids

    def test_get_children_returns_root_categories_when_parent_none(
        self, db_session: Session
    ) -> None:
        cid = uuid.uuid4()
        root1 = _make_category(db_session, company_id=cid, code="R1", name="Root1")
        root2 = _make_category(db_session, company_id=cid, code="R2", name="Root2")
        child = _make_category(
            db_session, company_id=cid, code="CH", name="Child", parent_id=root1.id
        )
        repo = _repo(db_session)
        roots = repo.get_children(company_id=cid, parent_id=None)
        root_ids = {c.id for c in roots}
        assert root1.id in root_ids
        assert root2.id in root_ids
        assert child.id not in root_ids

    def test_get_ancestors_returns_all_ancestors(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        root = _make_category(db_session, company_id=cid, code="L1", name="Level1")
        l2 = _make_category(
            db_session, company_id=cid, code="L2", name="Level2", parent_id=root.id
        )
        l3 = _make_category(
            db_session, company_id=cid, code="L3", name="Level3", parent_id=l2.id
        )
        repo = _repo(db_session)
        ancestors = repo.get_ancestors(company_id=cid, category_id=l3.id)
        ancestor_ids = {a.id for a in ancestors}
        assert root.id in ancestor_ids
        assert l2.id in ancestor_ids
        assert l3.id not in ancestor_ids

    def test_get_ancestors_returns_empty_for_root(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        root = _make_category(db_session, company_id=cid, code="ROOT")
        repo = _repo(db_session)
        ancestors = repo.get_ancestors(company_id=cid, category_id=root.id)
        assert ancestors == []


# ---------------------------------------------------------------------------
# would_create_cycle
# ---------------------------------------------------------------------------


class TestWouldCreateCycle:
    def test_no_cycle_for_unrelated_categories(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        a = _make_category(db_session, company_id=cid, code="A")
        b = _make_category(db_session, company_id=cid, code="B")
        repo = _repo(db_session)
        result = repo.would_create_cycle(
            company_id=cid,
            category_id=a.id,
            new_parent_id=b.id,
        )
        assert result is False

    def test_cycle_detected_when_setting_self_as_parent(
        self, db_session: Session
    ) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="SELF")
        repo = _repo(db_session)
        result = repo.would_create_cycle(
            company_id=cid,
            category_id=cat.id,
            new_parent_id=cat.id,
        )
        assert result is True

    def test_cycle_detected_for_descendant_parent(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        root = _make_category(db_session, company_id=cid, code="ROOT")
        child = _make_category(
            db_session, company_id=cid, code="CHILD", parent_id=root.id
        )
        repo = _repo(db_session)
        result = repo.would_create_cycle(
            company_id=cid,
            category_id=root.id,
            new_parent_id=child.id,
        )
        assert result is True


# ---------------------------------------------------------------------------
# has_active_children
# ---------------------------------------------------------------------------


class TestHasActiveChildren:
    def test_returns_false_when_no_children(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="LEAF")
        repo = _repo(db_session)
        result = repo.has_active_children(company_id=cid, category_id=cat.id)
        assert result is False

    def test_returns_true_when_active_child_exists(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        parent = _make_category(db_session, company_id=cid, code="PAR")
        _make_category(
            db_session,
            company_id=cid,
            code="CHILD",
            parent_id=parent.id,
            status="active",
        )
        repo = _repo(db_session)
        result = repo.has_active_children(company_id=cid, category_id=parent.id)
        assert result is True

    def test_returns_false_when_only_inactive_children(
        self, db_session: Session
    ) -> None:
        cid = uuid.uuid4()
        parent = _make_category(db_session, company_id=cid, code="PAR2")
        child = _make_category(
            db_session,
            company_id=cid,
            code="CHILD2",
            parent_id=parent.id,
            status="active",
        )
        child.status = "inactive"
        _repo(db_session).update(child)
        repo = _repo(db_session)
        result = repo.has_active_children(company_id=cid, category_id=parent.id)
        assert result is False


# ---------------------------------------------------------------------------
# soft-delete
# ---------------------------------------------------------------------------


class TestSoftDelete:
    def test_soft_delete_hides_from_get(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="DEL")
        repo = _repo(db_session)
        repo.soft_delete(id=cat.id, company_id=cid)
        result = repo.get_by_id_or_none(id=cat.id, company_id=cid)
        assert result is None

    def test_soft_delete_hides_from_get_by_code(self, db_session: Session) -> None:
        cid = uuid.uuid4()
        cat = _make_category(db_session, company_id=cid, code="GONE")
        repo = _repo(db_session)
        repo.soft_delete(id=cat.id, company_id=cid)
        result = repo.get_by_code(company_id=cid, code="GONE")
        assert result is None

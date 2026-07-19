"""Unit tests for BaseRepository — multi-tenant CRUD operations.

T136 — create, get_by_id, cross-tenant isolation, soft-delete, list.
"""

import uuid
from uuid import UUID

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, Session, mapped_column

from core.database.models.tenant_base import TenantBaseModel
from core.exceptions.base import NotFoundException
from core.repositories.base import BaseRepository

# ---------------------------------------------------------------------------
# Test-only ORM model (created in the in-memory engine by conftest)
# ---------------------------------------------------------------------------


class TestEntity(TenantBaseModel):
    __tablename__ = "test_entities"

    name: Mapped[str] = mapped_column(String(255), nullable=False)


class TestRepository(BaseRepository[TestEntity]):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(company_id: UUID, name: str = "Test") -> TestEntity:
    return TestEntity(company_id=company_id, name=name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreate:
    def test_create_returns_entity_with_id(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        entity = repo.create(_make_entity(company_id))
        assert entity.id is not None

    def test_create_persists_fields(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        entity = repo.create(_make_entity(company_id, name="Persisted"))
        assert entity.name == "Persisted"
        assert entity.company_id == company_id


class TestGetById:
    def test_get_by_id_returns_entity(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id))
        fetched = repo.get_by_id(id=created.id, company_id=company_id)
        assert fetched.id == created.id

    def test_get_by_id_wrong_company_raises_not_found(
        self, db_session: Session
    ) -> None:
        """Cross-tenant isolation: different company_id must not return the record."""
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        other_company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id))
        with pytest.raises(NotFoundException):
            repo.get_by_id(id=created.id, company_id=other_company_id)

    def test_get_by_id_soft_deleted_raises_not_found(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id))
        repo.soft_delete(id=created.id, company_id=company_id)
        with pytest.raises(NotFoundException):
            repo.get_by_id(id=created.id, company_id=company_id)

    def test_get_by_id_or_none_returns_none_when_not_found(
        self, db_session: Session
    ) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        result = repo.get_by_id_or_none(id=uuid.uuid4(), company_id=company_id)
        assert result is None


class TestList:
    def test_list_returns_all_tenant_records(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        repo.create(_make_entity(company_id, "A"))
        repo.create(_make_entity(company_id, "B"))
        items, total = repo.list(company_id=company_id)
        assert total == 2
        assert len(items) == 2

    def test_list_excludes_soft_deleted_by_default(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id, "ToDelete"))
        repo.create(_make_entity(company_id, "Active"))
        repo.soft_delete(id=created.id, company_id=company_id)
        items, total = repo.list(company_id=company_id)
        assert total == 1
        assert items[0].name == "Active"

    def test_list_includes_deleted_when_requested(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id, "Deleted"))
        repo.create(_make_entity(company_id, "Active"))
        repo.soft_delete(id=created.id, company_id=company_id)
        items, total = repo.list(company_id=company_id, include_deleted=True)
        assert total == 2

    def test_list_never_returns_other_tenant_records(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        repo.create(_make_entity(company_a, "CompanyA"))
        repo.create(_make_entity(company_b, "CompanyB"))
        items_a, total_a = repo.list(company_id=company_a)
        items_b, total_b = repo.list(company_id=company_b)
        assert total_a == 1
        assert total_b == 1
        assert items_a[0].name == "CompanyA"
        assert items_b[0].name == "CompanyB"


class TestSoftDelete:
    def test_soft_delete_sets_is_deleted_true(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id))
        repo.soft_delete(id=created.id, company_id=company_id)
        # Directly query to verify is_deleted flag
        result = db_session.query(TestEntity).filter(TestEntity.id == created.id).one()
        assert result.is_deleted is True

    def test_soft_delete_populates_deleted_at(self, db_session: Session) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id))
        repo.soft_delete(id=created.id, company_id=company_id)
        result = db_session.query(TestEntity).filter(TestEntity.id == created.id).one()
        assert result.deleted_at is not None

    def test_soft_delete_wrong_company_raises_not_found(
        self, db_session: Session
    ) -> None:
        repo = TestRepository(db_session, TestEntity)
        company_id = uuid.uuid4()
        other_id = uuid.uuid4()
        created = repo.create(_make_entity(company_id))
        with pytest.raises(NotFoundException):
            repo.soft_delete(id=created.id, company_id=other_id)

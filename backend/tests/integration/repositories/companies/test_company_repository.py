"""Integration tests for CompanyRepository.

Uses the shared ``db_session`` fixture (SQLite in-memory with rollback isolation)
from conftest.py.  All writes are rolled back after each test function.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.companies.repositories.company_repository import CompanyRepository
from tests.fixtures.company_fixtures import make_company_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo(db: Session) -> CompanyRepository:
    return CompanyRepository(db)


def _make(db: Session, **overrides: Any) -> Company:
    """Create a company via the repository and return it."""
    data = make_company_data(**overrides)
    return _repo(db).create(data)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    def test_creates_company_with_required_fields(self, db_session: Session) -> None:
        data = make_company_data(legal_name="Test Corp LLC")
        company = _repo(db_session).create(data)
        assert company.id is not None
        assert company.legal_name == "Test Corp LLC"
        assert company.created_at is not None

    def test_default_status_is_pending_setup(self, db_session: Session) -> None:
        company = _make(db_session)
        assert company.status == CompanyStatus.pending_setup.value

    def test_unique_slug_per_company(self, db_session: Session) -> None:
        c1 = _make(db_session, legal_name="Alpha Inc", slug="alpha-inc-001")
        c2 = _make(db_session, legal_name="Beta Inc", slug="beta-inc-001")
        assert c1.slug != c2.slug


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    def test_returns_company_by_id(self, db_session: Session) -> None:
        company = _make(db_session)
        found = _repo(db_session).get_by_id(company.id)
        assert found is not None
        assert found.id == company.id

    def test_returns_none_for_unknown_id(self, db_session: Session) -> None:
        result = _repo(db_session).get_by_id(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# get_by_slug
# ---------------------------------------------------------------------------


class TestGetBySlug:
    def test_returns_company_by_slug(self, db_session: Session) -> None:
        company = _make(db_session, slug="my-unique-slug-001")
        found = _repo(db_session).get_by_slug("my-unique-slug-001")
        assert found is not None
        assert found.id == company.id

    def test_returns_none_for_unknown_slug(self, db_session: Session) -> None:
        result = _repo(db_session).get_by_slug("does-not-exist")
        assert result is None


# ---------------------------------------------------------------------------
# exists_by_name
# ---------------------------------------------------------------------------


class TestExistsByName:
    def test_returns_true_for_existing_name(self, db_session: Session) -> None:
        _make(db_session, legal_name="Existing Corp")
        assert _repo(db_session).exists_by_name("Existing Corp") is True

    def test_case_insensitive_match(self, db_session: Session) -> None:
        _make(db_session, legal_name="Case Corp")
        assert _repo(db_session).exists_by_name("case corp") is True
        assert _repo(db_session).exists_by_name("CASE CORP") is True

    def test_returns_false_for_unknown_name(self, db_session: Session) -> None:
        assert _repo(db_session).exists_by_name("Nobody Inc") is False

    def test_exclude_id_skips_self(self, db_session: Session) -> None:
        company = _make(db_session, legal_name="Self Corp")
        assert (
            _repo(db_session).exists_by_name("Self Corp", exclude_id=company.id)
            is False
        )


# ---------------------------------------------------------------------------
# exists_by_slug
# ---------------------------------------------------------------------------


class TestExistsBySlug:
    def test_returns_true_for_existing_slug(self, db_session: Session) -> None:
        _make(db_session, slug="taken-slug-001")
        assert _repo(db_session).exists_by_slug("taken-slug-001") is True

    def test_returns_false_for_unknown_slug(self, db_session: Session) -> None:
        assert _repo(db_session).exists_by_slug("free-slug") is False

    def test_exclude_id_skips_self(self, db_session: Session) -> None:
        company = _make(db_session, slug="own-slug-001")
        assert (
            _repo(db_session).exists_by_slug("own-slug-001", exclude_id=company.id)
            is False
        )


# ---------------------------------------------------------------------------
# soft_delete
# ---------------------------------------------------------------------------


class TestSoftDelete:
    def test_marks_company_deleted(self, db_session: Session) -> None:
        from core.utils.datetime import utcnow

        company = _make(db_session)
        deleted = _repo(db_session).soft_delete(
            company, deleted_at=utcnow(), reason="Test deletion"
        )
        assert deleted.status == CompanyStatus.deleted.value
        assert deleted.deleted_at is not None
        assert deleted.deletion_reason == "Test deletion"

    def test_deleted_company_excluded_from_list_by_owner(
        self, db_session: Session
    ) -> None:
        from core.utils.datetime import utcnow

        owner_id = uuid.uuid4()
        company = _make(db_session, owner_id=str(owner_id))
        _repo(db_session).soft_delete(company, deleted_at=utcnow(), reason="Gone")
        results = _repo(db_session).list_by_owner(owner_id)
        assert all(c.id != company.id for c in results)


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------


class TestRestore:
    def test_restores_deleted_company_to_inactive(self, db_session: Session) -> None:
        from core.utils.datetime import utcnow

        company = _make(db_session)
        _repo(db_session).soft_delete(company, deleted_at=utcnow(), reason="Test")
        restored = _repo(db_session).restore(company)
        assert restored.status == CompanyStatus.inactive.value
        assert restored.deleted_at is None
        assert restored.deletion_reason is None


# ---------------------------------------------------------------------------
# list_by_owner
# ---------------------------------------------------------------------------


class TestListByOwner:
    def test_returns_only_owner_companies(self, db_session: Session) -> None:
        owner_id = uuid.uuid4()
        other_owner_id = uuid.uuid4()
        c1 = _make(db_session, owner_id=str(owner_id), legal_name="Owner Co 1")
        c2 = _make(db_session, owner_id=str(owner_id), legal_name="Owner Co 2")
        _make(db_session, owner_id=str(other_owner_id), legal_name="Other Co")

        results = _repo(db_session).list_by_owner(owner_id)
        result_ids = {c.id for c in results}
        assert c1.id in result_ids
        assert c2.id in result_ids

    def test_returns_empty_for_unknown_owner(self, db_session: Session) -> None:
        results = _repo(db_session).list_by_owner(uuid.uuid4())
        assert results == []


# ---------------------------------------------------------------------------
# list_all (SuperAdmin)
# ---------------------------------------------------------------------------


class TestListAll:
    def test_returns_all_non_deleted(self, db_session: Session) -> None:
        from core.utils.datetime import utcnow

        prefix = uuid.uuid4().hex[:6]
        c1 = _make(db_session, legal_name=f"{prefix} Alpha")
        c2 = _make(db_session, legal_name=f"{prefix} Beta")
        deleted = _make(db_session, legal_name=f"{prefix} Deleted")
        _repo(db_session).soft_delete(deleted, deleted_at=utcnow(), reason="Gone")

        items, total = _repo(db_session).list_all(
            filters={"search": prefix}, page=1, page_size=50
        )
        ids = {c.id for c in items}
        assert c1.id in ids
        assert c2.id in ids
        assert deleted.id not in ids

    def test_include_deleted_filter(self, db_session: Session) -> None:
        from core.utils.datetime import utcnow

        prefix = uuid.uuid4().hex[:6]
        company = _make(db_session, legal_name=f"{prefix} ToDelete")
        _repo(db_session).soft_delete(company, deleted_at=utcnow(), reason="Gone")

        items, _ = _repo(db_session).list_all(
            filters={"search": prefix, "include_deleted": True}, page=1, page_size=50
        )
        assert any(c.id == company.id for c in items)

    def test_pagination(self, db_session: Session) -> None:
        prefix = uuid.uuid4().hex[:6]
        for i in range(5):
            _make(db_session, legal_name=f"{prefix} Paged {i}")

        _, total = _repo(db_session).list_all(
            filters={"search": prefix}, page=1, page_size=50
        )
        assert total >= 5

        page1, _ = _repo(db_session).list_all(
            filters={"search": prefix}, page=1, page_size=2
        )
        page2, _ = _repo(db_session).list_all(
            filters={"search": prefix}, page=2, page_size=2
        )
        assert len(page1) == 2
        assert len(page2) >= 1
        assert {c.id for c in page1}.isdisjoint({c.id for c in page2})

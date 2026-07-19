"""T039 [US1] — Repository integration tests for CompanyMemberRepository.

Tests: CRUD, company-scoped queries, unique constraint enforcement.

Uses the db_session fixture from conftest.py with SQLite in-memory.

Spec reference: tasks T039.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.company_fixtures import make_company_data
from tests.fixtures.users_roles_fixtures import (
    create_test_member,
    seed_system_roles,
)


def _setup_company_and_roles(db: Session) -> tuple:
    """Create a test company with seeded roles and return (company_id, owner, roles)."""
    from modules.companies.repositories.company_repository import CompanyRepository

    owner, _ = create_test_user(db, email=f"owner_{uuid.uuid4().hex[:8]}@example.com")
    company_data = make_company_data(owner_id=str(owner.id))
    company_repo = CompanyRepository(db)
    company = company_repo.create(company_data)
    roles = seed_system_roles(db, company.id, owner.id)

    return company.id, owner, roles


class TestCompanyMemberRepositoryCRUD:
    """Test basic CRUD operations."""

    def test_create_member(self, db_session: Session) -> None:
        """create() persists a CompanyMember and returns it with server-generated fields."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")

        member_user, _ = create_test_user(
            db_session, email=f"member_{uuid.uuid4().hex[:8]}@example.com"
        )

        repo = CompanyMemberRepository(db_session)
        member = CompanyMember(
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
            status=MembershipStatus.active.value,
            created_by=owner.id,
        )
        created = repo.create(member)

        assert created.id is not None
        assert created.company_id == company_id
        assert created.user_id == member_user.id
        assert created.role_id == viewer_role.id
        assert created.status == MembershipStatus.active.value

    def test_get_by_id(self, db_session: Session) -> None:
        """get_by_id() returns the member scoped by company_id."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")
        member_user, _ = create_test_user(
            db_session, email=f"getbyid_{uuid.uuid4().hex[:8]}@example.com"
        )

        member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
        )

        repo = CompanyMemberRepository(db_session)
        found = repo.get_by_id(id=member.id, company_id=company_id)
        assert found.id == member.id

    def test_get_by_id_wrong_company_raises(self, db_session: Session) -> None:
        """get_by_id() raises NotFoundException for wrong company_id."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")
        member_user, _ = create_test_user(
            db_session, email=f"wrongco_{uuid.uuid4().hex[:8]}@example.com"
        )

        member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
        )

        repo = CompanyMemberRepository(db_session)
        with pytest.raises(NotFoundException):
            repo.get_by_id(id=member.id, company_id=uuid.uuid4())


class TestCompanyMemberRepositoryLookups:
    """Test company-scoped lookup methods."""

    def test_get_by_user_id(self, db_session: Session) -> None:
        """get_by_user_id() returns the membership for a user in a company."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")
        member_user, _ = create_test_user(
            db_session, email=f"byuser_{uuid.uuid4().hex[:8]}@example.com"
        )

        member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
        )

        repo = CompanyMemberRepository(db_session)
        found = repo.get_by_user_id(user_id=member_user.id, company_id=company_id)
        assert found is not None
        assert found.id == member.id

    def test_get_by_user_id_returns_none_for_other_company(
        self, db_session: Session
    ) -> None:
        """get_by_user_id() returns None when user not in company."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")
        member_user, _ = create_test_user(
            db_session, email=f"nocompany_{uuid.uuid4().hex[:8]}@example.com"
        )

        create_test_member(
            db_session,
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
        )

        repo = CompanyMemberRepository(db_session)
        found = repo.get_by_user_id(user_id=member_user.id, company_id=uuid.uuid4())
        assert found is None

    def test_count_by_company(self, db_session: Session) -> None:
        """count_by_company() returns the correct count of members."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")

        repo = CompanyMemberRepository(db_session)
        assert repo.count_by_company(company_id) == 0

        for i in range(3):
            user, _ = create_test_user(
                db_session,
                email=f"count_{uuid.uuid4().hex[:8]}@example.com",
            )
            create_test_member(
                db_session,
                company_id=company_id,
                user_id=user.id,
                role_id=viewer_role.id,
            )

        assert repo.count_by_company(company_id) == 3

    def test_list_by_company_with_status_filter(self, db_session: Session) -> None:
        """list_by_company() filters by status."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")

        for i, stat in enumerate(["active", "active", "inactive"]):
            user, _ = create_test_user(
                db_session,
                email=f"filter_{uuid.uuid4().hex[:8]}@example.com",
            )
            create_test_member(
                db_session,
                company_id=company_id,
                user_id=user.id,
                role_id=viewer_role.id,
                status=stat,
            )

        repo = CompanyMemberRepository(db_session)
        active_members, active_total = repo.list_by_company(company_id, status="active")
        assert active_total == 2

        inactive_members, inactive_total = repo.list_by_company(
            company_id, status="inactive"
        )
        assert inactive_total == 1


class TestCompanyMemberRepositorySoftDelete:
    """Test soft-delete functionality."""

    def test_soft_delete_excludes_from_queries(self, db_session: Session) -> None:
        """Soft-deleted members are excluded from default queries."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")
        member_user, _ = create_test_user(
            db_session, email=f"softdel_{uuid.uuid4().hex[:8]}@example.com"
        )

        member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
        )

        repo = CompanyMemberRepository(db_session)
        repo.soft_delete(id=member.id, company_id=company_id)

        assert repo.get_by_user_id(member_user.id, company_id) is None
        assert repo.count_by_company(company_id) == 0

    def test_get_by_company_and_user_includes_deleted(
        self, db_session: Session
    ) -> None:
        """get_by_company_and_user with include_deleted=True returns soft-deleted members."""
        company_id, owner, roles = _setup_company_and_roles(db_session)
        viewer_role = next(r for r in roles if r.slug == "viewer")
        member_user, _ = create_test_user(
            db_session,
            email=f"incldel_{uuid.uuid4().hex[:8]}@example.com",
        )

        member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=member_user.id,
            role_id=viewer_role.id,
        )

        repo = CompanyMemberRepository(db_session)
        repo.soft_delete(id=member.id, company_id=company_id)

        found = repo.get_by_company_and_user(
            company_id, member_user.id, include_deleted=True
        )
        assert found is not None
        assert found.is_deleted is True

"""[T085] [FR-9A-017] [ADR-6] Unit tests for
``assert_company_access_allowed``'s two layers: company status, and the
authentication-freshness watermark comparison
(``Session.created_at <= Company.access_invalidated_at`` -> deny).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from modules.auth.models.session import Session as TenantSession
from modules.auth.models.user import User
from modules.companies.exceptions import CompanyNotFoundError, CompanySuspendedError
from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.platform_admin.services.company_access_service import (
    assert_company_access_allowed,
)


def _make_user(db: Session) -> User:
    user = User(
        email=f"access-rule-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Access Rule User",
    )
    db.add(user)
    db.flush()
    return user


def _make_company(
    db: Session,
    *,
    owner_id,
    status: str = CompanyStatus.active.value,
    access_invalidated_at: datetime | None = None,
) -> Company:
    suffix = uuid.uuid4().hex[:10]
    # ck_companies_pre_suspension_status_presence requires a non-NULL
    # pre_suspension_status exactly when status='suspended'.
    pre_suspension_status = (
        CompanyStatus.active.value if status == CompanyStatus.suspended.value else None
    )
    company = Company(
        legal_name=f"Access Rule Co {suffix}",
        slug=f"access-rule-co-{suffix}",
        owner_id=owner_id,
        email=f"access-rule-co-{suffix}@example.test",
        status=status,
        pre_suspension_status=pre_suspension_status,
        access_invalidated_at=access_invalidated_at,
    )
    db.add(company)
    db.flush()
    return company


def _make_session(db: Session, *, user_id, created_at: datetime) -> TenantSession:
    session = TenantSession(user_id=user_id)
    db.add(session)
    db.flush()
    session.created_at = created_at
    db.flush()
    return session


class TestStatusPaths:
    def test_active_company_allows(self, db_session: Session) -> None:
        user = _make_user(db_session)
        company = _make_company(db_session, owner_id=user.id)
        session = _make_session(
            db_session, user_id=user.id, created_at=datetime.now(UTC)
        )
        db_session.commit()

        assert_company_access_allowed(db_session, company.id, session.id)  # no raise

    def test_inactive_company_with_no_watermark_allows(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session)
        company = _make_company(
            db_session, owner_id=user.id, status=CompanyStatus.inactive.value
        )
        session = _make_session(
            db_session, user_id=user.id, created_at=datetime.now(UTC)
        )
        db_session.commit()

        assert_company_access_allowed(db_session, company.id, session.id)  # no raise

    def test_suspended_company_denies_with_company_suspended_error(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session)
        company = _make_company(
            db_session, owner_id=user.id, status=CompanyStatus.suspended.value
        )
        session = _make_session(
            db_session, user_id=user.id, created_at=datetime.now(UTC)
        )
        db_session.commit()

        with pytest.raises(CompanySuspendedError):
            assert_company_access_allowed(db_session, company.id, session.id)

    def test_deleted_company_denies_with_company_not_found_error(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session)
        company = _make_company(
            db_session, owner_id=user.id, status=CompanyStatus.deleted.value
        )
        session = _make_session(
            db_session, user_id=user.id, created_at=datetime.now(UTC)
        )
        db_session.commit()

        with pytest.raises(CompanyNotFoundError):
            assert_company_access_allowed(db_session, company.id, session.id)

    def test_nonexistent_company_is_a_no_op(self, db_session: Session) -> None:
        user = _make_user(db_session)
        session = _make_session(
            db_session, user_id=user.id, created_at=datetime.now(UTC)
        )
        db_session.commit()

        assert_company_access_allowed(db_session, uuid.uuid4(), session.id)  # no raise


class TestFreshnessWatermark:
    def test_session_created_before_watermark_denies(self, db_session: Session) -> None:
        user = _make_user(db_session)
        watermark = datetime.now(UTC)
        company = _make_company(
            db_session, owner_id=user.id, access_invalidated_at=watermark
        )
        session = _make_session(
            db_session, user_id=user.id, created_at=watermark - timedelta(minutes=1)
        )
        db_session.commit()

        with pytest.raises(CompanySuspendedError):
            assert_company_access_allowed(db_session, company.id, session.id)

    def test_session_created_exactly_at_watermark_denies(
        self, db_session: Session
    ) -> None:
        """The rule is `<=`, not `<` — an exact tie must still deny."""
        user = _make_user(db_session)
        watermark = datetime.now(UTC)
        company = _make_company(
            db_session, owner_id=user.id, access_invalidated_at=watermark
        )
        session = _make_session(db_session, user_id=user.id, created_at=watermark)
        db_session.commit()

        with pytest.raises(CompanySuspendedError):
            assert_company_access_allowed(db_session, company.id, session.id)

    def test_session_created_after_watermark_allows(self, db_session: Session) -> None:
        user = _make_user(db_session)
        watermark = datetime.now(UTC)
        company = _make_company(
            db_session, owner_id=user.id, access_invalidated_at=watermark
        )
        session = _make_session(
            db_session, user_id=user.id, created_at=watermark + timedelta(minutes=1)
        )
        db_session.commit()

        assert_company_access_allowed(db_session, company.id, session.id)  # no raise


class TestNullWatermarkDeniesNothing:
    def test_null_watermark_allows_regardless_of_session_age(
        self, db_session: Session
    ) -> None:
        """Rollout safety (T086): every pre-Epic-9A company has
        access_invalidated_at=NULL, so an old Session must never be
        denied on that basis alone."""
        user = _make_user(db_session)
        company = _make_company(
            db_session, owner_id=user.id, access_invalidated_at=None
        )
        ancient_session = _make_session(
            db_session, user_id=user.id, created_at=datetime(2000, 1, 1, tzinfo=UTC)
        )
        db_session.commit()

        assert_company_access_allowed(db_session, company.id, ancient_session.id)

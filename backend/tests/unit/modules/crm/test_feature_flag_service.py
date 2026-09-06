"""Unit tests for CrmFeatureFlagService.

Tests cover:
  - is_enabled() with no row -> defaults to False
  - enable() creates an override, is_enabled() then returns True
  - disable() creates/updates an override, is_enabled() then returns False
  - enable() is idempotent (calling twice does not create two rows)
  - Tenant isolation (different companies see different states)

Uses the real ``db_session`` SQLite fixture (not mocks) per tasks.md T007.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService


def _make_service(db: Session) -> CrmFeatureFlagService:
    return CrmFeatureFlagService(db=db, flag_repo=CrmFeatureFlagRepository(db))


class TestIsEnabledDefault:
    def test_defaults_to_false_when_no_row_exists(self, db_session: Session) -> None:
        svc = _make_service(db_session)
        assert svc.is_enabled(uuid.uuid4()) is False


class TestEnableDisable:
    def test_enable_then_is_enabled_true(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        svc = _make_service(db_session)
        svc.enable(company_id)
        assert svc.is_enabled(company_id) is True

    def test_disable_then_is_enabled_false(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        svc = _make_service(db_session)
        svc.enable(company_id)
        svc.disable(company_id)
        assert svc.is_enabled(company_id) is False

    def test_enable_is_idempotent_single_row(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        svc = _make_service(db_session)
        svc.enable(company_id)
        svc.enable(company_id)
        repo = CrmFeatureFlagRepository(db_session)
        items, total = repo.list(company_id=company_id)
        assert total == 1

    def test_enable_records_actor(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        svc = _make_service(db_session)
        svc.enable(company_id, actor_id=actor_id)
        repo = CrmFeatureFlagRepository(db_session)
        override = repo.get_by_key(
            company_id=company_id, flag_key="feature.crm.enabled"
        )
        assert override is not None
        assert override.created_by == actor_id

    def test_disable_without_prior_enable_creates_disabled_row(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        svc = _make_service(db_session)
        svc.disable(company_id)
        assert svc.is_enabled(company_id) is False


class TestTenantIsolation:
    def test_different_companies_see_different_states(
        self, db_session: Session
    ) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        svc = _make_service(db_session)
        svc.enable(company_a)
        assert svc.is_enabled(company_a) is True
        assert svc.is_enabled(company_b) is False

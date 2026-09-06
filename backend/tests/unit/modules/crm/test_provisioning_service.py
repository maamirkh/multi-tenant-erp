"""Unit test: CrmProvisioningService idempotency (tasks.md T035).

Uses the real ``db_session`` fixture (SQLite) rather than a fully mocked
repository/session — the property under test (exactly one default
Pipeline/stage-set and one CRM-Converted category survive two calls) is
inherently a persistence-layer property, not pure business logic in
isolation; a mock would just assert "was called twice", which proves
nothing about actual idempotency.

Task: T035 (tasks.md Phase 4).
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.provisioning_service import (
    CRM_CONVERTED_CATEGORY_CODE,
    CrmProvisioningService,
)
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.master import CustomerCategoryRepository
from modules.sales.services.master_data_service import CustomerCategoryService


def _service(db_session: Session) -> CrmProvisioningService:
    pipeline_repo = PipelineRepository(db_session)
    stage_repo = PipelineStageRepository(db_session)
    pipeline_service = PipelineService(db_session, pipeline_repo, stage_repo)
    category_repo = CustomerCategoryRepository(db_session)
    category_service = CustomerCategoryService(db_session, category_repo)
    return CrmProvisioningService(
        db_session, pipeline_repo, pipeline_service, category_repo, category_service
    )


class TestEnsureDefaultsIdempotency:
    def test_second_call_returns_the_same_pipeline_and_category(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _service(db_session)

        first = service.ensure_defaults(company_id)
        second = service.ensure_defaults(company_id)

        assert first.pipeline.id == second.pipeline.id
        assert first.category.id == second.category.id

    def test_exactly_one_default_pipeline_after_two_calls(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _service(db_session)

        service.ensure_defaults(company_id)
        service.ensure_defaults(company_id)

        _, total = BaseRepository(db_session, Pipeline).list(company_id=company_id)
        assert total == 1

    def test_exactly_one_crm_converted_category_after_two_calls(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _service(db_session)
        category_repo = CustomerCategoryRepository(db_session)

        service.ensure_defaults(company_id)
        service.ensure_defaults(company_id)

        # Note: deliberately not using CustomerCategoryRepository.get_active()
        # here — its is_active=True filter is unrelated to this test and
        # happens to be unreliable under SQLite specifically for a
        # server_default("true")-populated boolean column (SQLite stores
        # the quoted string default verbatim as TEXT rather than casting
        # it to its integer boolean convention the way Postgres does for a
        # real BOOLEAN column; a pre-existing Sales-side characteristic,
        # not something this phase modifies or fixes). get_by_code() is
        # unaffected (String column) and is the exact method
        # ``_ensure_crm_converted_category`` itself relies on for its own
        # idempotency check, so it is the correct thing to assert against.
        found = category_repo.get_by_code(
            company_id=company_id, code=CRM_CONVERTED_CATEGORY_CODE
        )
        assert found is not None

        all_categories, _ = BaseRepository(db_session, CustomerCategory).list(
            company_id=company_id, limit=100
        )
        matches = [c for c in all_categories if c.code == CRM_CONVERTED_CATEGORY_CODE]
        assert len(matches) == 1

    def test_default_pipeline_has_five_stages_with_won_and_lost_flagged(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _service(db_session)

        result = service.ensure_defaults(company_id)

        stages, total = BaseRepository(db_session, PipelineStage).list(
            company_id=company_id
        )
        assert total == 5
        assert all(s.pipeline_id == result.pipeline.id for s in stages)
        won_stages = [s for s in stages if s.is_won_stage]
        lost_stages = [s for s in stages if s.is_lost_stage]
        assert len(won_stages) == 1
        assert len(lost_stages) == 1

    def test_different_companies_get_independent_defaults(
        self, db_session: Session
    ) -> None:
        service = _service(db_session)
        company_a, company_b = uuid4(), uuid4()

        result_a = service.ensure_defaults(company_a)
        result_b = service.ensure_defaults(company_b)

        assert result_a.pipeline.id != result_b.pipeline.id
        assert result_a.category.id != result_b.category.id

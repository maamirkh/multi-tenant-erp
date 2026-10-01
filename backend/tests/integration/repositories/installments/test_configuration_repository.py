"""[Phase 2] Real-Postgres repository tests for Installments Configuration
and Plan Template — tenant isolation plus the T001 uniqueness invariant.

Covers tasks.md T039. Partial unique indexes are PostgreSQL-specific;
SQLite cannot substitute (plan.md §31/§32), mirroring the 057-061/T053
precedent — reuses the existing throwaway-per-test-database fixtures
(``pg_test_db``/``alembic_upgrade``/``db_engine``) from
``tests/integration/migrations/conftest.py`` rather than duplicating
that infrastructure.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from modules.installments.models.configuration import InstallmentConfiguration
from modules.installments.models.plan_template import InstallmentPlanTemplate
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from tests.integration.migrations.conftest import (  # noqa: F401 — pg_test_db re-exported for pytest fixture discovery
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def db_session(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _minimal_config_fields() -> dict[str, Any]:
    return {
        "allowed_frequencies": ["MONTHLY"],
        "min_term": 3,
        "max_term": 36,
    }


class TestInstallmentConfigurationRepositoryUniqueness:
    """T039(a)/(b)/(c): the T001 partial-unique-index invariant."""

    def test_only_one_company_default_row_allowed(self, db_session) -> None:
        repo = InstallmentConfigurationRepository(db_session)
        company_id = uuid.uuid4()

        repo.create(
            InstallmentConfiguration(
                company_id=company_id, branch_id=None, **_minimal_config_fields()
            )
        )

        with pytest.raises(IntegrityError):
            repo.create(
                InstallmentConfiguration(
                    company_id=company_id, branch_id=None, **_minimal_config_fields()
                )
            )
        db_session.rollback()

    def test_two_different_branch_overrides_coexist(self, db_session) -> None:
        repo = InstallmentConfigurationRepository(db_session)
        company_id = uuid.uuid4()
        branch_a, branch_b = uuid.uuid4(), uuid.uuid4()

        repo.create(
            InstallmentConfiguration(
                company_id=company_id, branch_id=branch_a, **_minimal_config_fields()
            )
        )
        repo.create(
            InstallmentConfiguration(
                company_id=company_id, branch_id=branch_b, **_minimal_config_fields()
            )
        )

        assert repo.get_branch_override(company_id, branch_a) is not None
        assert repo.get_branch_override(company_id, branch_b) is not None

    def test_duplicate_branch_override_rejected(self, db_session) -> None:
        repo = InstallmentConfigurationRepository(db_session)
        company_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        repo.create(
            InstallmentConfiguration(
                company_id=company_id, branch_id=branch_id, **_minimal_config_fields()
            )
        )

        with pytest.raises(IntegrityError):
            repo.create(
                InstallmentConfiguration(
                    company_id=company_id,
                    branch_id=branch_id,
                    **_minimal_config_fields(),
                )
            )
        db_session.rollback()

    def test_effective_config_resolves_branch_override_then_company_fallback(
        self, db_session
    ) -> None:
        repo = InstallmentConfigurationRepository(db_session)
        company_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        company_default = repo.create(
            InstallmentConfiguration(
                company_id=company_id, branch_id=None, **_minimal_config_fields()
            )
        )
        branch_override = repo.create(
            InstallmentConfiguration(
                company_id=company_id,
                branch_id=branch_id,
                **{**_minimal_config_fields(), "min_term": 6},
            )
        )

        # Branch override wins when queried with that branch_id.
        effective = repo.get_effective_config(company_id, branch_id)
        assert effective is not None
        assert effective.id == branch_override.id

        # A branch with no override falls back to the company default.
        effective_other_branch = repo.get_effective_config(company_id, uuid.uuid4())
        assert effective_other_branch is not None
        assert effective_other_branch.id == company_default.id

        # No branch_id -> company default directly.
        no_branch = repo.get_effective_config(company_id, None)
        assert no_branch is not None
        assert no_branch.id == company_default.id


class TestInstallmentConfigurationRepositoryTenantIsolation:
    """T039: tenant isolation, mirroring test_tenant_isolation.py's
    two_tenants pattern."""

    def test_configuration_scoped_to_owning_company(self, db_session) -> None:
        repo = InstallmentConfigurationRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()

        repo.create(
            InstallmentConfiguration(
                company_id=company_a, branch_id=None, **_minimal_config_fields()
            )
        )

        assert repo.get_company_default(company_a) is not None
        assert repo.get_company_default(company_b) is None

    def test_plan_template_scoped_to_owning_company(self, db_session) -> None:
        repo = InstallmentPlanTemplateRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()

        repo.create(
            InstallmentPlanTemplate(
                company_id=company_a,
                name="Standard 12-Month",
                frequency="MONTHLY",
                installment_count=12,
                down_payment_rule={"type": "PERCENTAGE", "value": 10},
            )
        )

        assert repo.get_by_name(company_a, "Standard 12-Month") is not None
        assert repo.get_by_name(company_b, "Standard 12-Month") is None
        assert len(repo.list_active(company_a)) == 1
        assert len(repo.list_active(company_b)) == 0


class TestInstallmentPlanTemplateRepositoryUniqueness:
    def test_duplicate_name_rejected_by_partial_unique_index(self, db_session) -> None:
        repo = InstallmentPlanTemplateRepository(db_session)
        company_id = uuid.uuid4()

        repo.create(
            InstallmentPlanTemplate(
                company_id=company_id,
                name="Standard 12-Month",
                frequency="MONTHLY",
                installment_count=12,
                down_payment_rule={"type": "PERCENTAGE", "value": 10},
            )
        )

        with pytest.raises(IntegrityError):
            repo.create(
                InstallmentPlanTemplate(
                    company_id=company_id,
                    name="Standard 12-Month",
                    frequency="WEEKLY",
                    installment_count=6,
                    down_payment_rule={"type": "PERCENTAGE", "value": 5},
                )
            )
        db_session.rollback()

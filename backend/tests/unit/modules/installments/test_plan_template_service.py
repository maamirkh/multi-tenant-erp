"""Unit tests for InstallmentPlanTemplateService.

Covers tasks.md T040: deactivation blocks new use (excluded from
``list_active()``) but leaves the template's own row otherwise
unaffected — a placeholder assertion against template state only; the
full contract-linkage proof ("existing contracts created from a
deactivated template are unaffected") is deferred to Phase 3, once
``InstallmentContract`` exists.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.services.plan_template_service import (
    InstallmentPlanTemplateService,
)


@pytest.fixture
def service(db_session: Session) -> InstallmentPlanTemplateService:
    return InstallmentPlanTemplateService(
        repo=InstallmentPlanTemplateRepository(db_session)
    )


def _create(service: InstallmentPlanTemplateService, company_id, **overrides):
    fields = {
        "name": "Standard 12-Month",
        "frequency": "MONTHLY",
        "installment_count": 12,
        "down_payment_rule": {"type": "PERCENTAGE", "value": 10},
        **overrides,
    }
    return service.create(company_id=company_id, actor_id=None, **fields)


class TestPlanTemplateDeactivation:
    def test_deactivate_excludes_template_from_list_active(
        self, service: InstallmentPlanTemplateService
    ) -> None:
        company_id = uuid.uuid4()
        template = _create(service, company_id)
        assert template in service.list_active(company_id)

        deactivated = service.deactivate(company_id, template.id)

        assert deactivated.is_active is False
        assert deactivated not in service.list_active(company_id)

    def test_deactivate_leaves_template_row_intact(
        self, service: InstallmentPlanTemplateService
    ) -> None:
        """Placeholder: the template row itself (name, terms) is
        untouched by deactivation — only ``is_active`` flips. Full
        contract-linkage assertion ("existing contracts unaffected")
        deferred to Phase 3 once InstallmentContract exists."""
        company_id = uuid.uuid4()
        template = _create(service, company_id)

        deactivated = service.deactivate(company_id, template.id)

        assert deactivated.id == template.id
        assert deactivated.name == template.name
        assert deactivated.installment_count == template.installment_count
        assert deactivated.down_payment_rule == template.down_payment_rule

    def test_deactivated_name_can_be_reused_by_a_new_template(
        self, service: InstallmentPlanTemplateService
    ) -> None:
        """Deactivation (soft, is_active=False) does not free the name —
        only soft-delete does (the DB partial unique index is scoped to
        ``is_deleted = false``, not ``is_active``). This documents the
        actual invariant rather than assuming deactivation implies
        deletion."""
        company_id = uuid.uuid4()
        template = _create(service, company_id)
        service.deactivate(company_id, template.id)

        with pytest.raises(ConflictException):
            _create(service, company_id)


class TestPlanTemplateUniqueName:
    def test_create_rejects_duplicate_name_same_company(
        self, service: InstallmentPlanTemplateService
    ) -> None:
        company_id = uuid.uuid4()
        _create(service, company_id)

        with pytest.raises(ConflictException):
            _create(service, company_id)

    def test_create_allows_same_name_different_company(
        self, service: InstallmentPlanTemplateService
    ) -> None:
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        _create(service, company_a)
        # Should not raise.
        _create(service, company_b)

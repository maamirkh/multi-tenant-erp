"""InstallmentPlanTemplateService — reusable commercial plan templates.

Create/edit/deactivate, enforcing unique-name-per-company at the service
layer (the DB partial unique index, migration 063, is the final
backstop). Deactivation blocks new use but never affects existing
contracts (FR-INST-013) — a deactivated template is simply excluded from
``list_active()``.

Spec ref: specs/010-installments/data-model.md "InstallmentPlanTemplate".
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.exceptions.base import ConflictException, ValidationException
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.models.plan_template import InstallmentPlanTemplate
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)


class InstallmentPlanTemplateService:
    """Service layer for Installments plan templates."""

    def __init__(
        self,
        repo: InstallmentPlanTemplateRepository,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self._repo = repo
        self._access_policy = access_policy

    def list_active(self, company_id: UUID) -> list[InstallmentPlanTemplate]:
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.READ
            )
        return self._repo.list_active(company_id)

    def get(self, company_id: UUID, template_id: UUID) -> InstallmentPlanTemplate:
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.READ
            )
        template = self._repo.get_by_id_or_none(template_id, company_id)
        if template is None:
            raise InstallmentNotFoundError("InstallmentPlanTemplate", str(template_id))
        return template

    def create(
        self, company_id: UUID, actor_id: UUID | None, **fields: Any
    ) -> InstallmentPlanTemplate:
        """Create a new plan template. Rejects a duplicate name for this
        company with a clean 409 before the DB partial unique index is
        ever reached."""
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
            )
        self._validate_fields(fields)
        if self._repo.get_by_name(company_id, fields["name"]) is not None:
            raise ConflictException(
                message=f"A plan template named '{fields['name']}' already exists.",
                details={"name": fields["name"]},
            )
        # Explicit Python-side defaults for every server_default-backed
        # boolean, matching CrmPipelineService.create()'s established
        # convention — never rely on a bare server_default alone, since a
        # freshly-created row's Python attributes are only fully correct
        # after an explicit set (server_default is a DB-side fallback for
        # rows written outside this service, not a substitute for setting
        # the value here).
        fields.setdefault("is_active", True)
        fields.setdefault("requires_approval", False)
        template = InstallmentPlanTemplate(
            company_id=company_id, created_by=actor_id, **fields
        )
        return self._repo.create(template)

    def update(
        self, company_id: UUID, template_id: UUID, **fields: Any
    ) -> InstallmentPlanTemplate:
        """Edit an existing template. A name change is re-validated for
        uniqueness against every other (non-deleted) template."""
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
            )
        template = self._repo.get_by_id_or_none(template_id, company_id)
        if template is None:
            raise InstallmentNotFoundError("InstallmentPlanTemplate", str(template_id))
        self._validate_fields({**self._current_fields(template), **fields})

        new_name = fields.get("name")
        if new_name is not None and new_name != template.name:
            existing = self._repo.get_by_name(company_id, new_name)
            if existing is not None and existing.id != template.id:
                raise ConflictException(
                    message=f"A plan template named '{new_name}' already exists.",
                    details={"name": new_name},
                )

        for key, value in fields.items():
            setattr(template, key, value)
        return self._repo.update(template)

    def deactivate(
        self, company_id: UUID, template_id: UUID
    ) -> InstallmentPlanTemplate:
        """Deactivate a template — blocks new use, never affects existing
        contracts (FR-INST-013)."""
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
            )
        template = self._repo.get_by_id_or_none(template_id, company_id)
        if template is None:
            raise InstallmentNotFoundError("InstallmentPlanTemplate", str(template_id))
        template.is_active = False
        return self._repo.update(template)

    @staticmethod
    def _current_fields(template: InstallmentPlanTemplate) -> dict[str, Any]:
        return {"installment_count": template.installment_count}

    @staticmethod
    def _validate_fields(fields: dict[str, Any]) -> None:
        installment_count = fields.get("installment_count")
        if installment_count is not None and installment_count <= 0:
            raise ValidationException(
                message="installment_count must be greater than 0.",
                details={"installment_count": installment_count},
            )

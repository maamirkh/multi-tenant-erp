"""InstallmentConfigurationService — tenant/branch policy configuration.

Validates ``min_term <= max_term`` and that at most one of
``min_down_payment_pct``/``min_down_payment_amount`` is set (data-model.md
"InstallmentConfiguration" validation rules) before any write.

Spec ref: specs/010-installments/data-model.md "InstallmentConfiguration".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from core.exceptions.base import ValidationException
from modules.installments.models.configuration import InstallmentConfiguration
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)


class InstallmentConfigurationService:
    """Service layer for tenant/branch Installments configuration."""

    def __init__(
        self,
        repo: InstallmentConfigurationRepository,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self._repo = repo
        self._access_policy = access_policy

    def get_effective_config(
        self, company_id: UUID, branch_id: UUID | None = None
    ) -> InstallmentConfiguration | None:
        """Resolve the effective configuration for ``branch_id``: a
        branch-specific override wins if one exists, otherwise the
        company-level default row, otherwise ``None`` (never configured).
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.READ
            )
        return self._repo.get_effective_config(company_id, branch_id)

    def upsert_config(
        self,
        company_id: UUID,
        branch_id: UUID | None,
        actor_id: UUID | None,
        **fields: Any,
    ) -> InstallmentConfiguration:
        """Create or update the configuration row for ``branch_id`` (or
        the company-level default row when ``branch_id`` is ``None``).

        Validates the two cross-field business rules before any write:
        ``min_term <= max_term`` and at most one of
        ``min_down_payment_pct``/``min_down_payment_amount`` populated.

        Entitlement note: spec FR-INST-353/§34 OQ-2 explicitly classify
        "configuration changes" as a blocked-while-disabled ORIGINATION
        operation — this overrides plan.md §16.1's permission-catalogue
        table, which loosely labels ``installments.config.manage`` as
        "ADMIN" in the RBAC sense (an admin-level permission), not the
        distinct ``InstallmentOperationClass.ADMIN`` entitlement-bypass
        sense (reserved for the module enable/disable toggle itself, per
        §15.2's own code). Spec outranks Plan's summary table per the
        documented authority order.
        """
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
            )
        self._validate_fields(fields)

        existing = (
            self._repo.get_branch_override(company_id, branch_id)
            if branch_id is not None
            else self._repo.get_company_default(company_id)
        )

        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            return self._repo.update(existing)

        # Explicit Python-side defaults for every server_default-backed
        # field, matching CrmPipelineService.create()'s established
        # convention — never rely on a bare server_default alone.
        fields.setdefault("rounding_policy", "ROUND_HALF_UP")
        fields.setdefault("grace_period_days", 0)
        fields.setdefault("backdating_allowed", False)
        fields.setdefault("writeoff_requires_permission", True)
        fields.setdefault("cure_enabled", False)

        config = InstallmentConfiguration(
            company_id=company_id,
            branch_id=branch_id,
            created_by=actor_id,
            **fields,
        )
        return self._repo.create(config)

    @staticmethod
    def _validate_fields(fields: dict[str, Any]) -> None:
        min_term = fields.get("min_term")
        max_term = fields.get("max_term")
        if min_term is not None and max_term is not None and min_term > max_term:
            raise ValidationException(
                message="min_term must be less than or equal to max_term.",
                details={"min_term": min_term, "max_term": max_term},
            )

        pct: Decimal | None = fields.get("min_down_payment_pct")
        amount: Decimal | None = fields.get("min_down_payment_amount")
        if pct is not None and amount is not None:
            raise ValidationException(
                message=(
                    "At most one of min_down_payment_pct/"
                    "min_down_payment_amount may be set."
                ),
                details={
                    "min_down_payment_pct": str(pct),
                    "min_down_payment_amount": str(amount),
                },
            )

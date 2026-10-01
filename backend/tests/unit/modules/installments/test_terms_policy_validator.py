"""Unit tests for InstallmentTermsPolicyValidator (tasks.md T073D,
FR-INST-011, plan.md §10.6).

``TestValidatorArithmetic`` uses a lightweight fake config object — the
validator only reads plain attributes, never ORM-specific behavior, so
no database is needed for the bounds-checking logic itself.
``TestBranchOverrideResolution`` uses the real
``InstallmentConfigurationService``/repository (SQLite ``db_session``)
to prove the validator enforces whichever config
``get_effective_config()`` actually resolves — a branch override, not
the company default — when both exist.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentTermsPolicyViolationError
from modules.installments.models.configuration import InstallmentConfiguration
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.terms_policy_validator import (
    InstallmentTermsPolicyValidator,
)


@dataclass
class _FakeConfig:
    allowed_frequencies: list[str] = field(default_factory=lambda: ["MONTHLY"])
    min_term: int = 6
    max_term: int = 24
    min_down_payment_pct: Decimal | None = None
    min_down_payment_amount: Decimal | None = None
    max_financed_amount: Decimal | None = None


def _as_config(fake: _FakeConfig) -> InstallmentConfiguration:
    """``_FakeConfig`` structurally mirrors the plain attributes the
    validator actually reads (see module docstring); casting documents
    that intentional duck-typing rather than widening the validator's
    real parameter type."""
    return cast(InstallmentConfiguration, fake)


def _violations(exc: InstallmentTermsPolicyViolationError) -> dict[str, str]:
    return cast(dict[str, str], exc.details["violations"])


def _valid_kwargs() -> dict[str, Any]:
    return dict(
        frequency="MONTHLY",
        installment_count=12,
        principal_amount=Decimal("1000"),
        down_payment_amount=Decimal("100"),
        financed_amount=Decimal("900"),
    )


class TestValidatorArithmetic:
    def test_valid_terms_pass(self) -> None:
        InstallmentTermsPolicyValidator.validate(
            _as_config(_FakeConfig()), **_valid_kwargs()
        )

    def test_unconfigured_tenant_is_a_noop(self) -> None:
        InstallmentTermsPolicyValidator.validate(None, **_valid_kwargs())

    def test_disallowed_frequency_rejected(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["frequency"] = "WEEKLY"
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(
                _as_config(_FakeConfig()), **kwargs
            )
        assert exc_info.value.code == "TERMS_POLICY_VIOLATION"
        assert "frequency" in _violations(exc_info.value)

    def test_installment_count_below_min_term_rejected(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["installment_count"] = 3
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(
                _as_config(_FakeConfig()), **kwargs
            )
        assert "installment_count" in _violations(exc_info.value)

    def test_installment_count_above_max_term_rejected(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["installment_count"] = 36
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(
                _as_config(_FakeConfig()), **kwargs
            )
        assert "installment_count" in _violations(exc_info.value)

    def test_down_payment_below_configured_flat_minimum_rejected(self) -> None:
        config = _FakeConfig(min_down_payment_amount=Decimal("200"))
        kwargs = _valid_kwargs()
        kwargs["down_payment_amount"] = Decimal("100")
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(_as_config(config), **kwargs)
        assert "down_payment_amount" in _violations(exc_info.value)

    def test_down_payment_below_configured_percentage_minimum_rejected(self) -> None:
        config = _FakeConfig(min_down_payment_pct=Decimal("20"))
        kwargs = _valid_kwargs()
        kwargs["principal_amount"] = Decimal("1000")
        kwargs["down_payment_amount"] = Decimal("100")  # 10% < required 20%
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(_as_config(config), **kwargs)
        assert "down_payment_amount" in _violations(exc_info.value)

    def test_down_payment_meeting_percentage_minimum_passes(self) -> None:
        config = _FakeConfig(min_down_payment_pct=Decimal("20"))
        kwargs = _valid_kwargs()
        kwargs["principal_amount"] = Decimal("1000")
        kwargs["down_payment_amount"] = Decimal("200")  # exactly 20%
        InstallmentTermsPolicyValidator.validate(_as_config(config), **kwargs)

    def test_financed_amount_exceeding_max_rejected(self) -> None:
        config = _FakeConfig(max_financed_amount=Decimal("500"))
        kwargs = _valid_kwargs()
        kwargs["financed_amount"] = Decimal("900")
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(_as_config(config), **kwargs)
        assert "financed_amount" in _violations(exc_info.value)

    def test_multiple_simultaneous_violations_all_reported(self) -> None:
        config = _FakeConfig(
            allowed_frequencies=["MONTHLY"],
            min_term=6,
            max_term=24,
            max_financed_amount=Decimal("100"),
        )
        with pytest.raises(InstallmentTermsPolicyViolationError) as exc_info:
            InstallmentTermsPolicyValidator.validate(
                _as_config(config),
                frequency="WEEKLY",
                installment_count=1,
                principal_amount=Decimal("1000"),
                down_payment_amount=Decimal("0"),
                financed_amount=Decimal("1000"),
            )
        violations = _violations(exc_info.value)
        assert {"frequency", "installment_count", "financed_amount"} <= set(violations)


class TestBranchOverrideResolution:
    def test_branch_override_bounds_enforced_over_company_default(
        self, db_session: Session
    ) -> None:
        """A company-default row allows up to 36 installments; a
        branch-specific override for the SAME company caps it at 12.
        Resolving for that branch must enforce 12, not 36."""
        company_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        repo = InstallmentConfigurationRepository(db_session)
        service = InstallmentConfigurationService(repo)

        service.upsert_config(
            company_id=company_id,
            branch_id=None,
            actor_id=None,
            allowed_frequencies=["MONTHLY"],
            min_term=1,
            max_term=36,
        )
        service.upsert_config(
            company_id=company_id,
            branch_id=branch_id,
            actor_id=None,
            allowed_frequencies=["MONTHLY"],
            min_term=1,
            max_term=12,
        )

        company_default = service.get_effective_config(company_id, branch_id=None)
        branch_override = service.get_effective_config(company_id, branch_id=branch_id)

        terms: dict[str, Any] = dict(
            frequency="MONTHLY",
            installment_count=24,
            principal_amount=Decimal("1000"),
            down_payment_amount=Decimal("100"),
            financed_amount=Decimal("900"),
        )

        # Passes against the company's wider default bound.
        InstallmentTermsPolicyValidator.validate(company_default, **terms)

        # Rejected against the branch's narrower override.
        with pytest.raises(InstallmentTermsPolicyViolationError):
            InstallmentTermsPolicyValidator.validate(branch_override, **terms)

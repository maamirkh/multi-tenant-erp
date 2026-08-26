"""Unit tests for InstallmentQuoteService.preview() (tasks.md T069,
FR-INST-030-032).

Uses fake eligibility/invoice/configuration collaborators (unit-level) so
these tests exercise only the quote service's own composition logic —
resolving eligible/invoice amount and the tenant rounding policy, then
delegating arithmetic entirely to ``ScheduleEngine``. Real end-to-end
wiring through the actual gateways is proven by the live HTTP smoke
verification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest

from core.exceptions.base import ValidationException
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.services.eligibility_service import EligibilityResult
from modules.installments.services.quote_service import InstallmentQuoteService


@dataclass
class _FakeInvoice:
    total_amount: Decimal


@dataclass
class _FakeConfig:
    rounding_policy: str
    allowed_frequencies: list[str] = field(
        default_factory=lambda: ["WEEKLY", "MONTHLY", "QUARTERLY"]
    )
    min_term: int = 1
    max_term: int = 1000
    min_down_payment_pct: Decimal | None = None
    min_down_payment_amount: Decimal | None = None
    max_financed_amount: Decimal | None = None


class _FakeEligibilityService:
    def __init__(self, result: EligibilityResult | None = None, error=None) -> None:
        self._result = result
        self._error = error

    def check_invoice_eligibility(self, company_id, sales_invoice_id):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeInvoiceGateway:
    def __init__(self, invoice: _FakeInvoice) -> None:
        self._invoice = invoice

    def get_invoice(self, company_id, sales_invoice_id):
        return self._invoice


class _FakeConfigurationService:
    def __init__(self, config: _FakeConfig | None) -> None:
        self._config = config

    def get_effective_config(self, company_id, branch_id=None):
        return self._config


def _make_service(
    *, eligible_amount: Decimal, invoice_amount: Decimal, rounding_policy: str | None
) -> InstallmentQuoteService:
    customer_id = uuid.uuid4()
    eligibility_result = EligibilityResult(
        sales_invoice_id=uuid.uuid4(),
        customer_id=customer_id,
        currency_code="USD",
        outstanding_amount=eligible_amount,
    )
    config = _FakeConfig(rounding_policy=rounding_policy) if rounding_policy else None
    return InstallmentQuoteService(
        eligibility_service=_FakeEligibilityService(result=eligibility_result),
        invoice_gateway=_FakeInvoiceGateway(_FakeInvoice(total_amount=invoice_amount)),
        configuration_service=_FakeConfigurationService(config),
    )


class TestQuotePreviewComposition:
    def test_preview_returns_full_fr_inst_030_field_set(self) -> None:
        svc = _make_service(
            eligible_amount=Decimal("900"),
            invoice_amount=Decimal("1000"),
            rounding_policy="ROUND_HALF_UP",
        )
        preview = svc.preview(
            uuid.uuid4(),
            sales_invoice_id=uuid.uuid4(),
            down_payment_amount=Decimal("100"),
            installment_count=4,
            frequency="MONTHLY",
            first_due_date=date(2026, 2, 1),
            markup_amount=Decimal("40"),
        )
        assert preview.invoice_amount == Decimal("1000")
        assert preview.eligible_amount == Decimal("900")
        assert preview.down_payment_amount == Decimal("100")
        assert preview.financed_principal == Decimal("800")
        assert preview.markup_amount == Decimal("40")
        assert preview.contractual_total == Decimal("840")
        assert len(preview.per_installment_amounts) == 4
        assert sum(preview.per_installment_amounts) == Decimal("840")
        assert preview.final_installment_amount == preview.per_installment_amounts[-1]
        assert preview.expected_completion_date == date(2026, 5, 1)
        assert preview.currency_code == "USD"

    def test_preview_uses_tenant_configured_rounding_policy(self) -> None:
        svc = _make_service(
            eligible_amount=Decimal("5.000001"),
            invoice_amount=Decimal("5.000001"),
            rounding_policy="ROUND_HALF_EVEN",
        )
        preview = svc.preview(
            uuid.uuid4(),
            sales_invoice_id=uuid.uuid4(),
            down_payment_amount=Decimal("0"),
            installment_count=2,
            frequency="MONTHLY",
            first_due_date=date(2026, 1, 1),
        )
        # 5.000001 / 2 = 2.5000005 exactly — ROUND_HALF_EVEN ties to the
        # even 6th digit (0), unlike ROUND_HALF_UP which would round up.
        assert preview.per_installment_amounts[0] == Decimal("2.500000")

    def test_preview_defaults_to_round_half_up_when_unconfigured(self) -> None:
        svc = _make_service(
            eligible_amount=Decimal("5.000001"),
            invoice_amount=Decimal("5.000001"),
            rounding_policy=None,
        )
        preview = svc.preview(
            uuid.uuid4(),
            sales_invoice_id=uuid.uuid4(),
            down_payment_amount=Decimal("0"),
            installment_count=2,
            frequency="MONTHLY",
            first_due_date=date(2026, 1, 1),
        )
        assert preview.per_installment_amounts[0] == Decimal("2.500001")

    def test_preview_never_persists_or_audits(self) -> None:
        """Structural guard: InstallmentQuoteService must not depend on
        any repository or audit service (FR-INST-032) — only read-only
        collaborators."""
        import inspect

        source = inspect.getsource(InstallmentQuoteService)
        assert "Repository" not in source
        assert "AuditService" not in source
        assert ".create(" not in source
        assert ".commit(" not in source

    def test_unsupported_frequency_surfaces_as_validation_exception_not_500(
        self,
    ) -> None:
        """A client-supplied frequency the engine rejects (a ValueError,
        by design a pure-function input-contract violation) must surface
        as a documented 422 at this client-facing boundary, never an
        unhandled 500. Uses an unconfigured tenant (no
        ``InstallmentConfiguration`` row) so ``InstallmentTermsPolicyValidator``
        no-ops and it is genuinely ``ScheduleEngine``'s own ValueError
        translation being exercised here, not the (separately tested)
        policy-bounds check."""
        svc = _make_service(
            eligible_amount=Decimal("900"),
            invoice_amount=Decimal("1000"),
            rounding_policy=None,
        )
        with pytest.raises(ValidationException) as exc_info:
            svc.preview(
                uuid.uuid4(),
                sales_invoice_id=uuid.uuid4(),
                down_payment_amount=Decimal("0"),
                installment_count=2,
                frequency="DAILY",
                first_due_date=date(2026, 1, 1),
            )
        assert exc_info.value.code == "INVALID_SCHEDULE_TERMS"

    def test_disallowed_frequency_rejected_by_policy_validator_when_configured(
        self,
    ) -> None:
        """When a tenant HAS a configuration row, a disallowed frequency
        is now caught earlier by ``InstallmentTermsPolicyValidator``
        (TERMS_POLICY_VIOLATION), before ever reaching ``ScheduleEngine``."""
        svc = _make_service(
            eligible_amount=Decimal("900"),
            invoice_amount=Decimal("1000"),
            rounding_policy="ROUND_HALF_UP",
        )
        with pytest.raises(ValidationException) as exc_info:
            svc.preview(
                uuid.uuid4(),
                sales_invoice_id=uuid.uuid4(),
                down_payment_amount=Decimal("0"),
                installment_count=2,
                frequency="DAILY",
                first_due_date=date(2026, 1, 1),
            )
        assert exc_info.value.code == "TERMS_POLICY_VIOLATION"

    def test_ineligible_invoice_propagates_the_eligibility_error(self) -> None:
        svc = InstallmentQuoteService(
            eligibility_service=_FakeEligibilityService(
                error=InstallmentNotFoundError("SalesInvoice", "x")
            ),
            invoice_gateway=_FakeInvoiceGateway(
                _FakeInvoice(total_amount=Decimal("0"))
            ),
            configuration_service=_FakeConfigurationService(None),
        )
        with pytest.raises(InstallmentNotFoundError):
            svc.preview(
                uuid.uuid4(),
                sales_invoice_id=uuid.uuid4(),
                down_payment_amount=Decimal("0"),
                installment_count=2,
                frequency="MONTHLY",
                first_due_date=date(2026, 1, 1),
            )

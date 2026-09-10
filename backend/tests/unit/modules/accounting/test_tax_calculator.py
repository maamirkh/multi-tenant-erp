"""Unit tests for TaxCalculator — Phase 11.

Tests (tasks.md T244):
  - Correct rate for transaction date
  - Date range boundary (effective_from, effective_to)
  - Zero-rated returns 0.00 but reportable
  - Tax group applies all member codes

Spec ref: specs/008-accounting-finance/tasks.md T244
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_tax_calculator
from modules.accounting.exceptions import PostingValidationError, TaxCodeNotFoundError
from modules.accounting.models.coa import Account
from modules.accounting.models.tax import TaxCode, TaxGroup, TaxGroupLine, TaxRate
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.tax import (
    TaxCodeRepository,
    TaxGroupLineRepository,
    TaxGroupRepository,
    TaxRateRepository,
)
from modules.accounting.services.tax_calculator import TaxCalculator


@pytest.fixture
def setup(db_session: Session) -> dict[str, Any]:
    account_repo = AccountRepository(db_session)
    company_id = uuid4()

    vat_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2200",
            account_name="VAT Payable",
            account_type="LIABILITY",
        )
    )
    provincial_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2210",
            account_name="Provincial Tax Payable",
            account_type="LIABILITY",
        )
    )
    zero_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2220",
            account_name="Zero-Rated Tax",
            account_type="LIABILITY",
        )
    )

    tax_code_repo = TaxCodeRepository(db_session)
    tax_rate_repo = TaxRateRepository(db_session)

    vat_code = tax_code_repo.create(
        TaxCode(
            company_id=company_id,
            tax_code="VAT-STD",
            tax_name="Standard VAT",
            tax_type="VAT",
            applicability="BOTH",
            gl_account_id=vat_gl.id,
            is_input_tax_recoverable=True,
        )
    )
    provincial_code = tax_code_repo.create(
        TaxCode(
            company_id=company_id,
            tax_code="PROV-TAX",
            tax_name="Provincial Tax",
            tax_type="SALES_TAX",
            applicability="SALES",
            gl_account_id=provincial_gl.id,
        )
    )
    zero_rated_code = tax_code_repo.create(
        TaxCode(
            company_id=company_id,
            tax_code="ZERO",
            tax_name="Zero-Rated",
            tax_type="ZERO_RATED",
            applicability="SALES",
            gl_account_id=zero_gl.id,
        )
    )
    out_of_scope_code = tax_code_repo.create(
        TaxCode(
            company_id=company_id,
            tax_code="OOS",
            tax_name="Out of Scope",
            tax_type="OUT_OF_SCOPE",
            applicability="BOTH",
            gl_account_id=zero_gl.id,
        )
    )

    return {
        "company_id": company_id,
        "vat_code": vat_code,
        "provincial_code": provincial_code,
        "zero_rated_code": zero_rated_code,
        "out_of_scope_code": out_of_scope_code,
        "tax_code_repo": tax_code_repo,
        "tax_rate_repo": tax_rate_repo,
    }


@pytest.fixture
def calculator(db_session: Session) -> TaxCalculator:
    return build_tax_calculator(db_session)


class TestRateResolutionByTransactionDate:
    def test_correct_rate_applied_for_transaction_date(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 5, 31),
                rate=Decimal("15.0"),
            )
        )
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 6, 1),
                effective_to=None,
                rate=Decimal("17.5"),
            )
        )

        results_before = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["vat_code"].id,
            base_amount=Decimal("1000.00"),
            transaction_date=date(2026, 3, 15),
        )
        assert results_before[0].tax_rate == Decimal("15.0")
        assert results_before[0].tax_amount == Decimal("150.00")

        results_after = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["vat_code"].id,
            base_amount=Decimal("1000.00"),
            transaction_date=date(2026, 7, 1),
        )
        assert results_after[0].tax_rate == Decimal("17.5")
        assert results_after[0].tax_amount == Decimal("175.00")

    def test_date_range_boundaries_are_inclusive(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 5, 31),
                rate=Decimal("15.0"),
            )
        )
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 6, 1),
                effective_to=None,
                rate=Decimal("17.5"),
            )
        )

        last_day_old = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["vat_code"].id,
            base_amount=Decimal("100.00"),
            transaction_date=date(2026, 5, 31),
        )
        assert last_day_old[0].tax_rate == Decimal("15.0")

        first_day_new = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["vat_code"].id,
            base_amount=Decimal("100.00"),
            transaction_date=date(2026, 6, 1),
        )
        assert first_day_new[0].tax_rate == Decimal("17.5")

    def test_no_rate_configured_for_date_raises(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 6, 1),
                effective_to=None,
                rate=Decimal("15.0"),
            )
        )
        with pytest.raises(PostingValidationError):
            calculator.calculate(
                company_id=setup["company_id"],
                tax_code_or_group_id=setup["vat_code"].id,
                base_amount=Decimal("100.00"),
                transaction_date=date(2026, 1, 1),
            )


class TestZeroRatedAndOutOfScope:
    def test_zero_rated_returns_zero_amount_but_still_reportable(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["zero_rated_code"].id,
                effective_from=date(2026, 1, 1),
                effective_to=None,
                rate=Decimal("0"),
            )
        )
        results = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["zero_rated_code"].id,
            base_amount=Decimal("500.00"),
            transaction_date=date(2026, 3, 1),
        )
        assert len(results) == 1
        assert results[0].tax_amount == Decimal("0.00")
        assert results[0].base_amount == Decimal("500.00")

    def test_out_of_scope_produces_no_line_at_all(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        # No TaxRate configured at all — OUT_OF_SCOPE must not need one.
        results = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["out_of_scope_code"].id,
            base_amount=Decimal("500.00"),
            transaction_date=date(2026, 3, 1),
        )
        assert results == []


class TestTaxGroup:
    def test_tax_group_applies_all_member_codes_simultaneously(
        self, calculator: TaxCalculator, setup: dict[str, Any], db_session: Session
    ) -> None:
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 1, 1),
                effective_to=None,
                rate=Decimal("15.0"),
            )
        )
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["provincial_code"].id,
                effective_from=date(2026, 1, 1),
                effective_to=None,
                rate=Decimal("5.0"),
            )
        )

        group_repo = TaxGroupRepository(db_session)
        line_repo = TaxGroupLineRepository(db_session)
        group = group_repo.create(
            TaxGroup(
                company_id=setup["company_id"],
                group_code="COMBO",
                group_name="Federal + Provincial",
                applicability="SALES",
            )
        )
        line_repo.create(
            TaxGroupLine(
                company_id=setup["company_id"],
                tax_group_id=group.id,
                tax_code_id=setup["vat_code"].id,
                display_order=1,
            )
        )
        line_repo.create(
            TaxGroupLine(
                company_id=setup["company_id"],
                tax_group_id=group.id,
                tax_code_id=setup["provincial_code"].id,
                display_order=2,
            )
        )

        results = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=group.id,
            base_amount=Decimal("1000.00"),
            transaction_date=date(2026, 3, 1),
        )
        assert len(results) == 2
        by_code = {r.tax_code: r for r in results}
        assert by_code["VAT-STD"].tax_amount == Decimal("150.00")
        assert by_code["PROV-TAX"].tax_amount == Decimal("50.00")

    def test_unknown_id_raises_not_found(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        with pytest.raises(TaxCodeNotFoundError):
            calculator.calculate(
                company_id=setup["company_id"],
                tax_code_or_group_id=uuid4(),
                base_amount=Decimal("100.00"),
                transaction_date=date(2026, 1, 1),
            )


class TestTaxInclusiveCalculation:
    def test_tax_inclusive_backs_out_the_tax_portion(
        self, calculator: TaxCalculator, setup: dict[str, Any]
    ) -> None:
        setup["tax_rate_repo"].create(
            TaxRate(
                company_id=setup["company_id"],
                tax_code_id=setup["vat_code"].id,
                effective_from=date(2026, 1, 1),
                effective_to=None,
                rate=Decimal("15.0"),
            )
        )
        results = calculator.calculate(
            company_id=setup["company_id"],
            tax_code_or_group_id=setup["vat_code"].id,
            base_amount=Decimal("115.00"),
            transaction_date=date(2026, 3, 1),
            is_tax_inclusive=True,
        )
        assert results[0].base_amount == Decimal("100.00")
        assert results[0].tax_amount == Decimal("15.00")

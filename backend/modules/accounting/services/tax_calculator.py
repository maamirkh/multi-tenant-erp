"""TaxCalculator — Tax Engine domain service — Phase 11.

Computes tax on a transaction line based on the applicable tax code or
tax group. See ``TaxAmount`` — see ``schemas/gl.py``'s ``PostingResult``
convention: this module's ``TaxAmount`` is the domain-layer value object;
``schemas/tax.py`` carries the corresponding API schema.

Reportability rule (spec.md §23.2 tax type table):
  - ZERO_RATED / EXEMPT: still reportable — a ``TaxCode`` of either type
    is expected to carry a ``TaxRate`` configured at 0%, so the normal
    calculation path naturally returns a 0.00 ``TaxAmount`` line (no
    special-casing needed: a real rate lookup at 0% IS the "reportable
    zero" spec.md describes).
  - OUT_OF_SCOPE: spec.md says "not subject to tax and not reportable" —
    this IS special-cased: no ``TaxAmount`` line is produced at all,
    regardless of whether a rate is configured.

Compound tax (spec.md §23.2: "tax calculated on a base that includes
another tax"): within a tax group, member codes are evaluated in
``display_order``; a member whose ``tax_type`` is COMPOUND uses
``original_base_amount + sum(tax_amounts already computed in this group)``
as its own base, rather than the group's raw input amount.

Spec ref: specs/008-accounting-finance/spec.md §23 Tax Management
Data model: specs/008-accounting-finance/data-model.md §4.2 TaxCalculator
Tasks ref: specs/008-accounting-finance/tasks.md T231
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.constants import RoundingRule, TaxType
from modules.accounting.exceptions import PostingValidationError, TaxCodeNotFoundError
from modules.accounting.models.tax import TaxCode
from modules.accounting.repositories.tax import (
    TaxCodeRepository,
    TaxGroupLineRepository,
    TaxGroupRepository,
    TaxRateRepository,
)

_TAX_DECIMAL_PLACES = Decimal("0.01")

_ROUNDING_MODE_BY_RULE: dict[str, str] = {
    RoundingRule.HALF_UP.value: ROUND_HALF_UP,
    RoundingRule.HALF_EVEN.value: ROUND_HALF_EVEN,
    RoundingRule.DOWN.value: ROUND_DOWN,
    RoundingRule.UP.value: ROUND_UP,
}

#: Tax types that produce no reportable TaxAmount line at all (spec.md §23.2).
_NON_REPORTABLE_TYPES = frozenset({TaxType.OUT_OF_SCOPE.value})

#: Tax types with a real, nonzero rate lookup that still fold into a
#: compound base when they appear later in a tax group's display order.
_COMPOUND_TYPES = frozenset({TaxType.COMPOUND.value})


@dataclass(frozen=True)
class TaxAmount:
    """Domain-layer value object — one calculated tax line.
    data-model.md §3 Value Objects: tax_code, base_amount, tax_rate, tax_amount.
    """

    tax_code_id: UUID
    tax_code: str
    base_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    gl_account_id: UUID
    is_input_tax_recoverable: bool


class TaxCalculator:
    """Domain service: resolves the effective rate and computes tax amounts."""

    def __init__(
        self,
        db: Session,
        tax_code_repo: TaxCodeRepository,
        tax_rate_repo: TaxRateRepository,
        tax_group_repo: TaxGroupRepository,
        tax_group_line_repo: TaxGroupLineRepository,
    ) -> None:
        self.db = db
        self._tax_codes = tax_code_repo
        self._tax_rates = tax_rate_repo
        self._tax_groups = tax_group_repo
        self._tax_group_lines = tax_group_line_repo

    def calculate(
        self,
        company_id: UUID,
        tax_code_or_group_id: UUID,
        base_amount: Decimal,
        transaction_date: date,
        is_tax_inclusive: bool = False,
    ) -> list[TaxAmount]:
        """Calculate tax for ``base_amount`` using either a single TaxCode
        or every member of a TaxGroup, applied simultaneously.
        """
        tax_code = self._tax_codes.get_by_id_or_none(
            id=tax_code_or_group_id, company_id=company_id
        )
        if tax_code is not None:
            amount = self._calculate_one(
                company_id, tax_code, base_amount, transaction_date, is_tax_inclusive
            )
            return [amount] if amount is not None else []

        tax_group = self._tax_groups.get_by_id_or_none(
            id=tax_code_or_group_id, company_id=company_id
        )
        if tax_group is not None:
            lines = self._tax_group_lines.find_by_group(company_id, tax_group.id)
            results: list[TaxAmount] = []
            running_total = Decimal("0")
            for line in lines:
                member_code = self._tax_codes.get_by_id_or_none(
                    id=line.tax_code_id, company_id=company_id
                )
                if member_code is None:
                    continue
                effective_base = (
                    base_amount + running_total
                    if member_code.tax_type in _COMPOUND_TYPES
                    else base_amount
                )
                amount = self._calculate_one(
                    company_id,
                    member_code,
                    effective_base,
                    transaction_date,
                    is_tax_inclusive,
                )
                if amount is not None:
                    results.append(amount)
                    running_total += amount.tax_amount
            return results

        raise TaxCodeNotFoundError(tax_code_id=str(tax_code_or_group_id))

    def _calculate_one(
        self,
        company_id: UUID,
        tax_code: TaxCode,
        base_amount: Decimal,
        transaction_date: date,
        is_tax_inclusive: bool,
    ) -> TaxAmount | None:
        if tax_code.tax_type in _NON_REPORTABLE_TYPES:
            return None

        rate_record = self._tax_rates.find_effective_at(
            company_id, tax_code.id, transaction_date
        )
        if rate_record is None:
            raise PostingValidationError(
                f"No effective tax rate found for tax code '{tax_code.tax_code}' "
                f"on {transaction_date.isoformat()}."
            )

        rate = rate_record.rate
        rounding_mode = _ROUNDING_MODE_BY_RULE.get(
            rate_record.rounding_rule, ROUND_HALF_UP
        )

        if is_tax_inclusive:
            net_base = (base_amount / (1 + rate / Decimal("100"))).quantize(
                _TAX_DECIMAL_PLACES, rounding=rounding_mode
            )
            tax_amount = (base_amount - net_base).quantize(
                _TAX_DECIMAL_PLACES, rounding=rounding_mode
            )
        else:
            net_base = base_amount
            tax_amount = (base_amount * rate / Decimal("100")).quantize(
                _TAX_DECIMAL_PLACES, rounding=rounding_mode
            )

        return TaxAmount(
            tax_code_id=tax_code.id,
            tax_code=tax_code.tax_code,
            base_amount=net_base,
            tax_rate=rate,
            tax_amount=tax_amount,
            gl_account_id=tax_code.gl_account_id,
            is_input_tax_recoverable=tax_code.is_input_tax_recoverable,
        )

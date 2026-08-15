"""Pydantic v2 schemas for the Tax Engine — Phase 11.

  TaxCodeCreateRequest / TaxCodeUpdateRequest / TaxCodeResponse
  TaxRateCreateRequest / TaxRateResponse
  TaxGroupCreateRequest / TaxGroupResponse
  TaxGroupLineCreateRequest / TaxGroupLineResponse
  TaxCalculationRequest / TaxAmountResponse / TaxCalculationResult
  TaxSummaryReport / TaxSummaryReportRow
  TaxDetailRow
  WHTReport / WHTReportRow

Spec ref: specs/008-accounting-finance/tasks.md T234
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Tax codes
# ---------------------------------------------------------------------------


class TaxCodeCreateRequest(AccountingBaseSchema):
    tax_code: str = Field(..., min_length=1, max_length=20)
    tax_name: str = Field(..., min_length=1, max_length=200)
    tax_type: str = Field(
        ...,
        pattern="^(SALES_TAX|VAT|GST|WITHHOLDING|COMPOUND|EXEMPT|ZERO_RATED|OUT_OF_SCOPE)$",
    )
    applicability: str = Field(..., pattern="^(SALES|PURCHASES|BOTH)$")
    gl_account_id: UUID
    is_input_tax_recoverable: bool = False
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class TaxCodeUpdateRequest(AccountingBaseSchema):
    tax_name: str | None = None
    is_input_tax_recoverable: bool | None = None
    country_code: str | None = None
    is_active: bool | None = None


class TaxCodeResponse(AccountingBaseSchema):
    id: UUID
    tax_code: str
    tax_name: str
    tax_type: str
    applicability: str
    gl_account_id: UUID
    is_input_tax_recoverable: bool
    country_code: str | None = None
    is_active: bool


# ---------------------------------------------------------------------------
# Tax rates
# ---------------------------------------------------------------------------


class TaxRateCreateRequest(AccountingBaseSchema):
    effective_from: date
    effective_to: date | None = None
    rate: Decimal = Field(..., ge=0)
    rounding_rule: str = Field(
        default="HALF_UP", pattern="^(HALF_UP|HALF_EVEN|DOWN|UP)$"
    )


class TaxRateResponse(AccountingBaseSchema):
    id: UUID
    tax_code_id: UUID
    effective_from: date
    effective_to: date | None = None
    rate: Decimal
    rounding_rule: str


# ---------------------------------------------------------------------------
# Tax groups
# ---------------------------------------------------------------------------


class TaxGroupCreateRequest(AccountingBaseSchema):
    group_code: str = Field(..., min_length=1, max_length=20)
    group_name: str = Field(..., min_length=1, max_length=200)
    applicability: str = Field(..., pattern="^(SALES|PURCHASES|BOTH)$")


class TaxGroupResponse(AccountingBaseSchema):
    id: UUID
    group_code: str
    group_name: str
    applicability: str
    is_active: bool


class TaxGroupLineCreateRequest(AccountingBaseSchema):
    tax_code_id: UUID
    display_order: int = 0


class TaxGroupLineResponse(AccountingBaseSchema):
    id: UUID
    tax_group_id: UUID
    tax_code_id: UUID
    display_order: int


# ---------------------------------------------------------------------------
# Tax calculation
# ---------------------------------------------------------------------------


class TaxCalculationRequest(AccountingBaseSchema):
    tax_code_or_group_id: UUID
    base_amount: Decimal = Field(..., gt=0)
    transaction_date: date
    is_tax_inclusive: bool = False


class TaxAmountResponse(AccountingBaseSchema):
    tax_code_id: UUID
    tax_code: str
    base_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    gl_account_id: UUID
    is_input_tax_recoverable: bool


class TaxCalculationResult(AccountingBaseSchema):
    lines: list[TaxAmountResponse]
    total_tax_amount: Decimal


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class TaxSummaryReportRow(AccountingBaseSchema):
    tax_code_id: UUID
    tax_code: str
    tax_name: str
    output_tax: Decimal
    input_tax: Decimal
    is_input_tax_recoverable: bool


class TaxSummaryReport(AccountingBaseSchema):
    period_start: date
    period_end: date
    rows: list[TaxSummaryReportRow]
    total_output_tax: Decimal
    total_input_tax: Decimal
    net_payable: Decimal


class TaxDetailRow(AccountingBaseSchema):
    journal_entry_id: UUID
    journal_number: str
    posting_date: date
    account_id: UUID
    account_code: str
    debit_amount: Decimal
    credit_amount: Decimal
    description: str | None = None
    reference: str | None = None
    source_document_type: str | None = None
    source_document_id: UUID | None = None
    tax_code_id: UUID
    tax_code: str
    tax_type: str


class WHTReportRow(AccountingBaseSchema):
    supplier_id: UUID
    gross_amount: Decimal
    wht_amount: Decimal
    net_amount: Decimal
    payment_count: int


class WHTReport(AccountingBaseSchema):
    period_start: date
    period_end: date
    rows: list[WHTReportRow]
    total_wht: Decimal


__all__ = [
    "TaxAmountResponse",
    "TaxCalculationRequest",
    "TaxCalculationResult",
    "TaxCodeCreateRequest",
    "TaxCodeResponse",
    "TaxCodeUpdateRequest",
    "TaxDetailRow",
    "TaxGroupCreateRequest",
    "TaxGroupLineCreateRequest",
    "TaxGroupLineResponse",
    "TaxGroupResponse",
    "TaxRateCreateRequest",
    "TaxRateResponse",
    "TaxSummaryReport",
    "TaxSummaryReportRow",
    "WHTReport",
    "WHTReportRow",
]

"""Pydantic schemas for the installment quote/preview operation.

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/quotes`; specs/010-installments/spec.md FR-INST-030.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentQuoteRequest(InstallmentsBaseSchema):
    """Request body for ``POST /quotes`` — mirrors
    ``InstallmentContractCreate``'s terms fields exactly (the same terms
    later become a real draft contract via ``POST /contracts``)."""

    sales_invoice_id: UUID
    down_payment_amount: Decimal = Field(..., ge=0)
    installment_count: int = Field(..., gt=0)
    frequency: str
    first_due_date: date
    markup_amount: Decimal = Field(Decimal("0"), ge=0)
    branch_id: UUID | None = None


class InstallmentQuotePreviewRead(InstallmentsBaseSchema):
    """Response body for ``POST /quotes`` (FR-INST-030's full field list)."""

    sales_invoice_id: UUID
    invoice_amount: Decimal
    eligible_amount: Decimal
    down_payment_amount: Decimal
    financed_principal: Decimal
    markup_amount: Decimal
    contractual_total: Decimal
    installment_count: int
    frequency: str
    first_due_date: date
    per_installment_amounts: tuple[Decimal, ...]
    final_installment_amount: Decimal
    expected_completion_date: date
    currency_code: str


class InstallmentScheduleLineRead(InstallmentsBaseSchema):
    """One schedule line (tasks.md T129). Due-state derivation
    (``UPCOMING``/``DUE``/``PARTIALLY_PAID``/``PAID``/``OVERDUE``) is
    Phase 8's ``DueStateCalculator`` (T138) — not yet available in this
    phase, deliberately not pulled forward here."""

    sequence: int
    due_date: date
    scheduled_amount: Decimal
    waived_at: datetime | None
    voided_at: datetime | None


class InstallmentScheduleRead(InstallmentsBaseSchema):
    """Response body for ``GET /contracts/{id}/schedule`` and
    ``GET /contracts/{id}/schedule/versions/{v}`` (tasks.md T129)."""

    contract_id: UUID
    version_number: int
    status: str
    generated_at: datetime
    lines: list[InstallmentScheduleLineRead]

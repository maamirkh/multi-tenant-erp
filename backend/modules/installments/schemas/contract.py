"""Pydantic schemas for Installments Contract create/read/summary.

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/contracts`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentContractRejectRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/reject`` — ``reason`` is
    mandatory (FR-INST-102)."""

    reason: str = Field(..., min_length=1)


class InstallmentContractCancelRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/cancel`` — ``reason`` is
    mandatory. Not yet wired to a router endpoint (Phase 10's T174)."""

    reason: str = Field(..., min_length=1)


class InstallmentContractDefaultRequest(InstallmentsBaseSchema):
    """Request body for the future ``POST /contracts/{id}/default`` —
    ``reason`` is mandatory. Not yet wired to a router endpoint (Phase
    10's T167; the underlying ``mark_defaulted()`` primitive this phase
    adds is internal-only and not reachable from any endpoint yet)."""

    reason: str = Field(..., min_length=1)


class InstallmentContractCreate(InstallmentsBaseSchema):
    """Request body for ``POST /contracts`` — create a DRAFT contract
    from custom terms (or informationally linked to a plan template via
    ``plan_template_id``, never dereferenced for calculation)."""

    sales_invoice_id: UUID
    down_payment_amount: Decimal = Field(..., ge=0)
    installment_count: int = Field(..., gt=0)
    frequency: str
    first_due_date: date
    maturity_date: date
    markup_amount: Decimal = Field(Decimal("0"), ge=0)
    plan_template_id: UUID | None = None
    branch_id: UUID | None = None
    contract_date: date | None = None


class InstallmentContractRead(InstallmentsBaseSchema):
    """Response body for full contract detail (``GET /contracts/{id}``,
    ``POST /contracts``)."""

    id: UUID
    company_id: UUID
    contract_number: str
    branch_id: UUID | None
    customer_id: UUID
    sales_invoice_id: UUID
    plan_template_id: UUID | None
    contract_date: date
    principal_amount: Decimal
    down_payment_amount: Decimal
    markup_amount: Decimal
    contractual_total: Decimal
    installment_count: int
    frequency: str
    first_due_date: date
    maturity_date: date
    currency_code: str
    status: str
    terms_snapshot: dict
    active_schedule_version_id: UUID | None
    submitted_by: UUID | None
    submitted_at: datetime | None
    approved_by: UUID | None
    approved_at: datetime | None
    activated_at: datetime | None
    closed_at: datetime | None
    defaulted_at: datetime | None
    cancelled_at: datetime | None
    written_off_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class InstallmentContractSummary(InstallmentsBaseSchema):
    """Response body for list rows (``GET /contracts``) — a lighter
    projection than full detail."""

    id: UUID
    contract_number: str
    customer_id: UUID
    sales_invoice_id: UUID
    status: str
    contractual_total: Decimal
    currency_code: str
    created_at: datetime

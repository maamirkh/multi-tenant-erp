"""Pydantic schemas for Collection/Reversal request-response (tasks.md
T125).

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/contracts/{contractId}/collections`, `/collections/{collectionId}/reverse`.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentCollectionCreate(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/collections``.

    Exactly one of ``bank_account_id``/``cash_account_id`` is required —
    mirrors Accounting's own ``PaymentService.stage_customer_payment()``
    contract exactly (no tenant-level default deposit account exists
    anywhere in the system to substitute for this)."""

    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., min_length=1)
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None


class InstallmentCollectionResultRead(InstallmentsBaseSchema):
    """Response body for a successful collection or reversal."""

    contract_id: UUID
    amount: Decimal | None = None
    accounting_payment_id: UUID | None = None
    collection_id: UUID | None = None
    contract_status: str | None = None
    status: str


class InstallmentCollectionReverseRequest(InstallmentsBaseSchema):
    """Request body for ``POST /collections/{id}/reverse`` — ``reason``
    is mandatory."""

    reason: str = Field(..., min_length=1)

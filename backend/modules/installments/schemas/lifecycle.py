"""Pydantic schemas for reschedule/cancel/default/cure/writeoff request
bodies (tasks.md T172). All five endpoints respond with the existing
``InstallmentContractRead`` (``StandardResponse<InstallmentContract>``
per the OpenAPI contract) — no new response schema is needed.

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/contracts/{contractId}/reschedule`, `/cancel`, `/default`, `/cure`,
`/writeoff`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentRescheduleRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/reschedule``.

    Only ``first_due_date``/``frequency`` are ever actually applied —
    ``principal_amount``/``markup_amount``/``installment_count`` are
    accepted solely so a caller's attempt to change them is explicitly
    rejected as restructuring (FR-INST-202), never silently ignored.
    ``requested_by`` must differ from the authenticated actor executing
    the request (FR-INST-201's maker-checker discipline)."""

    first_due_date: date
    frequency: str | None = None
    principal_amount: Decimal | None = None
    markup_amount: Decimal | None = None
    installment_count: int | None = None
    reason: str = Field(..., min_length=1)
    requested_by: UUID


class InstallmentCancelRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/cancel``. ``payment_id``
    is the down payment's Accounting ``Payment`` id — required only when
    the contract is ``ACTIVE`` with a recorded down payment (the caller
    already has it from ``activate()``'s own response or
    ``GET /contracts/{id}``)."""

    reason: str = Field(..., min_length=1)
    payment_id: UUID | None = None


class InstallmentDefaultRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/default``."""

    reason: str = Field(..., min_length=1)


class InstallmentCureRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/cure``."""

    reason: str | None = None


class InstallmentWriteoffRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/writeoff``."""

    reason: str = Field(..., min_length=1)
